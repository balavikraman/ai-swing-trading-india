# AI-Assisted Swing Trading — India

Experiment-first swing-trading research application for Indian equities and ETFs.

## Principles
- Long-only delivery swing trades
- No leverage, F&O, averaging down, or blind AI predictions
- Human approval before any broker order
- LIVE portfolio capped by available capital; SHADOW portfolio tracks otherwise valid setups
- System can and should return **NO TRADE**
- Every trade has a predefined stop and target
- Initial capital: ₹1,000; initial max live positions: 1

## V1 architecture
Market data → technical scanner → candidate setups → rule-based score → risk engine → LIVE/PAPER classification → human approval → journal → review/backtest.

## Included now
- FastAPI API
- Trend/breakout/volume scoring model
- Position sizing and risk/reward engine
- LIVE vs PAPER eligibility logic
- “NO TRADE” gate
- Journal-ready trade schema
- Basic Next.js dashboard shell
- Unit tests for scoring and risk calculations

## Run backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open: http://127.0.0.1:8000/docs

## Run tests
```bash
cd backend
pytest -q
```

## Run frontend
```bash
cd frontend
npm install
npm run dev
```

## Important
This repository is for research/education and experiment tracking. It is not financial advice and does not promise profitable outcomes.
