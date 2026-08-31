import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query

from .engine import build_trade_proposal, score_candidate
from .events import build_event_provider_from_env
from .journal import JournalService
from .market_data import YFinanceMarketDataProvider
from .models import CandidateInput, ExperimentConfig, OutcomeUpdate
from .scanner import scan_universe
from .universe import load_nifty_200

app = FastAPI(title="AI-Assisted Swing Trading India", version="0.3.0", description="Experiment-first research API. Human approval required; no auto-trading.")


@lru_cache(maxsize=1)
def get_journal() -> JournalService: return JournalService()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None: return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@app.get("/health")
def health():
    journal_ok=False; journal_error=None
    try: get_journal().ping(); journal_ok=True
    except Exception as exc: journal_error=str(exc)
    return {"status":"ok" if journal_ok else "degraded","mode":"research","auto_trading":False,"journal_connected":journal_ok,"journal_error":journal_error}


@app.post("/score")
def score(candidate: CandidateInput):
    total,components=score_candidate(candidate); return {"score":total,"components":components}


@app.post("/proposal")
def proposal(candidate: CandidateInput, capital: float=1000, max_rupee_risk: float=10):
    return build_trade_proposal(candidate,ExperimentConfig(capital=capital,max_rupee_risk=max_rupee_risk))


@app.get("/scan/nifty200")
def scan_nifty200(capital: float=1000, max_rupee_risk: float=10, limit: int=20,
                  event_days_before: int=Query(default=int(os.getenv("EVENT_DAYS_BEFORE","3")),ge=0,le=30),
                  event_days_after: int=Query(default=int(os.getenv("EVENT_DAYS_AFTER","1")),ge=0,le=30),
                  event_unknown_blocks_trade: bool=Query(default=_env_bool("EVENT_UNKNOWN_BLOCKS_TRADE",True))):
    try:
        members=load_nifty_200(); cfg=ExperimentConfig(capital=capital,max_rupee_risk=max_rupee_risk,event_days_before=event_days_before,event_days_after=event_days_after,event_unknown_blocks_trade=event_unknown_blocks_trade)
        market_provider=YFinanceMarketDataProvider(); event_provider=build_event_provider_from_env(); result=scan_universe(market_provider,members,cfg,event_provider=event_provider)
        run_id=None; journal_saved=False; journal_error=None
        try: run_id,journal_saved=get_journal().save_scan(result,"NIFTY_200",market_provider.name,event_provider.name,cfg)
        except Exception as exc:
            journal_error=str(exc)
            if _env_bool("JOURNAL_REQUIRED",True): raise RuntimeError(f"scanner results were not journaled: {exc}") from exc
        ranked=result.proposals[:max(1,min(limit,200))]
        return {"universe":"NIFTY_200","signal_date":result.signal_date,"market_regime":result.market_regime,"data_provider":market_provider.name,"event_provider":event_provider.name,"human_approval_required":True,"auto_trading":False,"journal_run_id":run_id,"journal_saved_new_snapshot":journal_saved,"journal_error":journal_error,"count":len(ranked),"total_evaluated":len(result.proposals),"candidates":ranked,"skipped_count":len(result.skipped)}
    except Exception as exc: raise HTTPException(status_code=503,detail=f"scan unavailable: {exc}") from exc


@app.get("/journal/runs")
def journal_runs(limit: int=30):
    try: return get_journal().list_runs(limit)
    except Exception as exc: raise HTTPException(status_code=503,detail=f"journal unavailable: {exc}") from exc


@app.get("/journal/signals")
def journal_signals(limit: int=100, symbol: str | None=None, classification: str | None=None):
    try: return get_journal().list_signals(limit,symbol,classification)
    except Exception as exc: raise HTTPException(status_code=503,detail=f"journal unavailable: {exc}") from exc


@app.patch("/journal/signals/{signal_id}/outcome")
def update_signal_outcome(signal_id: int, update: OutcomeUpdate):
    try:
        result=get_journal().update_outcome(signal_id,update)
        if result is None: raise HTTPException(status_code=404,detail="signal not found")
        return result
    except HTTPException: raise
    except Exception as exc: raise HTTPException(status_code=503,detail=f"journal unavailable: {exc}") from exc


@app.get("/journal/comparison")
def journal_comparison():
    try: return get_journal().comparison_summary()
    except Exception as exc: raise HTTPException(status_code=503,detail=f"journal unavailable: {exc}") from exc
