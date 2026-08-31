# Experiment Protocol

## Initial live rules
- Capital: ₹1,000
- Max live positions: 1
- Suggested initial risk budget: 1% of capital (₹10), configurable
- Long-only delivery trades
- No leverage, F&O, intraday, averaging down
- Minimum planned R:R: 1:2
- No mandatory daily trade

## Signal log fields
Date, instrument, score, entry, stop, targets, quantity, setup, rationale, LIVE/PAPER, actual entry, actual exit, P/L, return %, MAE, MFE, holding period, stop hit, target hit, system-followed, violations, chart reference, expected-vs-actual notes.

## Evaluation gate before scaling
Do not scale from a few winners. Review at least 20–30 generated signals, including NO-TRADE periods, and compare LIVE vs PAPER results.

## Metrics
Win rate, average winner/loser, profit factor, average R:R, max drawdown, max consecutive losses, average holding period, total return, benchmark comparison, and—only when sample size is meaningful—CAGR/Sharpe.

## Future validation
Backtest 5–10 years where data permits with transaction costs, slippage, applicable charges/taxes, survivorship-bias awareness, in-sample/out-of-sample splits, and walk-forward testing.
