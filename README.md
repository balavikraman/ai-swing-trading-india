# AI-Assisted Swing Trading — India

Experiment-first swing-trading research application for Indian equities and ETFs.

## Principles
- Long-only delivery swing trades
- No leverage, F&O, averaging down, or blind AI predictions
- Human approval before any broker order
- LIVE portfolio capped by available capital; SHADOW/PAPER tracks otherwise valid setups
- The system can and should return **NO TRADE**
- Initial experiment capital: ₹1,000

## Current pipeline
Market data → Nifty 200 scanner → earnings/event filter → deterministic score/risk engine → LIVE/PAPER/NO_TRADE → PostgreSQL journal → automatic simulated outcome tracking → human review.

## Implemented
- FastAPI backend and Nifty 200 daily scanner
- EMA20 / DMA50 / DMA200 trend filter, consolidation breakout, volume, liquidity, ATR stop and targets
- Configurable earnings/company-event exclusion with manual CSV fallback
- PostgreSQL/SQLAlchemy experiment journal with idempotent scan snapshots
- Automatic tracking for saved LIVE/PAPER signals using subsequent daily OHLC data
- Simulated entry, stop, Target 1, time exit, MAE, MFE, R multiple, holding sessions and P&L
- PAPER and simulated-LIVE summary metrics
- Manual actual-trade outcome fields remain separate from simulated results
- No broker auto-trading

## PostgreSQL
```bash
docker compose up -d postgres
```
Default URL: `postgresql+psycopg://swing:swing@localhost:5432/swing_trading`

## Run backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000/docs`.

## Daily scan
```text
GET /scan/nifty200?capital=1000&max_rupee_risk=10&limit=20
```
The scan journals the full evaluated snapshot. With `AUTO_REFRESH_OUTCOMES=true` it also refreshes older non-terminal LIVE/PAPER simulations in the same request.

## Automatic outcome model
Defaults are configurable in `.env.example`:
- Entry is considered only from the first session after the signal, avoiding same-close lookahead.
- Entry zone remains valid for 3 post-signal sessions.
- If price gaps above the entry zone and never trades back into it, the system does not chase.
- Target 1 is the deterministic full simulated exit because no partial-exit rule has been defined yet.
- Maximum holding period is 20 trading sessions; otherwise exit at that session's close.
- If a daily candle touches both stop and target, stop is assumed first (pessimistic handling of unknown intraday order).
- An intraday-triggered entry receives no same-bar target credit.
- Simulated outcomes never overwrite manually entered actual LIVE fills.

Simulation statuses include `PENDING_ENTRY`, `OPEN`, `TARGET1`, `STOPPED`, `TIME_EXIT`, `ENTRY_EXPIRED`, and `NO_DATA`.

## Outcome API
```text
POST /outcomes/refresh
GET  /outcomes/simulations?classification=PAPER
GET  /outcomes/summary
```
`/outcomes/summary` reports tracked/closed/open counts, entry expiries, wins/losses, win rate, simulated P&L, average return, average R and profit factor separately for PAPER and simulated LIVE signals.

Existing journal endpoints remain available:
```text
GET   /journal/runs
GET   /journal/signals
PATCH /journal/signals/{signal_id}/outcome
GET   /journal/comparison
```

## Tests
```bash
cd backend
pytest -q
```
Outcome tests cover next-session fills, no-chase entry expiry, pessimistic same-bar handling, time exits, persistence and paper summary calculations.

## Important
This is research/education software, not financial advice and not a promise of profit. The automatic results are daily-bar simulations, not actual broker fills. yfinance is still a research adapter. Transaction costs, slippage, taxes/charges, corporate actions, exchange holiday calendars and licensed market/event data should be incorporated before treating results as evidence of a repeatable edge.
