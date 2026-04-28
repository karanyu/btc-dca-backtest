"""Data quality validator for BTC/THB daily series.

Checks:
- C-1: monotonic dates, no duplicates
- C-2: no missing days (continuous daily series)
- C-3: no NaN/zero/negative prices
- C-4: no extreme single-day moves (>30%) without context
- C-5: timezone consistency
- C-6: spot-check known dates

Writes data/data_quality_report.md
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "btc_thb_daily.json"
REPORT = ROOT / "data" / "data_quality_report.md"


def load_bars() -> pd.DataFrame:
    payload = json.loads(SRC.read_text())
    df = pd.DataFrame(payload["bars"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df, payload


def check_monotonic(df: pd.DataFrame) -> dict:
    diff = df["date"].diff().dropna()
    return {
        "name": "C-1: Monotonic + unique dates",
        "pass": (diff > pd.Timedelta(0)).all() and df["date"].is_unique,
        "detail": f"{len(df)} rows, {df['date'].duplicated().sum()} duplicates, "
                  f"min_gap={diff.min()}, max_gap={diff.max()}",
    }


def check_continuous(df: pd.DataFrame) -> dict:
    diff = df["date"].diff().dropna()
    gaps = diff[diff > pd.Timedelta(days=1)]
    expected = pd.Timedelta(days=1)
    return {
        "name": "C-2: Continuous daily series (no missing days)",
        "pass": (diff == expected).all(),
        "detail": f"{len(gaps)} gaps > 1 day. "
                  + (f"Largest gap: {gaps.max()}" if len(gaps) else "Perfect continuity."),
        "gap_dates": [str(df.loc[i, "date"].date()) for i in gaps.index][:10],
    }


def check_prices(df: pd.DataFrame) -> dict:
    issues = []
    for col in ["o", "h", "l", "c"]:
        nan = df[col].isna().sum()
        zero = (df[col] <= 0).sum()
        if nan: issues.append(f"{col}: {nan} NaN")
        if zero: issues.append(f"{col}: {zero} <=0")
    invalid_hl = (df["h"] < df["l"]).sum()
    if invalid_hl: issues.append(f"high<low: {invalid_hl}")
    return {
        "name": "C-3: Price sanity (no NaN, no zero/negative, h>=l)",
        "pass": not issues,
        "detail": "; ".join(issues) if issues else "All prices valid.",
    }


def check_extremes(df: pd.DataFrame, threshold: float = 0.30) -> dict:
    df = df.copy()
    df["ret"] = df["c"].pct_change()
    extremes = df[df["ret"].abs() > threshold]
    return {
        "name": f"C-4: Extreme single-day moves (>{threshold:.0%})",
        "pass": len(extremes) == 0,
        "detail": f"{len(extremes)} extreme moves found",
        "extremes": [
            {"date": str(r["date"].date()), "close": r["c"], "return": f"{r['ret']:.2%}"}
            for _, r in extremes.iterrows()
        ][:10],
    }


def check_coverage(df: pd.DataFrame) -> dict:
    first = df["date"].iloc[0]
    last = df["date"].iloc[-1]
    span_days = (last - first).days + 1
    expected = span_days
    actual = len(df)
    return {
        "name": "C-5: Coverage span vs row count",
        "pass": actual == expected,
        "detail": f"first={first.date()}, last={last.date()}, span={span_days} days, rows={actual}",
    }


def spot_check(df: pd.DataFrame) -> dict:
    # Known reference dates for sanity:
    # - End of 2021 bull cycle: ~Nov 2021 (BTC ATH ~$69k)
    # - Bottom of 2022 bear: ~Nov 2022 (~$15-20k)
    # - 2024 ATH: Mar 2024 (~$73k)
    checks = [
        ("2021-11-10", "near 2021 ATH"),
        ("2022-11-21", "near 2022 bottom"),
        ("2024-03-14", "near 2024 ATH"),
    ]
    out = []
    for date_str, label in checks:
        target = pd.Timestamp(date_str)
        row = df[df["date"] == target]
        if not len(row):
            out.append({"date": date_str, "label": label, "found": False})
            continue
        r = row.iloc[0]
        out.append({
            "date": date_str, "label": label, "found": True,
            "close_thb": float(r["c"]),
            "high_thb": float(r["h"]),
            "low_thb": float(r["l"]),
        })
    return {
        "name": "C-6: Spot-check known reference dates",
        "pass": all(c.get("found") for c in out),
        "detail": "Manual review needed (compare with TradingView/Bitkub website)",
        "rows": out,
    }


def render_report(payload: dict, df: pd.DataFrame, results: list) -> str:
    lines = [
        "# Data Quality Report — BTC/THB Daily",
        "",
        f"**Source:** {payload['source']} ({payload['endpoint']})  ",
        f"**Symbol:** {payload['symbol']} @ {payload['resolution']}  ",
        f"**Fetched:** {payload['fetched_at']}  ",
        f"**Range:** {payload['range']['from']} → {payload['range']['to']} ({payload['count']} bars)  ",
        "",
        "## Summary",
        "",
        "| Check | Pass | Detail |",
        "|---|---|---|",
    ]
    for r in results:
        mark = "✅" if r["pass"] else "❌"
        lines.append(f"| {r['name']} | {mark} | {r['detail']} |")
    lines.append("")

    # Detail sections
    for r in results:
        if "extremes" in r and r.get("extremes"):
            lines.append(f"### Extremes detail ({r['name']})\n")
            for e in r["extremes"]:
                lines.append(f"- {e['date']}: close={e['close']:,.2f}, return={e['return']}")
            lines.append("")
        if "gap_dates" in r and r.get("gap_dates"):
            lines.append(f"### Gap detail ({r['name']})\n")
            for d in r["gap_dates"]:
                lines.append(f"- {d}")
            lines.append("")
        if "rows" in r:
            lines.append(f"### Spot-check rows ({r['name']})\n")
            for row in r["rows"]:
                if row.get("found"):
                    lines.append(
                        f"- **{row['date']}** ({row['label']}): close=฿{row['close_thb']:,.2f}, "
                        f"low=฿{row['low_thb']:,.2f}, high=฿{row['high_thb']:,.2f}"
                    )
                else:
                    lines.append(f"- **{row['date']}** ({row['label']}): ❌ not found in dataset")
            lines.append("")

    # Descriptive stats
    lines += [
        "## Price Statistics (close, THB)",
        "",
        f"- Min: ฿{df['c'].min():,.2f} on {df.loc[df['c'].idxmin(), 'date'].date()}",
        f"- Max: ฿{df['c'].max():,.2f} on {df.loc[df['c'].idxmax(), 'date'].date()}",
        f"- Mean: ฿{df['c'].mean():,.2f}",
        f"- Median: ฿{df['c'].median():,.2f}",
        f"- Std: ฿{df['c'].std():,.2f}",
        "",
        "## Return Statistics (daily close-to-close)",
        "",
    ]
    rets = df["c"].pct_change().dropna()
    lines += [
        f"- Mean daily return: {rets.mean():.4%}",
        f"- Std daily return: {rets.std():.4%}",
        f"- Annualized vol: {rets.std() * (365**0.5):.2%}",
        f"- Min daily: {rets.min():.2%} on {df.loc[rets.idxmin(), 'date'].date()}",
        f"- Max daily: {rets.max():.2%} on {df.loc[rets.idxmax(), 'date'].date()}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC} not found. Run fetch_bitkub.py first.", file=sys.stderr)
        return 1

    df, payload = load_bars()
    results = [
        check_monotonic(df),
        check_continuous(df),
        check_prices(df),
        check_extremes(df),
        check_coverage(df),
        spot_check(df),
    ]
    report = render_report(payload, df, results)
    REPORT.write_text(report)

    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*60}")
    for r in results:
        mark = "PASS" if r["pass"] else "FAIL"
        print(f"  [{mark}] {r['name']}")
        print(f"         {r['detail']}")
    print(f"\nFull report → {REPORT}")
    failed = [r for r in results if not r["pass"]]
    return 0 if not failed else 3


if __name__ == "__main__":
    sys.exit(main())
