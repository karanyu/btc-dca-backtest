"""End-to-end Phase 2 comparison.

Runs:
  - Single-path backtest: 5 strategies × 3 windows (1y, 3y, 5y)
  - Rolling-window analysis: 5 strategies × 3 windows
  - Generates: data/phase2_comparison_report.md
              data/phase2_results.json (machine-readable)

Run: .venv/bin/python scripts/run_comparison.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from data_loader import load_btc_thb
from engine import add_indicators, run_dca, STRATEGIES, DEFAULT_FEE
from metrics import compute_metrics
from rolling import rolling_window


ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data" / "phase2_comparison_report.md"
JSON_OUT = ROOT / "data" / "phase2_results.json"

WINDOWS = [
    ("1y", 365),
    ("3y", 1095),
    ("5y", 1826),  # actual full dataset length
]
STRATS = ["flat", "sma2x", "mayer", "bollinger3", "lumpsum"]
DAILY_AMOUNT = 1000.0


def _lump_factory(n_days: int, daily: float) -> dict:
    """Lump-sum budget = what flat DCA would invest over the same window."""
    return {"lump_total_thb": n_days * daily}


def single_path_run(df: pd.DataFrame, strategy: str, n_days: int) -> dict:
    """Run end-of-period single-path backtest.

    Uses the LAST n_days of the dataset (so '5y' = the full series).
    """
    sub = df.iloc[-n_days:].reset_index(drop=True)
    extra = _lump_factory(n_days, DAILY_AMOUNT) if strategy == "lumpsum" else None
    r = run_dca(sub, strategy=strategy, daily_amount=DAILY_AMOUNT,
                fee_rate=DEFAULT_FEE, extra_params=extra)
    m = compute_metrics(r)
    return m.as_dict()


def fmt_thb(v) -> str:
    return f"฿{v:,.0f}"


def fmt_pct(v) -> str:
    return f"{v:+.2f}%"


def render_single_table(rows: list[dict], window_label: str) -> str:
    out = [
        f"### {window_label} window — single-path (end of dataset)",
        "",
        "| Strategy | Invested | Fees | BTC | Value | ROI | CAGR | MaxDD | Sortino | T-to-1BTC |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        t1 = f"{r['time_to_1btc_days']}d" if r["time_to_1btc_days"] else "—"
        out.append(
            f"| {r['strategy']} | {fmt_thb(r['total_invested'])} | {fmt_thb(r['total_fees'])} "
            f"| {r['final_btc']:.4f} | {fmt_thb(r['final_value'])} "
            f"| {fmt_pct(r['roi_pct'])} | {fmt_pct(r['cagr_pct'])} "
            f"| {r['max_drawdown_pct']:.1f}% | {r['sortino']:.2f} | {t1} |"
        )
    return "\n".join(out)


def render_rolling_table(rolling_results: list, window_label: str) -> str:
    out = [
        f"### {window_label} window — rolling analysis (across all start dates)",
        "",
        "| Strategy | N paths | ROI median | P10 | P90 | Prob profit | BTC median | MaxDD median |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rs in rolling_results:
        roi = rs.roi
        btc = rs.final_btc
        dd = rs.max_drawdown
        out.append(
            f"| {rs.strategy} | {rs.n_paths} "
            f"| {roi['median']*100:+.2f}% "
            f"| {roi['p10']*100:+.2f}% "
            f"| {roi['p90']*100:+.2f}% "
            f"| {roi['prob_profit']*100:.1f}% "
            f"| {btc['median']:.4f} "
            f"| {dd['median']*100:.1f}% |"
        )
    return "\n".join(out)


def main():
    print("Phase 2 — running comparison...")
    ps = load_btc_thb()
    df_full = add_indicators(ps.df)
    print(f"Loaded {len(df_full)} bars, {ps.df['date'].iloc[0].date()} → {ps.df['date'].iloc[-1].date()}")

    results = {
        "metadata": {
            "data_source": ps.source,
            "data_range": f"{ps.df['date'].iloc[0].date()} → {ps.df['date'].iloc[-1].date()}",
            "data_bars": len(ps.df),
            "fee_rate": DEFAULT_FEE,
            "daily_amount": DAILY_AMOUNT,
            "strategies": STRATS,
        },
        "single_path": {},
        "rolling": {},
    }

    # ── Single-path runs ───────────────────────────────
    for label, days in WINDOWS:
        results["single_path"][label] = []
        for strat in STRATS:
            print(f"  single  {label:>3} {strat:<11} ...", end="")
            r = single_path_run(df_full, strat, days)
            results["single_path"][label].append(r)
            print(f" ROI {r['roi_pct']:+6.2f}%  BTC {r['final_btc']:.4f}")

    # ── Rolling analysis ───────────────────────────────
    for label, days in WINDOWS:
        if days >= len(df_full):
            print(f"  rolling {label}: skipped (window >= data length)")
            results["rolling"][label] = "skipped (window length >= dataset)"
            continue
        results["rolling"][label] = []
        for strat in STRATS:
            print(f"  rolling {label:>3} {strat:<11} ...", end="")
            factory = _lump_factory if strat == "lumpsum" else None
            rs = rolling_window(
                df_full, strategy=strat, window_days=days,
                step_days=7, daily_amount=DAILY_AMOUNT,
                extra_params_factory=factory,
            )
            results["rolling"][label].append(rs)
            print(f" n={rs.n_paths:3d}  median ROI {rs.roi['median']*100:+6.2f}%  "
                  f"P10 {rs.roi['p10']*100:+6.2f}%  P90 {rs.roi['p90']*100:+6.2f}%")

    # ── Render report ──────────────────────────────────
    md = [
        "# Phase 2 — Backtest Comparison Report",
        "",
        f"**Data:** {results['metadata']['data_source']} BTC/THB daily, "
        f"{results['metadata']['data_range']} ({results['metadata']['data_bars']} bars)  ",
        f"**Fee:** {DEFAULT_FEE*100:.2f}% per trade  ",
        f"**Base daily amount:** ฿{DAILY_AMOUNT:,.0f}  ",
        "",
        "## Strategy descriptions",
        "",
        "- **flat**: ฿1,000 / day, every day.",
        "- **sma2x**: ฿1,000 / day; ฿2,000 when close < SMA(140 days, ≈20W).",
        "- **mayer**: Mayer Multiple = close/SMA(200). <0.8 → 3x, <1.0 → 2x, >2.4 → 0.5x, else 1x.",
        "- **bollinger3**: Bollinger(140, 2σ). Below lower → 3x, in band → 1.5x, above upper → 1x.",
        "- **lumpsum**: invest the full equivalent flat-DCA budget on day 1, then nothing.",
        "",
        "## Part 1 — Single-path runs",
        "",
        "*Result if you happen to start DCA at the exact start of each window ending today.",
        "Sensitive to start date — see Part 2 for distribution view.*",
        "",
    ]
    for label, _ in WINDOWS:
        md.append(render_single_table(results["single_path"][label], label))
        md.append("")

    md += [
        "## Part 2 — Rolling-window analysis",
        "",
        "*Distribution of outcomes across ALL possible start dates (step=7 days).",
        "This is the statistically honest view of what to expect.*",
        "",
    ]
    for label, _ in WINDOWS:
        v = results["rolling"][label]
        if isinstance(v, str):
            md.append(f"### {label}: {v}\n")
            continue
        md.append(render_rolling_table(v, label))
        md.append("")

    # ── Summary findings ───────────────────────────────
    md += [
        "## Key findings",
        "",
        "1. **Methodology fix vs prior backtest:** numbers now derive from real",
        "   daily Bitkub closes (not monthly averages), fees deducted at 0.25%,",
        "   and BTC accumulation is provably monotonic (verified by unit tests).",
        "",
        "2. **Single-path bias:** the '5-year ROI = +75%' figure depends on the",
        "   exact start date. Part 2 shows the full distribution.",
        "",
        "3. **Strategy ranking (from rolling 1y data):** see table above —",
        "   compare median ROI and P10 (worst 10%) for risk-adjusted ranking.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "cd ~/Projects/btc-dca-backtest",
        "source .venv/bin/activate",
        "python scripts/run_comparison.py",
        "```",
        "",
        "All numbers in this report trace to deterministic functions in",
        "`scripts/engine.py` operating on `data/btc_thb_daily.json`.",
        "",
    ]

    REPORT.write_text("\n".join(md))

    # ── Save machine-readable results ──────────────────
    serializable = {
        "metadata": results["metadata"],
        "single_path": results["single_path"],
        "rolling": {
            label: (
                v if isinstance(v, str) else
                [{
                    "strategy": rs.strategy,
                    "window_days": rs.window_days,
                    "n_paths": rs.n_paths,
                    "roi": rs.roi,
                    "cagr": rs.cagr,
                    "final_btc": rs.final_btc,
                    "max_drawdown": rs.max_drawdown,
                    "time_to_1btc": rs.time_to_1btc,
                } for rs in v]
            )
            for label, v in results["rolling"].items()
        },
    }
    JSON_OUT.write_text(json.dumps(serializable, indent=2, default=str))

    print(f"\n✅ Report → {REPORT}")
    print(f"✅ Data   → {JSON_OUT}")


if __name__ == "__main__":
    main()
