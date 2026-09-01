import os
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .backtest import BacktestCostModel, backtest_symbol
from .benchmarks import benchmark_snapshot
from .broker import ZerodhaReadOnlyClient
from .engine import build_trade_proposal, score_candidate
from .intelligence_store import latest_market_context, list_intelligence
from .journal import JournalService
from .market_data import YFinanceMarketDataProvider
from .models import CandidateInput, ExperimentConfig, OutcomeUpdate
from .outcomes import OutcomeTracker, SimulationConfig, list_simulations, simulation_summary
from .performance import performance_from_simulation_rows
from .pipeline import env_bool, run_daily_pipeline

load_dotenv()

app = FastAPI(title="AI-Assisted Swing Trading India", version="0.5.0", description="Experiment-first market research platform. Human approval required; no auto-trading.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if item.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_journal() -> JournalService:
    return JournalService()


def simulation_config(entry=None, hold=None, period=None) -> SimulationConfig:
    return SimulationConfig(entry_valid_sessions=entry or int(os.getenv("OUTCOME_ENTRY_VALID_SESSIONS", "3")), max_holding_sessions=hold or int(os.getenv("OUTCOME_MAX_HOLDING_SESSIONS", "20")), history_period=period or os.getenv("OUTCOME_HISTORY_PERIOD", "2y"))


@app.get("/health")
def health():
    journal_ok = False
    journal_error = None
    try:
        get_journal().ping()
        journal_ok = True
    except Exception as exc:
        journal_error = str(exc)
    broker = ZerodhaReadOnlyClient().status()
    return {"status": "ok" if journal_ok else "degraded", "mode": "research", "auto_trading": False, "journal_connected": journal_ok, "journal_error": journal_error, "zerodha": broker.__dict__, "openai_configured": bool(os.getenv("OPENAI_API_KEY")), "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))}


@app.post("/score")
def score(candidate: CandidateInput):
    total, components = score_candidate(candidate)
    return {"score": total, "components": components}


@app.post("/proposal")
def proposal(candidate: CandidateInput, capital: float = 1000, max_rupee_risk: float = 10):
    return build_trade_proposal(candidate, ExperimentConfig(capital=capital, max_rupee_risk=max_rupee_risk))


@app.post("/scan/nifty200")
@app.get("/scan/nifty200")
def scan_nifty200(capital: float = 1000, max_rupee_risk: float = 10, limit: int = Query(default=20, ge=1, le=200), event_days_before: int = Query(default=int(os.getenv("EVENT_DAYS_BEFORE", "3")), ge=0, le=30), event_days_after: int = Query(default=int(os.getenv("EVENT_DAYS_AFTER", "1")), ge=0, le=30), event_unknown_blocks_trade: bool = Query(default=env_bool("EVENT_UNKNOWN_BLOCKS_TRADE", True)), enrich_news: bool = True, send_telegram: bool = False):
    try:
        return run_daily_pipeline(get_journal(), capital, max_rupee_risk, limit, send_telegram, enrich_news, event_days_before, event_days_after, event_unknown_blocks_trade)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"scan unavailable: {exc}") from exc


@app.get("/journal/runs")
def journal_runs(limit: int = 30):
    try:
        return get_journal().list_runs(limit)
    except Exception as exc:
        raise HTTPException(503, f"journal unavailable: {exc}")


@app.get("/journal/signals")
def journal_signals(limit: int = 100, symbol: str | None = None, classification: str | None = None):
    try:
        return get_journal().list_signals(limit, symbol, classification)
    except Exception as exc:
        raise HTTPException(503, f"journal unavailable: {exc}")


@app.patch("/journal/signals/{signal_id}/outcome")
def update_outcome(signal_id: int, update: OutcomeUpdate):
    try:
        row = get_journal().update_outcome(signal_id, update)
        if row is None:
            raise HTTPException(404, "signal not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"journal unavailable: {exc}")


@app.get("/journal/comparison")
def journal_comparison():
    return get_journal().comparison_summary()


@app.post("/outcomes/refresh")
def refresh_outcomes(limit: int = Query(default=200, ge=1, le=1000), entry_valid_sessions: int = Query(default=3, ge=1, le=10), max_holding_sessions: int = Query(default=20, ge=1, le=60), history_period: str = Query(default="2y", pattern="^(3mo|6mo|1y|2y|5y|max)$")):
    try:
        return OutcomeTracker(get_journal(), YFinanceMarketDataProvider(), simulation_config(entry_valid_sessions, max_holding_sessions, history_period)).refresh(limit)
    except Exception as exc:
        raise HTTPException(503, f"outcome refresh unavailable: {exc}")


@app.get("/outcomes/simulations")
def simulations(limit: int = 100, classification: str | None = None, status: str | None = None):
    return list_simulations(get_journal(), limit, classification, status)


@app.get("/outcomes/summary")
def outcomes_summary():
    return simulation_summary(get_journal())


@app.get("/performance")
def performance():
    paper = list_simulations(get_journal(), 1000, "PAPER")
    live = list_simulations(get_journal(), 1000, "LIVE")
    return {"paper": performance_from_simulation_rows(paper), "live_simulated": performance_from_simulation_rows(live), "note": "Simulation performance is not actual broker execution and excludes taxes/slippage unless explicitly modeled in backtests."}


@app.get("/intelligence/latest")
def intelligence_latest(limit: int = 50):
    return list_intelligence(get_journal(), limit)


@app.get("/benchmarks/snapshot")
def benchmarks():
    return benchmark_snapshot(ZerodhaReadOnlyClient())


@app.get("/broker/status")
def broker_status():
    return ZerodhaReadOnlyClient().status().__dict__


@app.get("/broker/holdings")
def broker_holdings():
    try:
        return ZerodhaReadOnlyClient().holdings()
    except Exception as exc:
        raise HTTPException(503, f"Zerodha holdings unavailable: {exc}")


@app.get("/broker/positions")
def broker_positions():
    try:
        return ZerodhaReadOnlyClient().positions()
    except Exception as exc:
        raise HTTPException(503, f"Zerodha positions unavailable: {exc}")


@app.get("/backtest/{symbol}")
def backtest(symbol: str, period: str = Query(default="5y", pattern="^(1y|2y|5y|max)$"), max_holding_sessions: int = Query(default=20, ge=1, le=60), entry_valid_sessions: int = Query(default=3, ge=1, le=10)):
    try:
        return backtest_symbol(YFinanceMarketDataProvider(), symbol.strip().upper(), ExperimentConfig(), period, max_holding_sessions, entry_valid_sessions, BacktestCostModel.from_env())
    except Exception as exc:
        raise HTTPException(503, f"backtest unavailable: {exc}")


@app.get("/dashboard/overview")
def dashboard_overview():
    try:
        signals = get_journal().list_signals(30)
        intelligence = list_intelligence(get_journal(), 20)
        paper = list_simulations(get_journal(), 1000, "PAPER")
        live = list_simulations(get_journal(), 1000, "LIVE")
        return {"market_context": latest_market_context(get_journal()), "signals": signals, "intelligence": intelligence, "outcomes": simulation_summary(get_journal()), "performance": {"paper": performance_from_simulation_rows(paper), "live_simulated": performance_from_simulation_rows(live)}, "benchmarks": benchmark_snapshot(ZerodhaReadOnlyClient()), "broker": ZerodhaReadOnlyClient().status().__dict__, "configuration": {"capital": 1000, "max_live_positions": 1, "max_rupee_risk": 10, "min_score": 80, "min_rr": 2, "auto_trading": False}}
    except Exception as exc:
        raise HTTPException(503, f"dashboard unavailable: {exc}")
