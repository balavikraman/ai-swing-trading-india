from __future__ import annotations

import os
from dataclasses import dataclass

from .engine import build_trade_proposal
from .models import ExperimentConfig, PortfolioType
from .outcomes import SimulationConfig, simulate_signal
from .scanner import candidate_from_history, detect_market_regime
from .universe import UniverseMember


@dataclass(frozen=True)
class BacktestCostModel:
    buy_cost_bps: float = 5.0
    sell_cost_bps: float = 10.0
    slippage_bps: float = 5.0

    @classmethod
    def from_env(cls):
        return cls(float(os.getenv("BACKTEST_BUY_COST_BPS", "5")), float(os.getenv("BACKTEST_SELL_COST_BPS", "10")), float(os.getenv("BACKTEST_SLIPPAGE_BPS", "5")))


def _metrics(trades: list[dict]) -> dict:
    pnls = [trade["net_pnl"] for trade in trades]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = peak = 0.0
    drawdown = 0.0
    streak = best_streak = 0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = min(drawdown, equity - peak)
        if pnl < 0:
            streak += 1
            best_streak = max(best_streak, streak)
        else:
            streak = 0
    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 2) if trades else None,
        "net_pnl": round(sum(pnls), 2),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "average_net_pnl": round(sum(pnls) / len(pnls), 2) if pnls else None,
        "average_r": round(sum(trade["net_r"] for trade in trades) / len(trades), 4) if trades else None,
        "max_drawdown": round(drawdown, 2),
        "max_consecutive_losses": best_streak,
        "average_holding_sessions": round(sum(trade["holding_sessions"] for trade in trades) / len(trades), 2) if trades else None,
    }


def backtest_symbol(provider, symbol: str, cfg: ExperimentConfig, period: str = "5y", max_holding_sessions: int = 20, entry_valid_sessions: int = 3, costs: BacktestCostModel | None = None, max_signals: int = 500) -> dict:
    costs = costs or BacktestCostModel.from_env()
    histories = provider.history_many([symbol, "^NSEI"], period=period)
    frame = histories.get(symbol)
    nifty = histories.get("^NSEI")
    if frame is None or len(frame) < 250 or nifty is None or len(nifty) < 220:
        raise ValueError("insufficient historical data for backtest")

    member = UniverseMember(symbol, symbol)
    trades = []
    last_exit = None
    for i in range(219, len(frame) - 2):
        signal_slice = frame.iloc[: i + 1]
        signal_date = signal_slice.index[-1]
        benchmark = nifty.loc[nifty.index <= signal_date]
        if len(benchmark) < 200:
            continue
        candidate = candidate_from_history(member, signal_slice, detect_market_regime(benchmark), benchmark, 0.5)
        if candidate is None:
            continue
        proposal = build_trade_proposal(candidate, cfg)
        if proposal.classification == PortfolioType.NO_TRADE:
            continue
        simulation = simulate_signal(proposal.model_dump(mode="python"), frame, SimulationConfig(entry_valid_sessions=entry_valid_sessions, max_holding_sessions=max_holding_sessions, history_period=period))
        if simulation.get("status") not in {"TARGET1", "STOPPED", "TIME_EXIT"} or simulation.get("entry_price") is None or simulation.get("exit_price") is None:
            continue
        if last_exit is not None and simulation["entry_date"] <= last_exit:
            continue
        quantity = max(1, int(proposal.quantity))
        entry = float(simulation["entry_price"])
        exit_price = float(simulation["exit_price"])
        gross = (exit_price - entry) * quantity
        friction = (entry * quantity * costs.buy_cost_bps + exit_price * quantity * costs.sell_cost_bps + (entry + exit_price) * quantity * costs.slippage_bps) / 10000
        net = gross - friction
        risk = max(entry - proposal.stop_loss, 1e-9) * quantity
        trades.append({"signal_date": proposal.signal_date, "entry_date": simulation["entry_date"], "exit_date": simulation["exit_date"], "status": simulation["status"], "base_score": proposal.ai_score, "entry": entry, "exit": exit_price, "stop": proposal.stop_loss, "target1": proposal.target1, "quantity": quantity, "gross_pnl": round(gross, 2), "estimated_costs": round(friction, 2), "net_pnl": round(net, 2), "net_r": round(net / risk, 4), "holding_sessions": simulation.get("holding_sessions") or 0})
        last_exit = simulation["exit_date"]
        if len(trades) >= max_signals:
            break

    benchmark_result = None
    if trades:
        start = trades[0]["signal_date"]
        end = trades[-1]["exit_date"]
        benchmark = nifty[(nifty.index.date >= start) & (nifty.index.date <= end)]
        if len(benchmark) >= 2:
            benchmark_result = {"name": "NIFTY50", "return_pct": round((float(benchmark["Close"].iloc[-1]) / float(benchmark["Close"].iloc[0]) - 1) * 100, 4), "start": start, "end": end}

    return {
        "symbol": symbol,
        "period": period,
        "strategy": "strict uptrend consolidation breakout",
        "cost_model_bps": costs.__dict__,
        "metrics": _metrics(trades),
        "benchmark": benchmark_result,
        "trades": trades,
        "limitations": [
            "Historical earnings/news intelligence is not replayed in this technical-core backtest yet.",
            "Nifty 200 historical benchmark comparison should use the Zerodha/official-index adapter once credentials are configured.",
            "Daily OHLC ambiguity is handled by the same conservative simulation policy used by paper tracking.",
        ],
    }
