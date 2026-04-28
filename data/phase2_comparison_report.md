# Phase 2 — Backtest Comparison Report

**Data:** bitkub BTC/THB daily, 2021-04-29 → 2026-04-28 (1826 bars)  
**Fee:** 0.25% per trade  
**Base daily amount:** ฿1,000  

## Strategy descriptions

- **flat**: ฿1,000 / day, every day.
- **sma2x**: ฿1,000 / day; ฿2,000 when close < SMA(140 days, ≈20W).
- **mayer**: Mayer Multiple = close/SMA(200). <0.8 → 3x, <1.0 → 2x, >2.4 → 0.5x, else 1x.
- **bollinger3**: Bollinger(140, 2σ). Below lower → 3x, in band → 1.5x, above upper → 1x.
- **lumpsum**: invest the full equivalent flat-DCA budget on day 1, then nothing.

## Part 1 — Single-path runs

*Result if you happen to start DCA at the exact start of each window ending today.
Sensitive to start date — see Part 2 for distribution view.*

### 1y window — single-path (end of dataset)

| Strategy | Invested | Fees | BTC | Value | ROI | CAGR | MaxDD | Sortino | T-to-1BTC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| flat | ฿365,000 | ฿912 | 0.1218 | ฿303,687 | -16.80% | -16.81% | 23.3% | 21.39 | — |
| sma2x | ฿559,000 | ฿1,398 | 0.1956 | ฿487,386 | -12.81% | -12.82% | 19.4% | 25.56 | — |
| mayer | ฿635,000 | ฿1,588 | 0.2309 | ฿575,434 | -9.38% | -9.39% | 16.6% | 25.34 | — |
| bollinger3 | ฿605,500 | ฿1,514 | 0.2040 | ฿508,373 | -16.04% | -16.05% | 22.4% | 22.89 | — |
| lumpsum | ฿365,000 | ฿912 | 0.1148 | ฿286,040 | -21.63% | -21.65% | 50.6% | -0.56 | — |

### 3y window — single-path (end of dataset)

| Strategy | Invested | Fees | BTC | Value | ROI | CAGR | MaxDD | Sortino | T-to-1BTC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| flat | ฿1,095,000 | ฿2,738 | 0.5562 | ฿1,386,232 | +26.60% | +8.18% | 45.5% | 8.45 | — |
| sma2x | ฿1,500,000 | ฿3,750 | 0.7493 | ฿1,867,398 | +24.49% | +7.58% | 42.7% | 8.85 | — |
| mayer | ฿1,531,000 | ฿3,828 | 0.7638 | ฿1,903,697 | +24.34% | +7.54% | 41.1% | 8.87 | — |
| bollinger3 | ฿1,652,500 | ฿4,131 | 0.8304 | ฿2,069,744 | +25.25% | +7.80% | 43.7% | 8.48 | — |
| lumpsum | ฿1,095,000 | ฿2,738 | 1.0831 | ฿2,699,562 | +146.54% | +35.12% | 50.6% | 1.21 | — |

### 5y window — single-path (end of dataset)

| Strategy | Invested | Fees | BTC | Value | ROI | CAGR | MaxDD | Sortino | T-to-1BTC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| flat | ฿1,826,000 | ฿4,565 | 1.2828 | ฿3,197,206 | +75.09% | +11.86% | 48.5% | 4.80 | 1048d |
| sma2x | ฿2,613,000 | ฿6,532 | 1.9041 | ฿4,745,695 | +81.62% | +12.68% | 47.9% | 5.05 | 616d |
| mayer | ฿2,890,000 | ฿7,225 | 2.2434 | ฿5,591,308 | +93.47% | +14.11% | 47.9% | 5.17 | 542d |
| bollinger3 | ฿2,756,500 | ฿6,891 | 1.9801 | ฿4,935,154 | +79.04% | +12.36% | 48.0% | 5.09 | 637d |
| lumpsum | ฿1,826,000 | ฿4,565 | 1.0702 | ฿2,667,241 | +46.07% | +7.87% | 75.0% | 0.48 | — |

## Part 2 — Rolling-window analysis

*Distribution of outcomes across ALL possible start dates (step=7 days).
This is the statistically honest view of what to expect.*

### 1y window — rolling analysis (across all start dates)

| Strategy | N paths | ROI median | P10 | P90 | Prob profit | BTC median | MaxDD median |
|---|---:|---:|---:|---:|---:|---:|---:|
| flat | 209 | +20.79% | -34.83% | +64.30% | 67.5% | 0.2621 | 18.9% |
| sma2x | 209 | +23.80% | -32.80% | +68.01% | 67.5% | 0.3428 | 17.7% |
| mayer | 209 | +24.78% | -29.96% | +70.37% | 67.5% | 0.3365 | 18.3% |
| bollinger3 | 209 | +21.75% | -32.77% | +65.82% | 67.5% | 0.3767 | 17.4% |
| lumpsum | 209 | +33.44% | -49.98% | +144.56% | 60.8% | 0.2566 | 30.3% |

### 3y window — rolling analysis (across all start dates)

| Strategy | N paths | ROI median | P10 | P90 | Prob profit | BTC median | MaxDD median |
|---|---:|---:|---:|---:|---:|---:|---:|
| flat | 105 | +133.24% | +26.01% | +191.20% | 100.0% | 0.9099 | 31.1% |
| sma2x | 105 | +146.73% | +23.69% | +206.53% | 100.0% | 1.3624 | 30.4% |
| mayer | 105 | +158.69% | +23.62% | +226.43% | 100.0% | 1.6530 | 30.1% |
| bollinger3 | 105 | +142.92% | +24.67% | +202.11% | 100.0% | 1.4541 | 29.5% |
| lumpsum | 105 | +139.33% | +36.29% | +389.75% | 100.0% | 1.0304 | 58.6% |

### 5y: skipped (window length >= dataset)

## Key findings

1. **Methodology fix vs prior backtest:** numbers now derive from real
   daily Bitkub closes (not monthly averages), fees deducted at 0.25%,
   and BTC accumulation is provably monotonic (verified by unit tests).

2. **Single-path bias:** the '5-year ROI = +75%' figure depends on the
   exact start date. Part 2 shows the full distribution.

3. **Strategy ranking (from rolling 1y data):** see table above —
   compare median ROI and P10 (worst 10%) for risk-adjusted ranking.

## Reproducibility

```bash
cd ~/Projects/btc-dca-backtest
source .venv/bin/activate
python scripts/run_comparison.py
```

All numbers in this report trace to deterministic functions in
`scripts/engine.py` operating on `data/btc_thb_daily.json`.
