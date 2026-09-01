from __future__ import annotations

import os

from .benchmarks import benchmark_snapshot
from .broker import ZerodhaReadOnlyClient
from .events import build_event_provider_from_env
from .intelligence import OpenAIWebIntelligenceProvider, enrich_candidates
from .intelligence_store import save_intelligence, save_market_context
from .journal import JournalService
from .market_data import YFinanceMarketDataProvider
from .models import ExperimentConfig
from .notifications import TelegramNotifier, format_scan_alert
from .outcomes import OutcomeTracker, SimulationConfig
from .scanner import scan_universe
from .universe import load_nifty_200


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def simulation_config() -> SimulationConfig:
    return SimulationConfig(
        entry_valid_sessions=int(os.getenv("OUTCOME_ENTRY_VALID_SESSIONS", "3")),
        max_holding_sessions=int(os.getenv("OUTCOME_MAX_HOLDING_SESSIONS", "20")),
        history_period=os.getenv("OUTCOME_HISTORY_PERIOD", "2y"),
    )


def run_daily_pipeline(
    journal: JournalService | None = None,
    capital: float = 1000,
    max_rupee_risk: float = 10,
    limit: int = 20,
    send_telegram: bool = False,
    enrich_news: bool = True,
    event_days_before: int | None = None,
    event_days_after: int | None = None,
    event_unknown_blocks_trade: bool | None = None,
) -> dict:
    journal = journal or JournalService()
    members = load_nifty_200()
    cfg = ExperimentConfig(
        capital=capital,
        max_rupee_risk=max_rupee_risk,
        event_days_before=event_days_before if event_days_before is not None else int(os.getenv("EVENT_DAYS_BEFORE", "3")),
        event_days_after=event_days_after if event_days_after is not None else int(os.getenv("EVENT_DAYS_AFTER", "1")),
        event_unknown_blocks_trade=event_unknown_blocks_trade if event_unknown_blocks_trade is not None else env_bool("EVENT_UNKNOWN_BLOCKS_TRADE", True),
    )
    market = YFinanceMarketDataProvider()
    events = build_event_provider_from_env()
    result = scan_universe(market, members, cfg, event_provider=events)
    run_id, created = journal.save_scan(result, "NIFTY_200", market.name, events.name, cfg)
    save_market_context(journal, run_id, result.market_context)

    outcome_refresh = None
    if env_bool("AUTO_REFRESH_OUTCOMES", True):
        try:
            outcome_refresh = OutcomeTracker(journal, market, simulation_config()).refresh(limit=int(os.getenv("OUTCOME_REFRESH_LIMIT", "200")))
        except Exception as exc:
            outcome_refresh = {"error": str(exc), "non_fatal": True}

    candidates = [proposal.model_dump(mode="json") for proposal in result.proposals]
    intelligence = []
    intelligence_saved = 0
    if enrich_news:
        intelligence = enrich_candidates(candidates, OpenAIWebIntelligenceProvider(), limit=int(os.getenv("INTELLIGENCE_SHORTLIST", "10")))
        if intelligence:
            intelligence_saved = save_intelligence(journal, run_id, intelligence)

    payload = {
        "universe": "NIFTY_200",
        "signal_date": result.signal_date.isoformat() if result.signal_date else None,
        "market_regime": result.market_regime.value,
        "market_context": result.market_context,
        "data_provider": market.name,
        "event_provider": events.name,
        "human_approval_required": True,
        "auto_trading": False,
        "journal_run_id": run_id,
        "journal_saved_new_snapshot": created,
        "outcome_refresh": outcome_refresh,
        "intelligence": intelligence,
        "intelligence_saved": intelligence_saved,
        "benchmarks": benchmark_snapshot(ZerodhaReadOnlyClient()),
        "count": len(candidates[: max(1, min(limit, 200))]),
        "total_evaluated": len(candidates),
        "candidates": candidates[: max(1, min(limit, 200))],
        "skipped_count": len(result.skipped),
    }
    if send_telegram:
        payload["telegram"] = TelegramNotifier().send(format_scan_alert(payload))
    return payload
