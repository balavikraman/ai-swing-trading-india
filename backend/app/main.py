from fastapi import FastAPI
from .models import CandidateInput, ExperimentConfig
from .engine import score_candidate, build_trade_proposal

app = FastAPI(
    title="AI-Assisted Swing Trading India",
    version="0.1.0",
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
