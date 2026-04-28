"""Performance metrics for a BacktestResult.

Computed metrics:
- ROI (final_value - invested) / invested
- CAGR (geometric, time-adjusted)
- Max Drawdown (from equity peak)
- Sortino (excess return / downside std)
- Time-to-1BTC (days)
- BTC accumulated, avg buy price, total fees
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from engine import BacktestResult


@dataclass
class Metrics:
    strategy: str
    days: int
    years: float
    daily_amount: int
    total_invested: float
    total_fees: float
    final_btc: float
    final_value: float
    roi: float
    cagr: float
    max_drawdown: float
    sortino: float
    time_to_1btc_days: Optional[int]
    avg_buy_price: float
    final_price: float

    def as_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "days": self.days,
            "years": round(self.years, 2),
            "daily_amount": self.daily_amount,
            "total_invested": round(self.total_invested, 2),
            "total_fees": round(self.total_fees, 2),
            "final_btc": round(self.final_btc, 6),
            "final_value": round(self.final_value, 2),
            "roi_pct": round(self.roi * 100, 2),
            "cagr_pct": round(self.cagr * 100, 2),
            "max_drawdown_pct": round(self.max_drawdown * 100, 2),
            "sortino": round(self.sortino, 3),
            "time_to_1btc_days": self.time_to_1btc_days,
            "avg_buy_price": round(self.avg_buy_price, 2),
            "final_price": round(self.final_price, 2),
        }


def _cagr(start_value: float, end_value: float, years: float) -> float:
    """Compounded Annual Growth Rate. For DCA, start_value is total invested
    (which is technically not what CAGR is meant for, but useful as proxy)."""
    if start_value <= 0 or years <= 0:
        return 0.0
    return (end_value / start_value) ** (1.0 / years) - 1.0


def _sortino(equity: pd.DataFrame, target_return: float = 0.0) -> float:
    """Sortino ratio on daily portfolio returns (mark-to-market value).

    For DCA, daily return is computed on (value - invested) / invested.
    We use simple value-pct-change, which is influenced by both price moves
    and capital injections — for DCA this is acceptable as a proxy.
    """
    # Use daily pct change of value, but only after first non-zero day
    eq = equity[equity["value"] > 0].copy()
    if len(eq) < 2:
        return 0.0
    rets = eq["value"].pct_change().dropna()
    if len(rets) == 0 or rets.std() == 0:
        return 0.0
    excess = rets - target_return / 252  # daily target
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return (excess.mean() * 252) / (downside.std() * np.sqrt(252))


def _time_to_1btc(equity: pd.DataFrame) -> Optional[int]:
    """Days from start until cumulative BTC ≥ 1.0. None if never reached."""
    hit = equity[equity["btc"] >= 1.0]
    if len(hit) == 0:
        return None
    first = hit.iloc[0]["date"]
    start = equity.iloc[0]["date"]
    return int((first - start).days)


def compute_metrics(result: BacktestResult) -> Metrics:
    """Derive performance metrics from a BacktestResult."""
    years = result.days / 365.25
    cagr = _cagr(result.total_invested, result.final_value, years)
    max_dd = float(result.equity["drawdown"].max())
    sortino = _sortino(result.equity)
    t1 = _time_to_1btc(result.equity)
    avg_buy = result.total_invested / result.final_btc if result.final_btc > 0 else 0.0

    return Metrics(
        strategy=result.strategy,
        days=result.days,
        years=years,
        daily_amount=result.daily_amount,
        total_invested=result.total_invested,
        total_fees=result.total_fees,
        final_btc=result.final_btc,
        final_value=result.final_value,
        roi=result.roi,
        cagr=cagr,
        max_drawdown=max_dd,
        sortino=sortino,
        time_to_1btc_days=t1,
        avg_buy_price=avg_buy,
        final_price=result.final_price,
    )
