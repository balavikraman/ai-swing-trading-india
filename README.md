# AI-Assisted Swing Trading — India

Experiment-first swing-trading research application for Indian equities and ETFs.

## Principles
- Long-only delivery swing trades
- No leverage, F&O, averaging down, or blind AI predictions
- Human approval before any broker order
- LIVE portfolio capped by available capital; SHADOW/PAPER portfolio tracks otherwise valid setups
- System can and should return **NO TRADE**
- Every trade has a predefined stop and target
- Initial capital: ₹1,000; initial max live positions: 1

## V1 architecture
Market data → technical scanner → event filter → rule-based score → risk engine → LIVE/PAPER/NO_TRADE → PostgreSQL journal → human review → outcome comparison.

## Included now
- FastAPI API and Nifty 200 daily scanner
- Configurable earnings/company-event exclusion window
- Conservative block when event data is unavailable (configurable)
- Manual corporate-event CSV fallback plus yfinance research event adapter
- PostgreSQL/SQLAlchemy experiment journal
- Automatic idempotent persistence of every evaluated recommendation in each scan snapshot
- Outcome review fields: actual entry/exit, P&L, return, realized R, MAE/MFE, stop/target flags, rule violations, chart reference and decision-quality label
- Basic predicted-decision vs reviewed-outcome comparison endpoint
- Human approval remains required; no broker auto-trading

## Start PostgreSQL
```bash
docker compose up -d postgres
```
Default database URL: `postgresql+psycopg://swing:swing@localhost:5432/swing_trading`

Copy `.env.example` values into your environment as needed. Journal persistence is required by default so experiment signals are not silently lost.

## Corporate event filter
Default policy: avoid new entries 3 business days before and 1 business day after a known results/company-event date. If automatic event data is unavailable, an otherwise actionable trade is blocked by default. The V1 business-day window is a Monday–Friday approximation; use an NSE holiday-aware exchange calendar before production use.

`EVENT_PROVIDER` modes: `composite` (default), `manual`, `yfinance`, or `disabled`.

For manual verified dates, copy `backend/data/corporate_events.example.csv` to `backend/data/corporate_events.csv` and replace examples with verified dates. The real local calendar is gitignored.

## Run backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open API docs: `http://127.0.0.1:8000/docs`

## Scan and auto-journal
```text
GET /scan/nifty200?capital=1000&max_rupee_risk=10&limit=20&event_days_before=3&event_days_after=1&event_unknown_blocks_trade=true
```
Every evaluated proposal is persisted before the response is considered successful when `JOURNAL_REQUIRED=true`. Exact repeated snapshots are deduplicated by fingerprint to prevent double counting.

## Journal API
```text
GET   /journal/runs
GET   /journal/signals
PATCH /journal/signals/{signal_id}/outcome
GET   /journal/comparison
```
The outcome endpoint stores actual execution/outcome data and computes realized P&L, percentage return, R multiple and holding period. `decision_was_correct` is an explicit post-trade review label, not an AI probability or guaranteed-performance metric.

## Run tests
```bash
cd backend
pytest -q
```
The suite covers the engine, scanner, event blocking and journal persistence/outcome calculations.

## Important
This repository is for research/education and experiment tracking. It is not financial advice and does not promise profitable outcomes. `yfinance` remains a research adapter, not an exchange-grade execution feed. Transaction costs, slippage, taxes/charges, corporate actions, survivorship bias and better event-data quality must be included before treating results as evidence of a repeatable edge.
