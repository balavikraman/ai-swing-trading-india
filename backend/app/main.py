from fastapi import FastAPI, HTTPException

from .engine import score_candidate, build_trade_proposal
from .market_data import YFinanceMarketDataProvider
from .models import CandidateInput, ExperimentConfig
from .scanner import scan_universe
from .universe import load_nifty_200

app = FastAPI(
    title="AI-Assisted Swing Trading India",
    version="0.2.0",
    description="Experiment-first research API. Human approval required; no auto-trading.",
)


@app.get("/health")
def health():
    return {"status": "ok", "mode": "research", "auto_trading": False}


@app.post("/score")
def score(candidate: CandidateInput):
    total, components = score_candidate(candidate)
    return {"score": total, "components": components}


@app.post("/proposal")
def proposal(candidate: CandidateInput, capital: float = 1000, max_rupee_risk: float = 10):
    cfg = ExperimentConfig(capital=capital, max_rupee_risk=max_rupee_risk)
    return build_trade_proposal(candidate, cfg)


@app.get("/scan/nifty200")
def scan_nifty200(capital: float = 1000, max_rupee_risk: float = 10, limit: int = 20):
    try:
        members = load_nifty_200()
        cfg = ExperimentConfig(capital=capital, max_rupee_risk=max_rupee_risk)
        result = scan_universe(YFinanceMarketDataProvider(), members, cfg)
        ranked = result.proposals[: max(1, min(limit, 200))]
        return {
            "universe": "NIFTY_200",
            "market_regime": result.market_regime,
            "data_provider": "yfinance-research",
            "human_approval_required": True,
            "auto_trading": False,
            "count": len(ranked),
            "candidates": ranked,
            "skipped_count": len(result.skipped),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"scan unavailable: {exc}") from exc
