"""Rolling window analysis — distribution of DCA outcomes across start dates.

For each (strategy, window_days), iterate start_date through the dataset,
run a DCA backtest, and collect summary metrics.

This addresses single-path bias: instead of saying "if you started 5 years
ago you'd have +75%", we say "median 5y ROI = X%, P10 = Y%, P90 = Z%".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from engine import add_indicators, run_dca, DEFAULT_FEE
from metrics import compute_metrics


@dataclass
class RollingSummary:
    strategy: str
    window_days: int
    n_paths: int
    roi: dict     # {p10, p25, median, p75, p90, mean, prob_profit}
    cagr: dict
    final_btc: dict
    max_drawdown: dict
    time_to_1btc: dict


def _percentiles(values: list[float], drop_na: bool = False) -> dict:
    arr = np.array([v for v in values if v is not None]) if drop_na else np.array(values)
    if len(arr) == 0:
        return {"p10": None, "p25": None, "median": None, "p75": None,
                "p90": None, "mean": None, "n": 0}
    return {
        "p10": float(np.percentile(arr, 10)),
        "p25": float(np.percentile(arr, 25)),
        "median": float(np.median(arr)),
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90)),
        "mean": float(arr.mean()),
        "n": int(len(arr)),
    }


def rolling_window(
    prices: pd.DataFrame,
    strategy: str,
    window_days: int,
    *,
    step_days: int = 7,
    daily_amount: float = 1000.0,
    fee_rate: float = DEFAULT_FEE,
    extra_params_factory=None,
) -> RollingSummary:
    """Run rolling-window DCA and summarize outcomes.

    Args:
        prices: full DataFrame (with indicators).
        strategy: name of strategy registered in engine.STRATEGIES.
        window_days: length of each backtest path.
        step_days: stride between consecutive start dates.
        extra_params_factory: callable (n_days, daily_amount) -> dict, used
            for lumpsum where total budget depends on window length.
    """
    df = prices.sort_values("date").reset_index(drop=True)
    n = len(df)
    if window_days >= n:
        raise ValueError(f"window_days ({window_days}) >= n_bars ({n})")

    rois, cagrs, btcs, dds, t1s = [], [], [], [], []
    n_paths = 0

    for start_idx in range(0, n - window_days, step_days):
        sub = df.iloc[start_idx : start_idx + window_days].reset_index(drop=True)
        params = extra_params_factory(window_days, daily_amount) if extra_params_factory else None
        r = run_dca(sub, strategy=strategy, daily_amount=daily_amount,
                    fee_rate=fee_rate, extra_params=params)
        m = compute_metrics(r)
        rois.append(m.roi)
        cagrs.append(m.cagr)
        btcs.append(m.final_btc)
        dds.append(m.max_drawdown)
        t1s.append(m.time_to_1btc_days)
        n_paths += 1

    roi_pcts = _percentiles(rois)
    roi_pcts["prob_profit"] = float(sum(1 for r in rois if r > 0) / len(rois)) if rois else 0.0

    return RollingSummary(
        strategy=strategy,
        window_days=window_days,
        n_paths=n_paths,
        roi=roi_pcts,
        cagr=_percentiles(cagrs),
        final_btc=_percentiles(btcs),
        max_drawdown=_percentiles(dds),
        time_to_1btc=_percentiles(t1s, drop_na=True),
    )
