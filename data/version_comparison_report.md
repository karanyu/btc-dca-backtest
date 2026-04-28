# รายงานเปรียบเทียบ — BTC DCA Backtest Version เก่า vs ใหม่

**วันที่:** 28 เม.ย. 2569
**ผู้จัดทำ:** Claude (Audit + Rebuild)
**Old version:** React artifact (`https://claude.ai/public/artifacts/cc6c8bca-...`)
**New version:** `~/Projects/btc-dca-backtest/` (Phase 1-3)

---

## 1. Executive Summary

| มิติ | Version เก่า | Version ใหม่ | ผลลัพธ์ |
|---|---|---|---|
| **Data correctness** | ❌ มี bug | ✅ ผ่าน 6/6 checks | **แก้ได้** |
| **Methodology** | ⚠️ Monthly avg | ✅ Daily real | **ตรงขึ้น** |
| **Reproducibility** | ❌ Hardcoded | ✅ Algorithm | **Audit ได้** |
| **Coverage** | 1 กลยุทธ์ | 5 กลยุทธ์ | **+4 strategies** |
| **Statistical view** | ❌ Single path | ✅ Rolling 209+105 | **+robustness** |
| **Sharability** | Claude.ai เท่านั้น | Single HTML | **portable** |

---

## 2. Side-by-side Comparison

### 2.1 Data Layer

| ประเด็น | เก่า | ใหม่ |
|---|---|---|
| Data source | CoinLore Monthly OHLC | Bitkub Daily TradingView |
| Granularity | รายเดือน (1 จุด/เดือน) | รายวัน (1 จุด/วัน) |
| Currency conversion | USD × FX "โดยประมาณ" | THB native (ตรงกับที่ trade จริง) |
| Time range | ก.ค. 2564 – เม.ย. 2569 | 29 เม.ย. 2564 – 28 เม.ย. 2569 |
| Total data points | ~60 monthly bars | **1,826 daily bars** |
| Validation checks | ❌ ไม่มี | ✅ 6 automated checks |
| Duplicate handling | ❌ ไม่ตรวจ | ✅ Detected & deduped 3 dates |
| Spot-check vs reality | ❌ ไม่มี | ✅ ATH/bottom dates ตรงประวัติ |

### 2.2 Backtest Engine

| ประเด็น | เก่า | ใหม่ |
|---|---|---|
| Logic location | ❌ ไม่มีในโค้ด | ✅ `scripts/engine.py` (162 lines) |
| Implementation | Hardcoded numbers ใน JSX | Pure functions, deterministic |
| Buy execution | "ราคาเฉลี่ยรายเดือน" | Daily close price |
| Fee handling | ❌ ไม่หัก | ✅ 0.25% (Bitkub spot) |
| Slippage | ❌ ไม่คิด | ✅ Conservative (เพราะ DCA เล็ก) |
| Unit tests | ❌ ไม่มี | ✅ 11 tests (BTC monotonic, fee correct, etc.) |
| Strategies supported | 2 (flat, sma2x) | **5** (+mayer, +bollinger3, +lumpsum) |

### 2.3 Statistical Analysis

| ประเด็น | เก่า | ใหม่ |
|---|---|---|
| Number of paths analyzed | 1 | 209 (1y) + 105 (3y) = **314 paths** |
| Distribution view | ❌ | ✅ P10/P25/Median/P75/P90 + histogram |
| Probability of profit | ❌ | ✅ คำนวณ % paths ที่กำไร |
| Single-start-date bias | ⚠️ Yes | ✅ Eliminated |
| Sortino ratio | ❌ | ✅ Computed |
| Max Drawdown | ⚠️ จากตัวเลข hardcoded | ✅ จาก equity curve จริง |
| Time-to-1BTC | ❌ ไม่มี | ✅ Computed per strategy |

### 2.4 User Interface

| ประเด็น | เก่า | ใหม่ |
|---|---|---|
| Platform | React artifact (claude.ai) | Single HTML file |
| Dependencies | recharts in claude.ai env | Chart.js from CDN |
| Sharability | ต้อง share Claude link | Portable file (252 KB) |
| Strategy comparison | ❌ ไม่ได้ | ✅ Multi-strategy overlay |
| Equity curve | Single line | **5 strategies overlaid** |
| Drawdown chart | ❌ | ✅ Per strategy |
| Tabs | 3 (window-based) | 3 (compare/rolling/audit) |
| Audit trail | ❌ | ✅ Full disclosure tab |

---

## 3. Critical Bugs Found in Old Version

### Bug #1 — BTC ลดลงผิดธรรมชาติ 🔴

**Evidence:**
```
3y, มี.ค. → เม.ย. 69:
  มี.ค.: BTC = 0.55285, cumInv = 1,072,000
  เม.ย.: BTC = 0.55285, cumInv = 1,097,000  ← ลงทุน +25,000 ฿ แต่ BTC ไม่เพิ่ม

5y, มี.ค. → เม.ย. 69:
  มี.ค.: BTC = 1.28222
  เม.ย.: BTC = 1.26876  ← BTC ลดลง 0.01346 ทั้งที่ DCA ห้ามขาย
```

**Root cause:** ค่า `final BTC` ถูก hardcode ก่อน แล้วตัวเลขรายเดือนถูก fit ตาม → ไม่ผ่าน algorithm จริง

**ผลกระทบ:** ตัวเลขทั้ง report ไม่น่าเชื่อถือเชิงเทคนิค

**Fix in new version:** Unit test `test_btc_monotonic_increasing` enforce ทุก strategy

### Bug #2 — Methodology Distortion 🟡

**Evidence:** Footer ของเก่า: *"CoinLore Monthly OHLC + USD/THB โดยประมาณ"*

**ผลกระทบ:**
- ทุกวันใน "เม.ย. 2569" ถูกสมมติว่าซื้อที่ 2,446,769 ฿ ทั้ง 25 วัน
- ทำลายข้อได้เปรียบหลักของ DCA (ซื้อได้ BTC เยอะตอนวันที่ราคาต่ำ)
- พฤติกรรมเหมือน "lump sum รายเดือน" มากกว่า "DCA รายวัน"

**Fix:** ใช้ daily close ของ Bitkub โดยตรง

### Bug #3 — Hidden Cost ที่ไม่หัก 🟡

**Evidence:** ไม่มี fee deduction ใน hardcoded values

**ผลกระทบใน 5y:** ขาดต้นทุน ~฿4,565 (Flat) ถึง ~฿7,225 (Mayer) ในตัวเลข ROI

**Fix:** หัก 0.25% ทุก trade แสดงเปิดเผยใน column

---

## 4. Number-by-Number Diff (Same Strategy, Same Window)

### Flat DCA, 5 ปี

| Metric | เก่า อ้าง | ใหม่ ของจริง | Δ | คำอธิบาย |
|---|---|---|---|---|
| Total invested | ฿1,827,000 | ฿1,826,000 | −฿1,000 | 1826 vs 1827 days (5 ปีพอดี) |
| Total fees | ❌ ไม่หัก | ฿4,565 | +฿4,565 | New: หักจริง 0.25% |
| Final BTC | 1.2688 | **1.2828** | +0.0140 | Daily DCA ได้ low แม่นกว่า monthly |
| Final value | ฿3,199,682 | ฿3,197,206 | −฿2,476 | Reflect actual daily close |
| ROI | +75.13% | **+75.09%** | −0.04% | เกือบเหมือนกัน (ดีอย่างน่าประหลาด) |
| Max Drawdown | ❌ ไม่มี | 48.5% | new | Computed from equity curve |
| Time-to-1BTC | ❌ ไม่มี | 1,048 วัน | new | Computed |

### SMA-2x, 5 ปี

| Metric | เก่า อ้าง | ใหม่ ของจริง | Δ | คำอธิบาย |
|---|---|---|---|---|
| Total invested | ฿2,721,000 | ฿2,613,000 | −฿108,000 | Different threshold trigger frequency |
| Final BTC | 1.9668 | **1.9041** | −0.0627 | Closer to truth, daily-precision |
| ROI | +82.28% | **+81.62%** | −0.66% | Lower เพราะหักค่าธรรมเนียม |

**ข้อสังเกต:** ทิศทางทั้งหมดถูก แต่ **ตัวเลขเฉพาะจุดเชื่อไม่ได้** ใน version เก่า

---

## 5. New Capabilities (ไม่มีใน version เก่า)

### 5.1 Mayer Multiple Strategy ⭐
- **กลยุทธ์ที่ดีที่สุดในการ backtest** จากผลใหม่
- 5y ROI: **+93.47%** (vs Flat 75.09%)
- Time-to-1BTC: **542 วัน** (vs Flat 1048 วัน — เร็วกว่า 506 วัน)
- Rolling 3y median ROI: +158.69% (best of all)

### 5.2 Lump-sum Comparison (Wake-up call)
- 5y ROI: **+46.07%** (ตอนเริ่มผิดเวลา)
- MaxDD: **75.0%** (DCA แค่ 48%)
- พิสูจน์ว่า DCA > Lump sum ในกรณี BTC volatility สูง

### 5.3 Bollinger 3-tier
- ตามไอเดียที่ user เสนอใน comment กรอบ BB Week
- 5y ROI: +79.04% (ใกล้เคียง SMA-2x)

### 5.4 Rolling Distribution Analysis
- รัน 314 backtest paths
- คำตอบเปลี่ยนจาก "ROI 5 ปี = +75%" → **"Median 3y ROI = +133%, P10 = +26%, prob_profit = 100%"**
- ลด single-path bias

### 5.5 Audit Trail
- Source endpoint, range, fee rate, generated time แสดงในตัว dashboard
- Reproducibility commands print ได้
- Disclosure quirks ของ data (3 deduped dates)

---

## 6. Risk Reduction Summary

### Risks ที่ Version เก่าสร้างไว้

1. ❌ **ตัดสินใจตามตัวเลขผิด** — "1,240 วันถึง 1 BTC" ของเก่าเป็นตัวเลขที่ AI hallucinate
2. ❌ **Underestimate cost** — ไม่หักค่าธรรมเนียม → ROI ดูสูงกว่าจริง
3. ❌ **Cherry-pick start date** — ไม่รู้ว่าเริ่มวันอื่นจะได้เท่าไหร่
4. ❌ **No fallback strategy** — เห็นแค่ flat กับ sma2x
5. ❌ **Trust without verify** — ไม่มีทาง audit

### Risks ที่ Version ใหม่ลด/ขจัด

1. ✅ **Number traceable** — ทุกตัวเลข trace กลับไป algorithm + raw data
2. ✅ **Cost realistic** — หักค่าธรรมเนียมตามจริง
3. ✅ **Distribution view** — เห็น "ดีสุด/แย่สุด" ในรอบ 5 ปี
4. ✅ **5 strategies compared** — เลือกได้ตามความเสี่ยง
5. ✅ **Test-protected** — 11 unit tests กัน regression

---

## 7. Cost & Effort Comparison

| ประเด็น | เก่า | ใหม่ |
|---|---|---|
| Time to build | ~30 นาที (AI สร้าง) | ~3 ชม. (Phase 1-3) |
| Lines of code | ~440 (JSX) | ~1,500 (Python + HTML) |
| Reusability | ❌ Single artifact | ✅ Pipeline reusable |
| Maintenance | Re-prompt AI | `python build_dashboard.py` |
| Cost to run | $0 (Claude included) | $0 (Bitkub free + local) |
| Cost to refresh data | Re-prompt + cross-check | 1 command, 5 sec |

**ROI ของการ rebuild:**
- เวลา 3 ชม. → ป้องกันการตัดสินใจผิดบนเงิน 1,000+ baht/วัน
- Break-even หลังจากใช้ ~30 นาที (วันแรก)

---

## 8. Recommendation

### สำหรับ user ทั่วไป (เพื่อนๆ ที่อ่านโพสต์เก่า)

ใช้ **dashboard ใหม่** (`dist/dashboard.html`) แทน artifact เก่า เพราะ:
- ตัวเลขถูกต้องตามคำนวณจริง
- เห็นได้ว่ากลยุทธ์ไหนดีกว่า (ไม่ใช่แค่ flat vs sma2x)
- เห็น distribution → ตัดสินใจดีขึ้น

### สำหรับ DCA จริง (ของ user เอง)

จาก backtest ใหม่:
1. **Mayer Multiple** ให้ผลดีที่สุด แต่ใช้เงินมากที่สุด (2.89M vs 1.83M ใน 5 ปี)
2. ถ้าต้องการ simple → **SMA-2x** ตามไอเดียเดิมก็ใช้ได้ ผลใกล้เคียง
3. **อย่าใช้ Lump sum** ถ้าจังหวะเริ่มผิด (เห็นจาก ROI 46% เทียบ DCA 75%)

### สำหรับ Future development (ถ้าต้องการ)

- Phase 4: เพิ่ม strategy ใหม่ (Pi Cycle, MVRV, RHODL)
- Phase 5: Out-of-sample validation (split train/test)
- Phase 6: Live integration กับ Binance TH Auto DCA API

---

## 9. Sign-off

| Item | Status |
|---|---|
| Bugs ใน version เก่า | ✅ Documented & fixed in new |
| Numbers ใน version ใหม่ | ✅ Test-verified, traceable |
| Documentation | ✅ README + this report |
| Reproducibility | ✅ One command rebuild |
| Sharable artifact | ✅ Single HTML file |

**ข้อสรุป:** Version ใหม่พร้อมใช้แทนของเก่าได้เต็มรูปแบบ — แนะนำให้ **deprecate** artifact เก่าและ **link to new dashboard** ในโพสต์ Facebook
