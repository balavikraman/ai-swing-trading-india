from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, or_, select
from sqlalchemy.orm import Mapped, mapped_column

from .journal import Base, JournalService, SignalRecord
from .market_data import MarketDataProvider
from .models import PortfolioType


TERMINAL_STATUSES = {"TARGET1", "STOPPED", "TIME_EXIT", "ENTRY_EXPIRED"}


class SignalSimulationRecord(Base):
    __tablename__ = "signal_simulations"
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    provider: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), index=True)
    exit_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_last_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    profit_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentage_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    unrealized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    unrealized_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    holding_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stop_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    target1_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    target2_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    entry_expired: Mapped[bool] = mapped_column(Boolean, default=False)
    ambiguous_bar: Mapped[bool] = mapped_column(Boolean, default=False)
    assumptions: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


@dataclass(frozen=True)
class SimulationConfig:
    entry_valid_sessions: int = 3
    max_holding_sessions: int = 20
    history_period: str = "2y"

    def __post_init__(self):
        if self.entry_valid_sessions < 1:
            raise ValueError("entry_valid_sessions must be >= 1")
        if self.max_holding_sessions < 1:
            raise ValueError("max_holding_sessions must be >= 1")


def _signal_dict(signal: SignalRecord) -> dict:
    return {c.name: getattr(signal, c.name) for c in SignalRecord.__table__.columns}


def _simulation_dict(simulation: SignalSimulationRecord) -> dict:
    return {c.name: getattr(simulation, c.name) for c in SignalSimulationRecord.__table__.columns}


def get_trackable_signals(journal: JournalService, limit: int = 200) -> list[dict]:
    journal.init_schema()
    stmt = (
        select(SignalRecord)
        .outerjoin(SignalSimulationRecord, SignalSimulationRecord.signal_id == SignalRecord.id)
        .where(
            SignalRecord.classification.in_([PortfolioType.LIVE.value, PortfolioType.PAPER.value]),
            SignalRecord.signal_date.is_not(None),
            or_(SignalSimulationRecord.signal_id.is_(None), SignalSimulationRecord.status.not_in(TERMINAL_STATUSES)),
        )
        .order_by(SignalRecord.signal_date.asc(), SignalRecord.id.asc())
        .limit(max(1, min(limit, 1000)))
    )
    with journal.Session() as session:
        return [_signal_dict(s) for s in session.scalars(stmt).all()]


def save_simulation(journal: JournalService, signal_id: int, result: dict, provider: str, assumptions: dict) -> dict:
    journal.init_schema()
    with journal.Session.begin() as session:
        simulation = session.get(SignalSimulationRecord, signal_id)
        if simulation is None:
            simulation = SignalSimulationRecord(signal_id=signal_id, provider=provider, status=result["status"])
            session.add(simulation)
        simulation.provider = provider
        simulation.assumptions = assumptions
        simulation.updated_at = datetime.now(timezone.utc)
        for key, value in result.items():
            setattr(simulation, key, value)
        session.flush()
        return _simulation_dict(simulation)


def list_simulations(journal: JournalService, limit: int = 100, classification: str | None = None, status: str | None = None) -> list[dict]:
    journal.init_schema()
    stmt = (
        select(SignalRecord, SignalSimulationRecord)
        .join(SignalSimulationRecord, SignalSimulationRecord.signal_id == SignalRecord.id)
        .order_by(SignalSimulationRecord.updated_at.desc(), SignalRecord.id.desc())
        .limit(max(1, min(limit, 1000)))
    )
    if classification:
        stmt = stmt.where(SignalRecord.classification == classification.strip().upper())
    if status:
        stmt = stmt.where(SignalSimulationRecord.status == status.strip().upper())
    with journal.Session() as session:
        return [{"signal": _signal_dict(sig), "simulation": _simulation_dict(sim)} for sig, sim in session.execute(stmt).all()]


def simulation_summary(journal: JournalService) -> dict:
    journal.init_schema()
    closed_statuses = {"TARGET1", "STOPPED", "TIME_EXIT"}
    with journal.Session() as session:
        rows = session.execute(select(SignalRecord, SignalSimulationRecord).join(SignalSimulationRecord, SignalSimulationRecord.signal_id == SignalRecord.id)).all()

    def summarize(classification: str | None = None) -> dict:
        selected = [(s, m) for s, m in rows if classification is None or s.classification == classification]
        closed = [(s, m) for s, m in selected if m.status in closed_statuses and m.profit_loss is not None]
        wins = [m for _, m in closed if m.profit_loss > 0]
        losses = [m for _, m in closed if m.profit_loss < 0]
        gross_profit = sum(m.profit_loss for m in wins)
        gross_loss = abs(sum(m.profit_loss for m in losses))
        returns = [m.percentage_return for _, m in closed if m.percentage_return is not None]
        multiples = [m.realized_r_multiple for _, m in closed if m.realized_r_multiple is not None]
        return {
            "tracked": len(selected),
            "closed": len(closed),
            "open": sum(m.status == "OPEN" for _, m in selected),
            "pending_entry": sum(m.status in {"PENDING_ENTRY", "NO_DATA"} for _, m in selected),
            "entry_expired": sum(m.status == "ENTRY_EXPIRED" for _, m in selected),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(len(wins) / len(closed) * 100, 2) if closed else None,
            "total_pnl": round(sum(m.profit_loss for _, m in closed), 2),
            "average_return_pct": round(sum(returns) / len(returns), 4) if returns else None,
            "average_r_multiple": round(sum(multiples) / len(multiples), 4) if multiples else None,
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
        }

    return {
        "all": summarize(),
        "paper": summarize(PortfolioType.PAPER.value),
        "live_simulated": summarize(PortfolioType.LIVE.value),
        "note": "These are rule-based simulated outcomes from daily OHLC bars, not actual broker fills. Same-bar ambiguity is resolved pessimistically.",
    }


def _as_date(value) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _future_bars(frame: pd.DataFrame, signal_date: date) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    df = frame.copy()
    dates = pd.to_datetime(df.index, errors="coerce")
    return df.loc[dates.date > signal_date]


def _entry_fill(bar, low: float, high: float) -> tuple[float | None, bool]:
    open_price = float(bar["Open"])
    day_high = float(bar["High"])
    day_low = float(bar["Low"])
    if low <= open_price <= high:
        return open_price, True
    if open_price < low and day_high >= low:
        return low, False
    if open_price > high and day_low <= high:
        return high, False
    return None, False


def simulate_signal(signal: dict, frame: pd.DataFrame, cfg: SimulationConfig) -> dict:
    signal_date = signal.get("signal_date")
    if signal_date is None:
        return {"status": "NO_DATA", "notes": "signal date missing"}
    if frame is None or frame.empty:
        return {"status": "NO_DATA", "data_last_date": None, "notes": "market data unavailable"}

    future = _future_bars(frame, signal_date)
    data_last_date = _as_date(frame.index[-1])
    if future.empty:
        return {"status": "PENDING_ENTRY", "data_last_date": data_last_date, "notes": "no post-signal daily bar available yet"}

    entry_low = float(signal["entry_zone_low"])
    entry_high = float(signal["entry_zone_high"])
    stop = float(signal["stop_loss"])
    target1 = float(signal["target1"])
    target2 = float(signal["target2"]) if signal.get("target2") is not None else None
    qty = max(1, int(signal.get("quantity") or 1))

    entry_price = None
    entry_pos = None
    entered_at_open = False
    for pos, (_, bar) in enumerate(future.iloc[: cfg.entry_valid_sessions].iterrows()):
        fill, at_open = _entry_fill(bar, entry_low, entry_high)
        if fill is not None:
            entry_price = fill
            entry_pos = pos
            entered_at_open = at_open
            break

    if entry_price is None:
        if len(future) >= cfg.entry_valid_sessions:
            return {"status": "ENTRY_EXPIRED", "data_last_date": data_last_date, "entry_expired": True, "notes": f"entry zone not reached within {cfg.entry_valid_sessions} post-signal sessions"}
        return {"status": "PENDING_ENTRY", "data_last_date": data_last_date, "notes": "entry zone not reached yet; entry window still open"}

    trade = future.iloc[entry_pos : entry_pos + cfg.max_holding_sessions].copy()
    entry_date = _as_date(trade.index[0])
    risk = entry_price - stop
    min_low = entry_price
    max_high = entry_price
    ambiguous = False
    exit_price = None
    exit_date = None
    status = "OPEN"
    exit_reason = None
    stop_hit = False
    target1_hit = False
    target2_hit = False
    holding_sessions = None

    for i, (idx, bar) in enumerate(trade.iterrows(), start=1):
        low = float(bar["Low"])
        high = float(bar["High"])
        stop_touched = low <= stop
        target_touched = high >= target1
        target2_touched = target2 is not None and high >= target2

        if i == 1 and not entered_at_open:
            if stop_touched:
                min_low = min(min_low, stop)
                status = "STOPPED"
                exit_reason = "STOP"
                exit_price = stop
                exit_date = _as_date(idx)
                stop_hit = True
                ambiguous = True
                holding_sessions = i
                break
            min_low = min(min_low, low)
            continue

        if stop_touched and target_touched:
            min_low = min(min_low, stop)
            status = "STOPPED"
            exit_reason = "STOP_SAME_BAR_AMBIGUITY"
            exit_price = stop
            exit_date = _as_date(idx)
            stop_hit = True
            target1_hit = True
            target2_hit = target2_touched
            ambiguous = True
            holding_sessions = i
            break

        if stop_touched:
            min_low = min(min_low, stop)
            status = "STOPPED"
            exit_reason = "STOP"
            exit_price = stop
            exit_date = _as_date(idx)
            stop_hit = True
            holding_sessions = i
            break

        if target_touched:
            min_low = min(min_low, low)
            max_high = max(max_high, target1)
            status = "TARGET1"
            exit_reason = "TARGET1"
            exit_price = target1
            exit_date = _as_date(idx)
            target1_hit = True
            target2_hit = target2_touched
            holding_sessions = i
            break

        min_low = min(min_low, low)
        max_high = max(max_high, high)

    if status == "OPEN" and len(trade) >= cfg.max_holding_sessions:
        last = trade.iloc[cfg.max_holding_sessions - 1]
        exit_price = float(last["Close"])
        exit_date = _as_date(trade.index[cfg.max_holding_sessions - 1])
        status = "TIME_EXIT"
        exit_reason = "MAX_HOLDING"
        holding_sessions = cfg.max_holding_sessions

    mae_pct = (min_low / entry_price - 1) * 100
    mfe_pct = (max_high / entry_price - 1) * 100
    mae_r = (min_low - entry_price) / risk if risk > 0 else None
    mfe_r = (max_high - entry_price) / risk if risk > 0 else None
    result = {
        "status": status,
        "exit_reason": exit_reason,
        "data_last_date": data_last_date,
        "entry_price": round(entry_price, 4),
        "entry_date": entry_date,
        "exit_price": round(exit_price, 4) if exit_price is not None else None,
        "exit_date": exit_date,
        "mae_pct": round(mae_pct, 4),
        "mfe_pct": round(mfe_pct, 4),
        "mae_r": round(mae_r, 4) if mae_r is not None else None,
        "mfe_r": round(mfe_r, 4) if mfe_r is not None else None,
        "holding_sessions": holding_sessions or len(trade),
        "stop_hit": stop_hit,
        "target1_hit": target1_hit,
        "target2_hit": target2_hit,
        "entry_expired": False,
        "ambiguous_bar": ambiguous,
        "notes": "daily-bar simulation: no same-bar target credit for intraday-triggered entries; stop wins stop/target ambiguity",
    }

    if exit_price is not None:
        pnl = (exit_price - entry_price) * qty
        return_pct = (exit_price / entry_price - 1) * 100
        realized_r = (exit_price - entry_price) / risk if risk > 0 else None
        result.update({"profit_loss": round(pnl, 2), "percentage_return": round(return_pct, 4), "realized_r_multiple": round(realized_r, 4) if realized_r is not None else None, "unrealized_pnl": None, "unrealized_return_pct": None})
    else:
        last_close = float(trade.iloc[-1]["Close"])
        result.update({"profit_loss": None, "percentage_return": None, "realized_r_multiple": None, "unrealized_pnl": round((last_close - entry_price) * qty, 2), "unrealized_return_pct": round((last_close / entry_price - 1) * 100, 4)})
    return result


class OutcomeTracker:
    def __init__(self, journal: JournalService, provider: MarketDataProvider, cfg: SimulationConfig | None = None):
        self.journal = journal
        self.provider = provider
        self.cfg = cfg or SimulationConfig()

    def refresh(self, limit: int = 200) -> dict:
        signals = get_trackable_signals(self.journal, limit)
        symbols = list(dict.fromkeys(s["symbol"] for s in signals))
        histories = self.provider.history_many(symbols, period=self.cfg.history_period) if symbols else {}
        updated = []
        errors = []
        assumptions = {
            "entry_valid_sessions": self.cfg.entry_valid_sessions,
            "max_holding_sessions": self.cfg.max_holding_sessions,
            "history_period": self.cfg.history_period,
            "entry_model": "first post-signal zone touch; no chasing above entry zone",
            "target_model": "full simulated exit at Target 1",
            "same_bar_policy": "stop first; intraday-triggered entry bar receives no target credit",
        }
        for signal in signals:
            try:
                result = simulate_signal(signal, histories.get(signal["symbol"]), self.cfg)
                updated.append(save_simulation(self.journal, signal["id"], result, self.provider.name, assumptions))
            except Exception as exc:
                errors.append({"signal_id": signal["id"], "symbol": signal["symbol"], "error": str(exc)})
        return {
            "provider": self.provider.name,
            "requested": len(signals),
            "updated": len(updated),
            "errors": errors,
            "terminal": sum(r["status"] in TERMINAL_STATUSES for r in updated),
            "open": sum(r["status"] == "OPEN" for r in updated),
            "pending_entry": sum(r["status"] in {"PENDING_ENTRY", "NO_DATA"} for r in updated),
        }
