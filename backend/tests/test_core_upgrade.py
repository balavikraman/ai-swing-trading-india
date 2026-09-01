import numpy as np
import pandas as pd

from app.engine import build_trade_proposal
from app.models import ExperimentConfig, MarketRegime, PortfolioType
from app.scanner import candidate_from_history, compute_market_context
from app.universe import UniverseMember


def make_history(start=100, days=240, benchmark=False):
    idx = pd.date_range("2025-01-01", periods=days, freq="B")
    close = np.linspace(start, start * (1.20 if benchmark else 1.35), days)
    high = close * 1.01
    low = close * 0.99
    open_ = close * 0.998
    volume = np.full(days, 100_000.0)
    high[-16:-1] = close[-16:-1] * 1.005
    low[-16:-1] = close[-16:-1] * 0.995
    close[-1] = high[-16:-1].max() * 1.003
    high[-1] = close[-1] * 1.003
    low[-1] = close[-1] * 0.99
    open_[-1] = high[-16:-1].max() * 1.001
    volume[-1] = 190_000
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)


def test_rs_is_relative_to_nifty_and_gap_uses_open():
    stock = make_history(300)
    benchmark = make_history(20_000, benchmark=True)
    benchmark["Close"] = np.linspace(20_000, 21_000, len(benchmark))
    benchmark["Open"] = benchmark["Close"] * 0.998
    benchmark["High"] = benchmark["Close"] * 1.002
    benchmark["Low"] = benchmark["Close"] * 0.998
    candidate = candidate_from_history(UniverseMember("AAA", "A", "IT"), stock, MarketRegime.BULLISH, benchmark, 0.8)
    assert candidate.relative_strength_score > 0.5
    assert candidate.gap_pct_above_breakout < 1
    assert 5 <= candidate.consolidation_days <= 15


def test_strict_trend_is_a_hard_rule():
    stock = make_history(300)
    benchmark = make_history(20_000, benchmark=True)
    candidate = candidate_from_history(UniverseMember("AAA", "A"), stock, MarketRegime.BULLISH, benchmark, 0.8)
    candidate = candidate.model_copy(update={"current_price": candidate.dma50 * 0.99})
    proposal = build_trade_proposal(candidate, ExperimentConfig(max_rupee_risk=100, min_score_for_trade=0))
    assert proposal.classification == PortfolioType.NO_TRADE
    assert "strict trend" in proposal.decision_reason


def test_market_breadth_reports_components():
    members = [UniverseMember("A", "A", "IT"), UniverseMember("B", "B", "Bank")]
    context = compute_market_context({"A": make_history(100), "B": make_history(200)}, members)
    assert context["coverage"] == 2
    assert context["above_50dma_pct"] >= 50
    assert context["leading_industries"]
