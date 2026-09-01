# AI-Assisted Swing Trading — India

Local-first research platform for long-only Indian equity/ETF swing trading. The product is designed to test whether a repeatable edge exists; it does **not** promise profits and it does not auto-trade.

## Current architecture
**Nifty 200 daily data → strict technical scanner → market breadth / relative strength → earnings-event veto → LIVE/PAPER/NO_TRADE → PostgreSQL journal → current-news intelligence for shortlist → simulated outcome tracking → performance/backtest → dashboard / Telegram → human decision.**

Read `docs/ARCHITECTURE.md` for the feature/data architecture and future ML path.

## Implemented
- Strict long-only Nifty 200 breakout scanner with hard trend/consolidation/breakout gates.
- Opening-gap, volume, ATR stop, minimum R:R and turnover/liquidity checks.
- Relative strength against Nifty 50; Nifty 200 breadth and industry leadership.
- Earnings/company-event exclusion with conservative missing-data policy.
- PostgreSQL journal with idempotent snapshots and automatic PAPER/simulated-LIVE outcome tracking.
- Performance metrics including profit factor, average R, drawdown and losing streaks.
- Walk-forward technical-core backtest with configurable transaction-cost/slippage bps.
- OpenAI current-web intelligence adapter for the top shortlist only. It cannot override deterministic risk rules.
- Zerodha Kite **read-only** client; no order-placement methods exist in V1.
- Nifty 50 + Nifty 200 live benchmark snapshot path through Zerodha.
- Telegram notification adapter, local Windows post-market runner, and polished Next.js dashboard.

## Start locally on Windows
```powershell
# database
docker compose up -d postgres

# backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# separate terminal: frontend
cd frontend
npm install
npm run dev
```
API docs: `http://127.0.0.1:8000/docs` · Dashboard: `http://localhost:3000`

## Main API routes
```text
GET/POST /scan/nifty200
GET      /dashboard/overview
GET      /performance
GET      /backtest/{symbol}
POST     /outcomes/refresh
GET      /outcomes/simulations
GET      /outcomes/summary
GET      /intelligence/latest
GET      /benchmarks/snapshot
GET      /broker/status
GET      /broker/holdings
GET      /broker/positions
GET      /journal/runs
GET      /journal/signals
PATCH    /journal/signals/{signal_id}/outcome
```

## Automatic weekday scan
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_task.ps1 -ProjectRoot "C:\path\to\ai-swing-trading-india"
```
Default task time is 4:15 PM Monday–Friday. It scans, journals, refreshes outcomes, runs news enrichment when configured, and sends Telegram when configured. It **does not place broker orders**.

## Dependencies you can provide later
Nothing here blocks continued local development. Optional features activate when configured in `.env`:
1. Zerodha Kite Connect: `KITE_API_KEY` and current `KITE_ACCESS_TOKEN` for read-only broker/benchmark data.
2. OpenAI API: `OPENAI_API_KEY` for sourced current-news intelligence. Keep it server-side only.
3. Telegram: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.
4. A licensed/official timestamped historical news/event source is still needed before news/event features can be honestly historical-backtested without look-ahead bias.

Never commit secrets to GitHub. `.env` is gitignored.

## Backtesting warning
The current backtest tests the deterministic technical core walk-forward. It deliberately does not pretend to know historical news/earnings when a timestamped archive is unavailable. Cost/slippage bps are configurable approximations and should later be calibrated against actual Zerodha contract notes.

## Research rules
Initial live capital ₹1,000; maximum one live position; ₹10 max planned risk; minimum score 80; minimum R:R 1:2; delivery only; no leverage; no F&O; no averaging down; human approval required. Scale only after enough clean out-of-sample evidence.
