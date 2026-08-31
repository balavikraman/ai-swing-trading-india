from math import floor
from .models import CandidateInput, ExperimentConfig, PortfolioType, TradeProposal, MarketRegime


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(v, hi))


def score_candidate(c: CandidateInput) -> tuple[float, dict[str, float]]:
    trend_checks = [c.current_price > c.ema20, c.current_price > c.dma50, c.current_price > c.dma200, c.ema20 > c.dma50, c.dma50 > c.dma200]
    trend = 20 * sum(trend_checks) / len(trend_checks)
    breakout = 0.0
    breakout += 8 if c.current_price >= c.resistance else 0
    breakout += 8 if 5 <= c.consolidation_days <= 15 else (4 if 3 <= c.consolidation_days <= 20 else 0)
    breakout += 4 if c.gap_pct_above_breakout <= 2 else 0
    volume_ratio = c.breakout_volume / c.avg_volume_20d
    volume = 15 * _clamp((volume_ratio - 1.0) / 0.8, 0, 1)
    relative_strength = 15 * c.relative_strength_score
    risk = c.current_price - c.stop_loss
    reward = c.target1 - c.current_price
    rr = reward / risk if risk > 0 else 0
    rr_quality = 15 * _clamp(rr / 3.0, 0, 1)
    market = {MarketRegime.BULLISH: 10.0, MarketRegime.NEUTRAL: 6.0, MarketRegime.BEARISH: 0.0}[c.market_regime]
    volatility = 5 * c.volatility_quality
    components = {
        "trend_strength": round(trend, 2), "breakout_quality": round(breakout, 2), "volume_confirmation": round(volume, 2),
        "relative_strength": round(relative_strength, 2), "risk_reward_quality": round(rr_quality, 2),
        "broader_market_trend": round(market, 2), "volatility_quality": round(volatility, 2),
    }
    return round(sum(components.values()), 2), components


def build_trade_proposal(c: CandidateInput, cfg: ExperimentConfig) -> TradeProposal:
    score, components = score_candidate(c)
    entry = c.current_price
    per_share_risk = entry - c.stop_loss
    reward_per_share = c.target1 - entry
    rr = reward_per_share / per_share_risk if per_share_risk > 0 else 0
    quantity_by_risk = floor(cfg.max_rupee_risk / per_share_risk) if per_share_risk > 0 else 0
    quantity_by_capital = floor(cfg.capital / entry)
    live_qty = max(0, min(quantity_by_risk, quantity_by_capital))
    hard_reasons = []
    if not c.liquid: hard_reasons.append("illiquid instrument")
    if c.major_event_nearby: hard_reasons.append(c.event_reason or "major company event/results nearby")
    if c.market_regime == MarketRegime.BEARISH: hard_reasons.append("broader market regime is bearish")
    if c.gap_pct_above_breakout > cfg.max_gap_pct: hard_reasons.append("breakout is too extended/gapped")
    if per_share_risk <= 0: hard_reasons.append("invalid stop: stop must be below entry")
    if rr < cfg.min_rr: hard_reasons.append(f"risk/reward {rr:.2f} is below minimum {cfg.min_rr:.2f}")
    if score < cfg.min_score_for_trade: hard_reasons.append(f"score {score:.1f} is below trade threshold {cfg.min_score_for_trade:.1f}")
    if hard_reasons:
        classification, qty, decision_reason = PortfolioType.NO_TRADE, 0, "; ".join(hard_reasons)
    elif live_qty >= 1:
        classification, qty = PortfolioType.LIVE, live_qty
        decision_reason = "Meets strategy and risk rules and fits current live capital. Human confirmation still required."
    else:
        classification = PortfolioType.PAPER
        qty = max(1, quantity_by_risk) if quantity_by_risk > 0 else 1
        decision_reason = "Valid strategy setup but cannot be purchased within the live account constraints; track in shadow portfolio."
    capital_required = qty * entry
    planned_loss = qty * per_share_risk if per_share_risk > 0 else 0
    potential_reward = qty * reward_per_share if reward_per_share > 0 else 0
    technical_reason = (f"Price {entry:.2f}; EMA20 {c.ema20:.2f}; DMA50 {c.dma50:.2f}; DMA200 {c.dma200:.2f}; "
                        f"{c.consolidation_days}-day consolidation; breakout volume {c.breakout_volume/c.avg_volume_20d:.2f}× 20-day average.")
    market_reason = f"Broader market regime: {c.market_regime.value}."
    return TradeProposal(
        symbol=c.symbol, name=c.name, signal_date=c.signal_date, current_price=entry, setup_type="uptrend consolidation breakout",
        entry_zone_low=round(c.resistance, 2), entry_zone_high=round(max(c.resistance, entry), 2), stop_loss=round(c.stop_loss, 2),
        target1=round(c.target1, 2), target2=round(c.target2, 2) if c.target2 else None, quantity=qty,
        capital_required=round(capital_required, 2), maximum_planned_loss=round(planned_loss, 2), potential_reward=round(potential_reward, 2),
        risk_reward_ratio=round(rr, 2), ai_score=score, score_components=components, classification=classification,
        technical_reason=technical_reason, market_reason=market_reason, decision_reason=decision_reason,
        event_risk=c.major_event_nearby, event_reason=c.event_reason, event_data_status=c.event_data_status,
    )
