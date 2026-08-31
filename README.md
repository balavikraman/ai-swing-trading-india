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
- Nifty 200 universe loader
- Daily OHLCV market-data adapter using yfinance for research/testing
- Nifty market-regime filter
- EMA20 / DMA50 / DMA200 calculations
- 15-day resistance/consolidation breakout detection
- Volume confirmation and liquidity filter
- ATR-derived stop placement and 1:2 / 1:3 targets
- Relative-strength and volatility-quality inputs
- Trend/breakout/volume scoring model
- Position sizing and risk/reward engine
- LIVE vs PAPER eligibility logic
- **NO TRADE** gate
- Basic Next.js dashboard shell
- Deterministic unit tests for engine + scanner

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

### Run the live research scan
```text
GET /scan/nifty200?capital=1000&max_rupee_risk=10&limit=20
```

The endpoint downloads the current Nifty 200 constituent universe, obtains daily research data, determines the Nifty regime, builds rule-based candidates, scores them, and returns ranked LIVE/PAPER/NO_TRADE proposals. Ranking is based on setup quality rather than affordability so the ₹1,000 experiment can evaluate strategy quality separately from capital limitations.

`yfinance` is intentionally isolated behind a market-data provider interface. It is suitable here as a convenient research adapter, not an exchange-grade or broker execution feed. Later it can be replaced by Zerodha, Upstox, or another licensed source without changing the scanner logic.

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
This repository is for research/education and experiment tracking. It is not financial advice and does not promise profitable outcomes. Market-data quality, corporate actions, event filters, transaction costs, slippage, taxes, and survivorship bias must be addressed before treating backtest or live-shadow results as evidence of an edge.
