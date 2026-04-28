# BTC/THB DCA Backtest Dashboard

> **🌐 Live demo:** https://karanyu.github.io/btc-dca-backtest/
>
> **⚠️ Educational only — not investment advice.**

A goal-driven Bitcoin DCA (Dollar Cost Averaging) planner with backtest-grounded
recommendations, computed daily from real Bitkub BTC/THB prices.

## Features

- 📅 **DCA วันนี้** — daily verdict (buy / hold / cool down) based on current Mayer Multiple
- 🎯 **เป้าหมายของฉัน** — multi-goal tracker with 3 calculator modes:
  - Target BTC + deadline → required ฿/day
  - Budget + deadline → projected BTC
  - Target + budget → days to goal
- 📊 **เปรียบเทียบกลยุทธ์** — link to a goal, get the best strategy ranked
- 📈 **การกระจาย Rolling** — distribution of outcomes across all start dates
- 🔍 **ตรวจสอบข้อมูล** — full audit trail of source + methodology
- 🔔 **Browser notifications** at user-chosen time

## Strategies Compared

| Strategy | Logic |
|---|---|
| **Flat DCA** | ฿1,000 / day, every day |
| **SMA-2x** | 2x when price < SMA(20W), else 1x |
| **Mayer Multiple** | <0.8 → 3x, <1.0 → 2x, >2.4 → 0.5x |
| **Bollinger 3-tier** | <BB-low → 3x, in band → 1.5x, >BB-up → 1x |
| **Lump Sum** | Invest entire budget on day 1 (benchmark only) |

## Architecture

```
┌─────────────────────────────────────────┐
│ GitHub Pages (https://...github.io)     │
│  ← daily auto-deploy via Actions        │
└─────────────────────────────────────────┘
              ▲
              │ uploads dist/
┌─────────────┴───────────────────────────┐
│ GitHub Actions (cron 02:00 UTC daily)    │
│  1. fetch from Bitkub API                │
│  2. validate (6 checks)                  │
│  3. run engine tests (11 invariants)     │
│  4. rebuild dashboard                    │
└─────────────────────────────────────────┘
```

## Repository Structure

```
btc-dca-backtest/
├── scripts/
│   ├── fetch_bitkub.py            Daily OHLC fetcher (with dedup)
│   ├── validate_data.py           Data quality validator
│   ├── data_loader.py             PriceSeries loader
│   ├── engine.py                  Pure DCA engine + 5 strategies
│   ├── metrics.py                 ROI/CAGR/MaxDD/Sortino/etc
│   ├── rolling.py                 Rolling-window distribution
│   ├── run_comparison.py          Markdown report generator
│   ├── build_dashboard.py         HTML dashboard builder
│   └── dashboard_template.html    UI template (CSS/JS in single file)
├── tests/
│   ├── test_data_integrity.py     9 data-integrity smoke tests
│   └── test_engine.py             11 engine invariant tests
├── data/
│   ├── btc_thb_daily.json         Cached daily OHLCV (1826 bars)
│   ├── data_quality_report.md     Auto-generated validation report
│   └── phase2_comparison_report.md Backtest comparison report
├── dist/
│   └── index.html                 Final shareable single-file dashboard
└── .github/workflows/
    └── daily-rebuild.yml          Daily auto-rebuild + Pages deploy
```

## Local Development

Requires Python 3.12+

```bash
git clone https://github.com/karanyu/btc-dca-backtest.git
cd btc-dca-backtest
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Refresh data
python scripts/fetch_bitkub.py

# Validate
python scripts/validate_data.py

# Run tests
python tests/test_engine.py

# Build dashboard
python scripts/build_dashboard.py

# Open
open dist/index.html
```

## Methodology

- **Data source:** Bitkub Public TradingView API (`/tradingview/history`)
- **Coverage:** 5 years of daily BTC/THB closes
- **Fee:** 0.25% per trade (Bitkub spot rate)
- **Validation:** Monotonic dates, no gaps, h≥l, no extreme moves >30%
- **Invariants:** Unit-tested — BTC accumulation strictly non-decreasing, fee accounting exact

## Disclaimers

- Past performance does **NOT** guarantee future returns
- This dashboard is for **education only** — NOT investment advice
- Bitcoin is a volatile, speculative asset. Only invest what you can afford to lose.
- The author makes no representations about the accuracy, completeness, or fitness of any
  information for any purpose. Use at your own risk.

## License

[MIT](LICENSE) — fork it, modify it, share it.
