from app.broker import ZerodhaReadOnlyClient
from app.intelligence import IntelligenceResult, OpenAIWebIntelligenceProvider, enrich_candidates
from app.notifications import TelegramNotifier, format_scan_alert


def test_unconfigured_integrations_fail_closed_without_network():
    zerodha = ZerodhaReadOnlyClient(api_key="", access_token="")
    assert zerodha.status().configured is False
    assert zerodha.status().read_only is True
    telegram = TelegramNotifier(token="", chat_id="")
    assert telegram.send("x")["sent"] is False
    openai = OpenAIWebIntelligenceProvider(api_key="")
    assert openai.analyze("INFY", "Infosys", 90, "technical", "market").configured is False


def test_intelligence_only_enriches_actionable_shortlist():
    class FakeProvider:
        def analyze(self, symbol, name, base_score, technical_reason, market_reason):
            return IntelligenceResult("fake", True, symbol, research_score=base_score + 1)

    rows = [
        {"symbol": "A", "name": "A", "classification": "NO_TRADE", "ai_score": 99},
        {"symbol": "B", "name": "B", "classification": "PAPER", "ai_score": 90, "technical_reason": "", "market_reason": ""},
    ]
    output = enrich_candidates(rows, FakeProvider(), limit=5)
    assert len(output) == 1
    assert output[0]["symbol"] == "B"


def test_alert_has_human_approval_warning():
    message = format_scan_alert(
        {"signal_date": "2026-08-31", "market_regime": "BULLISH", "market_context": {"breadth_score": 0.7}, "candidates": []}
    )
    assert "Human approval" in message
