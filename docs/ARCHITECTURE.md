# Research Architecture — High-efficiency swing intelligence

The system is deliberately not a single black-box stock predictor. It is a layered evidence system designed to make falsifiable recommendations and learn from outcomes.

## 1. Deterministic market layer — every Nifty 200 stock
Runs first because it is fast, cheap and reproducible.

Inputs: daily OHLCV, EMA20, DMA50, DMA200, 5–15 session consolidation, confirmed breakout, opening-gap extension, volume vs 20-day average, ATR, liquidity/turnover, relative strength vs Nifty 50, Nifty regime, cross-sectional breadth, and industry leadership.

Hard vetoes: trend failure, no breakout, invalid consolidation, bad stop/R:R, bearish regime, excessive gap, illiquidity, known nearby event, or missing event data when the conservative policy is enabled.

## 2. Market intelligence layer — shortlist only
Runs only for the best LIVE/PAPER candidates to control latency and API cost.

The OpenAI Responses API is used with web search to collect current public evidence. The prompt asks for primary exchange/company filings and reputable financial journalism and returns structured sentiment, news risk, confidence, catalysts, risks, source references, and a bounded research-score adjustment.

The LLM cannot override the deterministic stop, position size, event veto or auto-place an order. A high-confidence critical news risk is surfaced as a review hold.

Future provider slots: NSE corporate filings feed, company IR/RSS, licensed newswire, economic calendar, RBI/SEBI releases, sector-specific feeds, credit-rating releases.

## 3. Portfolio/execution context
Zerodha Kite Connect is read-only in V1: profile, holdings, positions, margins and market snapshots. There are intentionally no order placement methods.

Both Nifty 50 and Nifty 200 live benchmark snapshots use Zerodha when credentials are configured. Historical benchmark adapters can later use Kite historical candles/official index data.

## 4. Experiment journal
Every deterministic scan is fingerprinted and persisted. Separate tables store market breadth, AI/news intelligence and simulated outcomes, preserving the original recommendation exactly as it existed when generated.

This prevents look-ahead contamination: later news, model changes or outcome data never rewrite the original signal.

## 5. Outcome and validation layer
Paper and simulated-LIVE signals are replayed from the next trading session. Entry is not chased beyond the entry zone. Same-day stop/target ambiguity is resolved pessimistically. Metrics include P&L, return, R, MAE/MFE, holding sessions, win rate, average winner/loser, profit factor, drawdown and losing streaks.

The backtest endpoint walk-forwards the deterministic core using only data available at each historical date. Configurable bps model transaction costs and slippage. Historical news/events are explicitly excluded until a timestamped archive is available; they must never be backfilled with present-day knowledge.

## 6. Improvement loop
Do not optimize weights after a handful of trades. Accumulate signals, separate in-sample/out-of-sample periods, run walk-forward tests, measure feature stability, and only promote a rule/model when it improves risk-adjusted OOS results after costs.

Candidate future features, added only with reliable timestamped data: sector relative strength, market breadth regimes, India VIX, delivery percentage, institutional flows, fundamentals/earnings revisions, valuation regime, corporate actions, order-book/credit events, macro rates/FX/commodities, and eventually calibrated ML probability models.

## Prediction target
The product should not claim “stock X will rise tomorrow.” A later ML model should estimate measurable outcomes such as `P(target before stop within 20 sessions)` and expected R, with probability calibration and abstention when confidence/data quality is insufficient.
