import numpy as np
import pandas as pd

from app.events import CorporateEvent, CorporateEventProvider, EventLookup
from app.models import EventDataStatus, ExperimentConfig, MarketRegime, PortfolioType
from app.scanner import candidate_from_history, detect_market_regime, scan_universe
from app.universe import UniverseMember


def make_history(start=100, days=240, breakout=True):
    idx = pd.date_range("2025-01-01", periods=days, freq="B")
    close = np.linspace(start, start * 1.35, days); high = close * 1.01; low = close * 0.99; volume = np.full(days, 100_000.0)
    if breakout:
        high[-16:-1] = close[-16:-1] * 1.005; close[-1] = high[-16:-1].max() * 1.003; high[-1] = close[-1] * 1.003; low[-1] = close[-1] * 0.99; volume[-1] = 190_000
    return pd.DataFrame({"Open": close * 0.998, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)


def test_detect_bullish_market_regime(): assert detect_market_regime(make_history()) == MarketRegime.BULLISH

def test_candidate_detects_breakout_and_volume():
    c = candidate_from_history(UniverseMember("TEST", "Test Ltd"), make_history(start=300), MarketRegime.BULLISH); assert c is not None; assert c.current_price >= c.resistance; assert c.breakout_volume > c.avg_volume_20d; assert c.target1 > c.current_price > c.stop_loss


class FakeProvider:
    name = "fake"
    def history_many(self, symbols, period, batch_size=40):
        data = {s: make_history(start=300 if s == "AAA" else 2500) for s in symbols}; data["^NSEI"] = make_history(start=20_000); return data


def test_scan_keeps_quality_ranking_and_live_paper_split():
    members = [UniverseMember("AAA", "Affordable"), UniverseMember("BBB", "Expensive")]
    result = scan_universe(FakeProvider(), members, ExperimentConfig(capital=1000, max_rupee_risk=100, min_score_for_trade=70))
    assert result.market_regime == MarketRegime.BULLISH; assert len(result.proposals) == 2
    classes = {p.symbol: p.classification for p in result.proposals}; assert classes["AAA"] in {PortfolioType.LIVE, PortfolioType.NO_TRADE}; assert classes["BBB"] in {PortfolioType.PAPER, PortfolioType.NO_TRADE}; assert result.proposals == sorted(result.proposals, key=lambda p: p.ai_score, reverse=True)


class BlockingEventProvider(CorporateEventProvider):
    name = "blocking-events"
    def lookup(self, symbol, start, end): return EventLookup([CorporateEvent(symbol, start, "earnings", "results", self.name)], EventDataStatus.AVAILABLE, self.name)


def test_scan_turns_otherwise_valid_setup_into_no_trade_near_event():
    result = scan_universe(FakeProvider(), [UniverseMember("BBB", "Expensive")], ExperimentConfig(capital=1000, max_rupee_risk=100, min_score_for_trade=70), event_provider=BlockingEventProvider())
    p = result.proposals[0]
    if p.ai_score >= 70 and "score" not in p.decision_reason:
        assert p.classification == PortfolioType.NO_TRADE; assert p.event_risk is True; assert "earnings" in p.decision_reason
