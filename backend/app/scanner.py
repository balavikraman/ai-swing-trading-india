from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from .engine import build_trade_proposal
from .events import CorporateEventProvider, evaluate_event_risk
from .market_data import MarketDataProvider
from .models import CandidateInput, ExperimentConfig, MarketRegime, PortfolioType
from .universe import UniverseMember


@dataclass
class ScanResult:
    proposals: list
    skipped: list[dict]
    market_regime: MarketRegime
    signal_date: date | None = None
    market_context: dict | None = None


def _frame_date(frame: pd.DataFrame | None) -> date | None:
    if frame is None or frame.empty:
        return None
    parsed = pd.to_datetime(frame.index[-1], errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def detect_market_regime(nifty: pd.DataFrame) -> MarketRegime:
    if nifty is None or len(nifty) < 200:
        return MarketRegime.NEUTRAL
    close = nifty["Close"]
    price = close.iloc[-1]
    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    dma50 = close.rolling(50).mean().iloc[-1]
    dma200 = close.rolling(200).mean().iloc[-1]
    if price > ema20 > dma50 > dma200:
        return MarketRegime.BULLISH
    if price < ema20 and price < dma50:
        return MarketRegime.BEARISH
    return MarketRegime.NEUTRAL


def compute_market_context(histories: dict[str, pd.DataFrame], members: list[UniverseMember]) -> dict:
    valid: list[str] = []
    advances = above20 = above50 = above200 = 0
    sector_returns: dict[str, list[float]] = {}
    for member in members:
        frame = histories.get(member.symbol)
        if frame is None or len(frame) < 200:
            continue
        close = frame["Close"]
        last = float(close.iloc[-1])
        valid.append(member.symbol)
        advances += last > float(close.iloc[-2])
        above20 += last > float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        above50 += last > float(close.rolling(50).mean().iloc[-1])
        above200 += last > float(close.rolling(200).mean().iloc[-1])
        if member.industry and len(close) >= 21:
            sector_returns.setdefault(member.industry, []).append(last / float(close.iloc[-21]) - 1)

    count = len(valid)
    if not count:
        return {
            "coverage": 0,
            "breadth_score": 0.5,
            "advance_decline_pct": None,
            "above_20ema_pct": None,
            "above_50dma_pct": None,
            "above_200dma_pct": None,
            "leading_industries": [],
        }

    advance_ratio = advances / count
    ratio20 = above20 / count
    ratio50 = above50 / count
    ratio200 = above200 / count
    breadth = float(np.clip(0.25 * advance_ratio + 0.30 * ratio20 + 0.25 * ratio50 + 0.20 * ratio200, 0, 1))
    sectors = sorted(
        ((industry, sum(values) / len(values)) for industry, values in sector_returns.items() if values),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    return {
        "coverage": count,
        "breadth_score": round(breadth, 4),
        "advance_decline_pct": round(advance_ratio * 100, 2),
        "above_20ema_pct": round(ratio20 * 100, 2),
        "above_50dma_pct": round(ratio50 * 100, 2),
        "above_200dma_pct": round(ratio200 * 100, 2),
        "leading_industries": [{"industry": industry, "return_20d_pct": round(ret * 100, 2)} for industry, ret in sectors],
    }


def _consolidation(high: pd.Series, low: pd.Series, price: float) -> tuple[int, float, float]:
    for days in range(15, 4, -1):
        highs = high.iloc[-days - 1 : -1]
        lows = low.iloc[-days - 1 : -1]
        if len(highs) != days:
            continue
        range_pct = (float(highs.max()) - float(lows.min())) / price
        if range_pct <= 0.12:
            return days, float(highs.max()), float(lows.min())
    highs = high.iloc[-16:-1]
    lows = low.iloc[-16:-1]
    return 1, float(highs.max()), float(lows.min())


def candidate_from_history(
    member: UniverseMember,
    frame: pd.DataFrame,
    regime: MarketRegime,
    benchmark_frame: pd.DataFrame | None = None,
    market_breadth_score: float = 0.5,
) -> CandidateInput | None:
    if frame is None or len(frame) < 220:
        return None
    close = frame["Close"]
    high = frame["High"]
    low = frame["Low"]
    open_ = frame["Open"]
    volume = frame["Volume"]

    ema20 = close.ewm(span=20, adjust=False).mean()
    dma50 = close.rolling(50).mean()
    dma200 = close.rolling(200).mean()
    avg_volume20 = volume.rolling(20).mean()
    tr = pd.concat([(high - low), (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()

    price = float(close.iloc[-1])
    consolidation_days, resistance, consolidation_low = _consolidation(high, low, price)
    atr = float(atr14.iloc[-1])
    stop = float(max(consolidation_low, price - 1.5 * atr))
    risk = price - stop
    avg_volume = float(avg_volume20.iloc[-2]) if np.isfinite(avg_volume20.iloc[-2]) else 0
    if not np.isfinite(risk) or risk <= 0 or avg_volume <= 0:
        return None

    stock_return = price / float(close.iloc[-64]) - 1 if len(close) >= 64 else 0
    benchmark_return = 0.0
    if benchmark_frame is not None and len(benchmark_frame) >= 64:
        benchmark_close = benchmark_frame["Close"]
        benchmark_return = float(benchmark_close.iloc[-1]) / float(benchmark_close.iloc[-64]) - 1
    excess_return = stock_return - benchmark_return
    relative_strength_score = float(np.clip((excess_return + 0.10) / 0.30, 0, 1))

    atr_pct = atr / price
    volatility_quality = float(np.clip(1 - abs(atr_pct - 0.025) / 0.04, 0, 1))
    opening_gap_pct = max(0.0, (float(open_.iloc[-1]) - resistance) / resistance * 100) if resistance > 0 else 0.0

    return CandidateInput(
        symbol=member.symbol,
        name=member.name,
        signal_date=_frame_date(frame),
        current_price=price,
        ema20=float(ema20.iloc[-1]),
        dma50=float(dma50.iloc[-1]),
        dma200=float(dma200.iloc[-1]),
        resistance=resistance,
        avg_volume_20d=avg_volume,
        breakout_volume=float(volume.iloc[-1]),
        consolidation_days=consolidation_days,
        relative_strength_score=relative_strength_score,
        volatility_quality=volatility_quality,
        stop_loss=stop,
        target1=price + 2 * risk,
        target2=price + 3 * risk,
        liquid=avg_volume * price >= 50_000_000,
        gap_pct_above_breakout=opening_gap_pct,
        market_regime=regime,
        market_breadth_score=market_breadth_score,
    )


def scan_universe(
    provider: MarketDataProvider,
    members: list[UniverseMember],
    cfg: ExperimentConfig,
    period: str = "18mo",
    event_provider: CorporateEventProvider | None = None,
) -> ScanResult:
    symbols = [member.symbol for member in members]
    histories = provider.history_many(symbols + ["^NSEI"], period=period)
    nifty = histories.get("^NSEI")
    regime = detect_market_regime(nifty)
    market_context = compute_market_context(histories, members)
    proposals = []
    skipped = []

    for member in members:
        candidate = candidate_from_history(
            member,
            histories.get(member.symbol),
            regime,
            nifty,
            market_context["breadth_score"],
        )
        if candidate is None:
            skipped.append({"symbol": member.symbol, "reason": "insufficient/invalid market data"})
            continue
        proposal = build_trade_proposal(candidate, cfg)
        if event_provider is not None and proposal.classification != PortfolioType.NO_TRADE and candidate.signal_date is not None:
            event_check = evaluate_event_risk(member.symbol, candidate.signal_date, event_provider, cfg)
            candidate = candidate.model_copy(
                update={
                    "major_event_nearby": event_check.blocked,
                    "event_reason": event_check.reason,
                    "event_data_status": event_check.status,
                }
            )
            proposal = build_trade_proposal(candidate, cfg)
        proposals.append(proposal)

    proposals.sort(key=lambda proposal: proposal.ai_score, reverse=True)
    return ScanResult(proposals, skipped, regime, _frame_date(nifty), market_context)
