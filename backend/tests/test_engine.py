from app.engine import score_candidate, build_trade_proposal
from app.models import CandidateInput, ExperimentConfig, MarketRegime, PortfolioType


def strong_candidate(price=500):
    return CandidateInput(
        symbol="TEST",
        name="Test Ltd",
        current_price=price,
        ema20=price * 0.96,
        dma50=price * 0.92,
        dma200=price * 0.80,
        resistance=price * 0.995,
        avg_volume_20d=100000,
        breakout_volume=180000,
        consolidation_days=10,
        relative_strength_score=0.9,
        volatility_quality=0.8,
        stop_loss=price * 0.96,
        target1=price * 1.08,
        market_regime=MarketRegime.BULLISH,
    )


def test_score_is_high_for_clean_setup():
    score, parts = score_candidate(strong_candidate())
    assert score >= 80
    assert round(sum(parts.values()), 2) == score


def test_live_when_affordable_and_risk_allows():
    c = strong_candidate(price=500)
    p = build_trade_proposal(c, ExperimentConfig(capital=1000, max_rupee_risk=20))
    assert p.classification == PortfolioType.LIVE
    assert p.quantity >= 1


def test_paper_when_valid_but_not_affordable():
    c = strong_candidate(price=2500)
    p = build_trade_proposal(c, ExperimentConfig(capital=1000, max_rupee_risk=100))
    assert p.classification == PortfolioType.PAPER


def test_no_trade_in_bearish_market():
    c = strong_candidate()
    c.market_regime = MarketRegime.BEARISH
    p = build_trade_proposal(c, ExperimentConfig(capital=1000, max_rupee_risk=20))
    assert p.classification == PortfolioType.NO_TRADE
