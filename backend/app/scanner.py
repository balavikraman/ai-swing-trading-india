from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .engine import build_trade_proposal, score_candidate
from .market_data import MarketDataProvider
from .models import CandidateInput, ExperimentConfig, MarketRegime
from .universe import UniverseMember


@dataclass
class ScanResult:
    proposals: list
    skipped: list[dict]
    market_regime: MarketRegime


def detect_market_regime(nifty: pd.DataFrame) -> MarketRegime:
    if nifty is None or len(nifty) < 200:
        return MarketRegime.NEUTRAL
    close = nifty["Close"]
    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    dma50 = close.rolling(50).mean().iloc[-1]
    dma200 = close.rolling(200).mean().iloc[-1]
    price = close.iloc[-1]
    if price > ema20 > dma50 > dma200:
        return MarketRegime.BULLISH
    if price < ema20 and price < dma50:
        return MarketRegime.BEARISH
    return MarketRegime.NEUTRAL


def candidate_from_history(member: UniverseMember, frame: pd.DataFrame, regime: MarketRegime) -> CandidateInput | None:
    if frame is None or len(frame) < 220:
        return None
    df = frame.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    ema20 = close.ewm(span=20, adjust=False).mean()
    dma50 = close.rolling(50).mean()
    dma200 = close.rolling(200).mean()
    avg_vol20 = volume.rolling(20).mean()
    tr = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()

    price = float(close.iloc[-1])
    resistance = float(high.iloc[-16:-1].max())
    recent_lows = low.iloc[-16:-1]
    stop = float(max(recent_lows.min(), price - 1.5 * float(atr14.iloc[-1])))
    risk = price - stop
    if not np.isfinite(risk) or risk <= 0:
        return None

    consolidation_range = (float(high.iloc[-16:-1].max()) - float(low.iloc[-16:-1].min())) / price
    consolidation_days = 10 if consolidation_range <= 0.08 else 5 if consolidation_range <= 0.12 else 1
    breakout_volume = float(volume.iloc[-1])
    avg_volume = float(avg_vol20.iloc[-2]) if np.isfinite(avg_vol20.iloc[-2]) else 0
    if avg_volume <= 0:
        return None

    rs_63 = price / float(close.iloc[-64]) - 1 if len(close) >= 64 else 0
    relative_strength_score = float(np.clip((rs_63 + 0.10) / 0.30, 0, 1))
    atr_pct = float(atr14.iloc[-1]) / price
    volatility_quality = float(np.clip(1 - abs(atr_pct - 0.025) / 0.04, 0, 1))
    gap_pct = max(0.0, (price - resistance) / resistance * 100) if resistance > 0 else 0.0

    return CandidateInput(
        symbol=member.symbol,
        name=member.name,
        current_price=price,
        ema20=float(ema20.iloc[-1]),
        dma50=float(dma50.iloc[-1]),
        dma200=float(dma200.iloc[-1]),
        resistance=resistance,
        avg_volume_20d=avg_volume,
        breakout_volume=breakout_volume,
        consolidation_days=consolidation_days,
        relative_strength_score=relative_strength_score,
        volatility_quality=volatility_quality,
        stop_loss=stop,
        target1=price + 2 * risk,
        target2=price + 3 * risk,
        liquid=avg_volume * price >= 50_000_000,
        gap_pct_above_breakout=gap_pct,
        market_regime=regime,
    )


def scan_universe(provider: MarketDataProvider, members: list[UniverseMember], cfg: ExperimentConfig, period: str = "18mo") -> ScanResult:
    symbols = [m.symbol for m in members]
    histories = provider.history_many(symbols + ["^NSEI"], period=period)
    regime = detect_market_regime(histories.get("^NSEI"))
    proposals = []
    skipped = []
    for member in members:
        candidate = candidate_from_history(member, histories.get(member.symbol), regime)
        if candidate is None:
            skipped.append({"symbol": member.symbol, "reason": "insufficient/invalid market data"})
            continue
        proposal = build_trade_proposal(candidate, cfg)
        proposals.append(proposal)
    proposals.sort(key=lambda p: p.ai_score, reverse=True)
    return ScanResult(proposals=proposals, skipped=skipped, market_regime=regime)
