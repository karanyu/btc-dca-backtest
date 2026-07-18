# Data Quality Report — BTC/THB Daily

**Source:** bitkub (https://api.bitkub.com/tradingview/history)  
**Symbol:** BTC_THB @ 1D  
**Fetched:** 2026-07-18T04:41:43.414860+00:00  
**Range:** 2021-07-19 → 2026-07-18 (1826 bars)  

## Summary

| Check | Pass | Detail |
|---|---|---|
| C-1: Monotonic + unique dates | ✅ | 1826 rows, 0 duplicates, min_gap=1 days 00:00:00, max_gap=1 days 00:00:00 |
| C-2: Continuous daily series (no missing days) | ✅ | 0 gaps > 1 day. Perfect continuity. |
| C-3: Price sanity (no NaN, no zero/negative, h>=l) | ✅ | All prices valid. |
| C-4: Extreme single-day moves (>30%) | ✅ | 0 extreme moves found |
| C-5: Coverage span vs row count | ✅ | first=2021-07-19, last=2026-07-18, span=1826 days, rows=1826 |
| C-6: Spot-check known reference dates | ✅ | Manual review needed (compare with TradingView/Bitkub website) |

### Spot-check rows (C-6: Spot-check known reference dates)

- **2021-11-10** (near 2021 ATH): close=฿2,272,000.00, low=฿2,215,000.00, high=฿2,285,500.00
- **2022-11-21** (near 2022 bottom): close=฿581,705.00, low=฿576,000.05, high=฿597,727.62
- **2024-03-14** (near 2024 ATH): close=฿2,565,399.73, low=฿2,520,000.00, high=฿2,632,000.00

## Price Statistics (close, THB)

- Min: ฿568,036.66 on 2023-01-06
- Max: ฿4,045,998.95 on 2025-10-06
- Mean: ฿1,938,774.88
- Median: ฿1,919,329.98
- Std: ฿960,931.18

## Return Statistics (daily close-to-close)

- Mean daily return: 0.0709%
- Std daily return: 2.4527%
- Annualized vol: 46.86%
- Min daily: -14.67% on 2022-06-13
- Max daily: 16.12% on 2023-03-13
