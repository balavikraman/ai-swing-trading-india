# Stock Analyzer v0.1 — Local UI Prototype

This first build is intentionally **demo-data only**. Its purpose is to review the report UX before wiring real fundamentals, current news, Zerodha holdings and PostgreSQL.

## Run on Windows

1. Install Python 3.12 or newer.
2. Double-click `setup.bat` once.
3. Double-click `Stock Analyzer.bat` whenever you want to run it.
4. The browser opens at `http://127.0.0.1:8765`.

## Current build

- Polished stock-report overview
- Overall opportunity score
- Beginner-friendly metric explanations
- Entry / accumulate / strong-accumulate / hold / do-not-chase / profit zones
- Thesis-break rule
- 8-part scorecard
- 5-year annual financial presentation
- Quarterly trend presentation
- Current-news classification UI
- Bear/base/bull valuation presentation
- Responsive mobile/desktop layout
- FastAPI backend scaffold
- Service-module architecture for the real analyzer

## Next wiring order

1. PostgreSQL schema + migrations
2. Stock/security master
3. Real annual and quarterly financial ingestion
4. Valuation calculations
5. Technical/chart calculations
6. Company + international news research pipeline
7. Governance/value-trap checks
8. Zerodha read-only portfolio connection
9. Portfolio-fit / position sizing
10. Journal + historical validation/backtesting

## Important

Never put Zerodha passwords/PIN in this app. Only Kite API credentials belong in `.env`, and `.env` must never be committed to GitHub.
