"""Build a self-contained interactive HTML dashboard.

Produces dist/dashboard.html with:
  - All backtest data embedded as JSON
  - Chart.js from CDN for visualization
  - Strategy comparison view (equity overlay, stat cards)
  - Rolling distribution view (histogram, percentiles)
  - Data integrity view (audit trail)
  - No build step required, opens directly in browser
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data_loader import load_btc_thb
from engine import add_indicators, run_dca, STRATEGIES, DEFAULT_FEE
from metrics import compute_metrics
from rolling import rolling_window


ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DASHBOARD = DIST / "index.html"

WINDOWS = [("1y", 365), ("3y", 1095), ("5y", 1826)]
STRATS = [
    ("flat", "Flat DCA", "#94a3b8"),
    ("sma2x", "SMA-2x", "#60a5fa"),
    ("mayer", "Mayer Multiple", "#22c55e"),
    ("bollinger3", "Bollinger 3-tier", "#a78bfa"),
    ("lumpsum", "Lump Sum", "#f59e0b"),
]
DAILY_AMOUNT = 1000.0
EQUITY_SAMPLE_EVERY = 7   # weekly sampling for chart compactness


def lump_factory(n_days, daily):
    return {"lump_total_thb": n_days * daily}


def sample_equity(eq: pd.DataFrame, every: int = EQUITY_SAMPLE_EVERY) -> list:
    """Downsample equity curve to weekly points + always include final."""
    sampled = eq.iloc[::every].copy()
    if sampled.iloc[-1]["date"] != eq.iloc[-1]["date"]:
        sampled = pd.concat([sampled, eq.iloc[[-1]]])
    return [
        {
            "d": r["date"].strftime("%Y-%m-%d"),
            "p": round(float(r["price"]), 2),
            "btc": round(float(r["btc"]), 5),
            "inv": round(float(r["invested"]), 0),
            "val": round(float(r["value"]), 0),
            "dd": round(float(r["drawdown"]) * 100, 2),
        }
        for _, r in sampled.iterrows()
    ]


def collect_single_path(df_full: pd.DataFrame) -> dict:
    """For each window×strategy, run backtest and return summary + equity curve."""
    out = {}
    for label, n_days in WINDOWS:
        sub = df_full.iloc[-n_days:].reset_index(drop=True)
        out[label] = []
        for strat_id, _, _ in STRATS:
            extra = lump_factory(n_days, DAILY_AMOUNT) if strat_id == "lumpsum" else None
            r = run_dca(sub, strategy=strat_id, daily_amount=DAILY_AMOUNT,
                        fee_rate=DEFAULT_FEE, extra_params=extra)
            m = compute_metrics(r)
            out[label].append({
                "strategy": strat_id,
                "metrics": m.as_dict(),
                "equity": sample_equity(r.equity),
            })
    return out


def collect_goal_reference(rolling_out: dict) -> dict:
    """Distill rolling data into goal-calculator-friendly reference.

    For each strategy × window, give per-฿1000/day-base reference:
      median_btc, p10_btc, p90_btc, median_invested
    Goal calculator uses these to project future outcomes.
    """
    ref = {}
    for window_label, results in rolling_out.items():
        if not results or isinstance(results, str):
            continue
        ref[window_label] = {}
        for r in results:
            if r["strategy"] == "lumpsum":
                continue
            ref[window_label][r["strategy"]] = {
                "median_btc": r["summary"]["btc_median"],
                "n_paths": r["n_paths"],
                "median_roi_pct": r["summary"]["roi"]["median"],
                "p10_roi_pct": r["summary"]["roi"]["p10"],
                "p90_roi_pct": r["summary"]["roi"]["p90"],
                "prob_profit_pct": r["summary"]["prob_profit"],
            }
    return ref


def fetch_fear_greed() -> dict | None:
    """Fetch current Fear & Greed Index from alternative.me API.

    Free public API, no auth needed. Returns None on failure (graceful degrade).
    """
    import requests
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        r.raise_for_status()
        data = r.json()["data"][0]
        return {
            "value": int(data["value"]),
            "classification": data["value_classification"],
            "timestamp": data["timestamp"],
            "source": "alternative.me",
        }
    except Exception as e:
        print(f"[fear_greed] WARN: fetch failed ({e}), skipping")
        return None


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Standard Wilder's RSI(14) on close prices."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_timing_advantage(date: pd.Timestamp) -> dict:
    """Returns timing advantage info from PDF stats (River Financial 2023 study).

    Stats compounded from 13 years of BTC data (2010-2023).
    """
    # Day of week (0=Monday, 6=Sunday)
    dow = date.weekday()
    # Day of month (1-31)
    dom = date.day

    # Monday advantage: +14.36% (from PDF section 5.1)
    dow_advantage = {
        0: 14.36,    # Monday — best
        1: 0.0,      # Tuesday — neutral baseline
        2: -2.0,     # Wednesday
        3: -4.0,     # Thursday
        4: -3.0,     # Friday
        5: -2.0,     # Saturday
        6: -3.36,    # Sunday — opposite of Monday
    }
    dow_names = {0: "จันทร์", 1: "อังคาร", 2: "พุธ", 3: "พฤหัสฯ", 4: "ศุกร์", 5: "เสาร์", 6: "อาทิตย์"}

    # Day-of-month advantage
    if dom == 1:
        dom_advantage, dom_label = 6.83, "วันที่ 1 ของเดือน — top advantage"
    elif dom == 2:
        dom_advantage, dom_label = 3.73, "วันที่ 2 ของเดือน — high advantage"
    elif dom <= 7:
        dom_advantage, dom_label = 1.5, f"ต้นเดือน (วันที่ {dom})"
    elif dom >= 29:
        dom_advantage, dom_label = -3.0, f"ปลายเดือน (วันที่ {dom}) — มักเป็นจุดสูง"
    else:
        dom_advantage, dom_label = 0.0, f"กลางเดือน (วันที่ {dom})"

    total_advantage = dow_advantage[dow] + dom_advantage
    return {
        "day_of_week": dow,
        "day_of_week_th": dow_names[dow],
        "day_of_week_advantage_pct": dow_advantage[dow],
        "day_of_month": dom,
        "day_of_month_label": dom_label,
        "day_of_month_advantage_pct": dom_advantage,
        "total_advantage_pct": total_advantage,
        "is_monday": dow == 0,
        "is_first_or_second": dom in (1, 2),
        "best_day": dow == 0 and dom in (1, 2),  # combo!
        "source": "PDF Sec 5 (River Financial 2023, 13y stats)",
    }


# Annual returns from PDF Table 2 (Section 2)
BTC_ANNUAL_RETURNS = [
    {"year": 2014, "return_pct": -29.99, "phase": "หลัง ATH 2013"},
    {"year": 2015, "return_pct": 34.47,  "phase": "Accumulation Phase"},
    {"year": 2016, "return_pct": 123.83, "phase": "ก่อน/หลัง Halving"},
    {"year": 2017, "return_pct": 1368.90, "phase": "Bull market (Euphoria)"},
    {"year": 2018, "return_pct": -73.56, "phase": "Bear market"},
    {"year": 2019, "return_pct": 92.20,  "phase": "Recovery"},
    {"year": 2020, "return_pct": 303.16, "phase": "COVID liquidity"},
    {"year": 2021, "return_pct": 59.67,  "phase": "Double-top cycle"},
    {"year": 2022, "return_pct": -64.27, "phase": "Crypto winter / rate hikes"},
    {"year": 2023, "return_pct": 155.42, "phase": "ETF anticipation"},
    {"year": 2024, "return_pct": 121.05, "phase": "Spot ETF + ATH"},
    {"year": 2025, "return_pct": -6.34,  "phase": "Consolidation"},
    {"year": 2026, "return_pct": -12.13, "phase": "Current YTD"},
]


def collect_today_state(df_full: pd.DataFrame) -> dict:
    """Compute today's DCA recommendation per strategy, with full context.

    This is what powers the 'DCA วันนี้' tab — daily review snapshot.
    """
    last = df_full.iloc[-1]
    df_clean = df_full.dropna(subset=["mayer", "sma_140", "sma_200", "bb_lo", "bb_up"])

    # Phase 10: extra indicators from PDF principles
    rsi_series = compute_rsi(df_full["c"])
    rsi_today = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None
    rsi_5d_ago = float(rsi_series.iloc[-6]) if len(rsi_series) > 6 else None
    timing = compute_timing_advantage(last["date"])
    fear_greed = fetch_fear_greed()

    # Recent context
    def back_pct(days):
        if len(df_full) <= days:
            return None
        prev = df_full.iloc[-days - 1]
        return {
            "date": prev["date"].strftime("%Y-%m-%d"),
            "price": float(prev["c"]),
            "change_pct": round((float(last["c"]) / float(prev["c"]) - 1) * 100, 2),
        }

    # 1y range position
    last_365 = df_full.tail(365)
    high_1y = float(last_365["c"].max())
    low_1y = float(last_365["c"].min())
    range_pos = (float(last["c"]) - low_1y) / (high_1y - low_1y) * 100

    # Per-strategy recommendation
    today_decisions = []
    for strat_id, _, _ in STRATS:
        if strat_id == "lumpsum":
            continue  # not relevant for daily DCA
        mult, lump = STRATEGIES[strat_id](last, {})
        amount = DAILY_AMOUNT * mult + lump
        # Reason text
        if strat_id == "flat":
            reason = "DCA คงที่ทุกวัน"
        elif strat_id == "sma2x":
            sma = float(last["sma_140"])
            reason = (f"ราคาต่ำกว่า SMA 20W (฿{sma:,.0f}) → 2x"
                      if last["c"] < sma else
                      f"ราคาเหนือ SMA 20W (฿{sma:,.0f}) → 1x ปกติ")
        elif strat_id == "mayer":
            m = float(last["mayer"])
            if m < 0.8:
                reason = f"Mayer {m:.3f} < 0.8 → deeply undervalued, 3x"
            elif m < 1.0:
                reason = f"Mayer {m:.3f} < 1.0 → undervalued, 2x"
            elif m > 2.4:
                reason = f"Mayer {m:.3f} > 2.4 → overheated, 0.5x"
            else:
                reason = f"Mayer {m:.3f} อยู่ในช่วงปกติ (1.0–2.4) → 1x"
        elif strat_id == "bollinger3":
            c, lo, up = float(last["c"]), float(last["bb_lo"]), float(last["bb_up"])
            if c < lo:
                reason = f"ราคาต่ำกว่า BB lower (฿{lo:,.0f}) → 3x"
            elif c > up:
                reason = f"ราคาเหนือ BB upper (฿{up:,.0f}) → 1x ระมัดระวัง"
            else:
                reason = f"ราคาในกรอบ BB (฿{lo:,.0f}–฿{up:,.0f}) → 1.5x"
        today_decisions.append({
            "strategy": strat_id,
            "multiplier": mult,
            "amount_thb": amount,
            "reason": reason,
        })

    # Threshold prices — where each tier triggers
    sma_200 = float(last["sma_200"])
    sma_140 = float(last["sma_140"])
    bb_lo = float(last["bb_lo"])
    bb_up = float(last["bb_up"])
    thresholds = {
        "sma_20w": {"price": sma_140, "label": "SMA 20W (sma2x trigger 2x ใต้เส้น)"},
        "sma_200": {"price": sma_200, "label": "SMA 200 / Mayer = 1.0 (mayer trigger 2x ใต้เส้น)"},
        "mayer_08": {"price": sma_200 * 0.8, "label": "Mayer = 0.8 (mayer trigger 3x ใต้เส้น)"},
        "mayer_24": {"price": sma_200 * 2.4, "label": "Mayer = 2.4 (mayer ลด 0.5x เหนือเส้น)"},
        "bb_upper": {"price": bb_up, "label": "BB upper (bollinger ลด 1x เหนือเส้น)"},
        "bb_lower": {"price": bb_lo, "label": "BB lower (bollinger เพิ่ม 3x ใต้เส้น)"},
    }

    # Mayer historical distribution (for histogram with current marker)
    mayer_hist = df_clean["mayer"].tolist()
    mayer_pct_below = float((df_clean["mayer"] < float(last["mayer"])).sum() / len(df_clean) * 100)

    return {
        "as_of_date": last["date"].strftime("%Y-%m-%d"),
        "price": float(last["c"]),
        "indicators": {
            "sma_20w": sma_140,
            "sma_200": sma_200,
            "bb_upper": bb_up,
            "bb_lower": bb_lo,
            "mayer": float(last["mayer"]),
            "price_vs_sma20w_pct": round((float(last["c"]) / sma_140 - 1) * 100, 2),
            "price_vs_sma200_pct": round((float(last["c"]) / sma_200 - 1) * 100, 2),
        },
        "context": {
            "30d": back_pct(30),
            "90d": back_pct(90),
            "365d": back_pct(365),
            "1y_high": high_1y,
            "1y_low": low_1y,
            "1y_range_pos_pct": round(range_pos, 1),
        },
        "decisions": today_decisions,
        "thresholds": thresholds,
        "rsi_14": round(rsi_today, 2) if rsi_today is not None else None,
        "rsi_14_5d_ago": round(rsi_5d_ago, 2) if rsi_5d_ago is not None else None,
        "timing_advantage": timing,
        "fear_greed": fear_greed,
        "annual_returns": BTC_ANNUAL_RETURNS,
        "mayer_history": [round(v, 4) for v in mayer_hist],
        "mayer_percentile": round(mayer_pct_below, 1),
        "mayer_stats": {
            "median": round(float(df_clean["mayer"].median()), 3),
            "mean": round(float(df_clean["mayer"].mean()), 3),
            "p10": round(float(df_clean["mayer"].quantile(0.10)), 3),
            "p25": round(float(df_clean["mayer"].quantile(0.25)), 3),
            "p75": round(float(df_clean["mayer"].quantile(0.75)), 3),
            "p90": round(float(df_clean["mayer"].quantile(0.90)), 3),
        },
    }


def collect_rolling(df_full: pd.DataFrame) -> dict:
    """For each window×strategy, run rolling and return distribution + raw rois."""
    out = {}
    for label, n_days in WINDOWS:
        if n_days >= len(df_full):
            out[label] = None
            continue
        out[label] = []
        for strat_id, _, _ in STRATS:
            factory = lump_factory if strat_id == "lumpsum" else None
            rs = rolling_window(
                df_full, strategy=strat_id, window_days=n_days,
                step_days=7, daily_amount=DAILY_AMOUNT,
                extra_params_factory=factory,
            )
            # Re-collect raw ROIs for histogram
            rois = []
            for start_idx in range(0, len(df_full) - n_days, 7):
                sub = df_full.iloc[start_idx : start_idx + n_days].reset_index(drop=True)
                params = factory(n_days, DAILY_AMOUNT) if factory else None
                r = run_dca(sub, strategy=strat_id, daily_amount=DAILY_AMOUNT,
                            fee_rate=DEFAULT_FEE, extra_params=params)
                rois.append(round(r.roi * 100, 2))

            out[label].append({
                "strategy": strat_id,
                "n_paths": rs.n_paths,
                "summary": {
                    "roi": {k: round(v * 100, 2) if isinstance(v, float) and k != "n" else v
                            for k, v in rs.roi.items()},
                    "btc_median": round(rs.final_btc["median"], 4),
                    "dd_median": round(rs.max_drawdown["median"] * 100, 2),
                    "prob_profit": round(rs.roi["prob_profit"] * 100, 1),
                },
                "rois": rois,
            })
    return out


def main():
    print("[dashboard] loading data...")
    ps = load_btc_thb()
    df_full = add_indicators(ps.df)
    print(f"[dashboard] {len(df_full)} bars, {ps.df['date'].iloc[0].date()} → {ps.df['date'].iloc[-1].date()}")

    print("[dashboard] computing today's state...")
    today = collect_today_state(df_full)

    print("[dashboard] running single-path backtests...")
    single = collect_single_path(df_full)

    print("[dashboard] running rolling analyses (this takes ~30s)...")
    rolling_out = collect_rolling(df_full)

    payload = {
        "meta": {
            "data_source": ps.source,
            "data_endpoint": "https://api.bitkub.com/tradingview/history",
            "symbol": "BTC_THB",
            "data_range_from": ps.df["date"].iloc[0].strftime("%Y-%m-%d"),
            "data_range_to": ps.df["date"].iloc[-1].strftime("%Y-%m-%d"),
            "data_bars": len(ps.df),
            "fee_rate_pct": DEFAULT_FEE * 100,
            "daily_amount_thb": DAILY_AMOUNT,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strategies": [{"id": s, "label": l, "color": c} for s, l, c in STRATS],
            "windows": [{"id": w, "days": d} for w, d in WINDOWS],
        },
        "today": today,
        "single_path": single,
        "rolling": rolling_out,
        "goal_reference": collect_goal_reference(rolling_out),
    }

    DIST.mkdir(parents=True, exist_ok=True)
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    template = (ROOT / "scripts" / "dashboard_template.html").read_text(encoding="utf-8")
    html = template.replace("/*__DATA_PLACEHOLDER__*/", payload_json)
    DASHBOARD.write_text(html, encoding="utf-8")

    size_kb = DASHBOARD.stat().st_size / 1024
    print(f"\n✅ Dashboard → {DASHBOARD} ({size_kb:.1f} KB)")
    print(f"   Open in browser: file://{DASHBOARD}")


if __name__ == "__main__":
    main()
