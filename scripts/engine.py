"""DCA backtest engine — pure functions.

Architecture:
    indicators(df)        -> df with rolling SMA, BB, Mayer
    strategy(row, params) -> multiplier of base daily amount
    run_dca(...)          -> trades + equity curve + summary

All numbers traceable to source bars + strategy logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────
DEFAULT_FEE = 0.0025          # Bitkub spot fee 0.25%
SMA_20W_DAYS = 140            # 20 weeks ≈ 140 calendar days
SMA_200_DAYS = 200            # Mayer Multiple convention
BB_WINDOW = 140               # weekly BB on daily series
BB_STD = 2.0


# ──────────────────────────────────────────────────────────
# Indicators
# ──────────────────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add SMA / BB / Mayer columns to a price DataFrame.

    Input df: date, o, h, l, c, v
    Output: same + sma_140, sma_200, bb_mid, bb_up, bb_lo, mayer
    """
    out = df.copy()
    out["sma_140"] = out["c"].rolling(SMA_20W_DAYS, min_periods=SMA_20W_DAYS).mean()
    out["sma_200"] = out["c"].rolling(SMA_200_DAYS, min_periods=SMA_200_DAYS).mean()
    rolling_std = out["c"].rolling(BB_WINDOW, min_periods=BB_WINDOW).std()
    out["bb_mid"] = out["sma_140"]
    out["bb_up"] = out["bb_mid"] + BB_STD * rolling_std
    out["bb_lo"] = out["bb_mid"] - BB_STD * rolling_std
    out["mayer"] = out["c"] / out["sma_200"]
    return out


# ──────────────────────────────────────────────────────────
# Strategies — return (multiplier, lump_today)
# ──────────────────────────────────────────────────────────
StrategyFn = Callable[[pd.Series, dict], tuple[float, float]]


def strat_flat(row: pd.Series, params: dict) -> tuple[float, float]:
    """Buy fixed daily amount every day."""
    return 1.0, 0.0


def strat_sma2x(row: pd.Series, params: dict) -> tuple[float, float]:
    """2x when price below SMA 20W, else 1x. Falls back to 1x when SMA is NaN (warm-up)."""
    sma = row.get("sma_140")
    if pd.isna(sma):
        return 1.0, 0.0
    return (2.0, 0.0) if row["c"] < sma else (1.0, 0.0)


def strat_mayer(row: pd.Series, params: dict) -> tuple[float, float]:
    """Mayer Multiple tiers (Price / 200DMA):
       <0.8 → 3x (deep undervalued)
       <1.0 → 2x (undervalued)
       1.0–2.4 → 1x (normal)
       >2.4 → 0.5x (overvalued cap)
    """
    m = row.get("mayer")
    if pd.isna(m):
        return 1.0, 0.0
    if m < 0.8:
        return 3.0, 0.0
    if m < 1.0:
        return 2.0, 0.0
    if m > 2.4:
        return 0.5, 0.0
    return 1.0, 0.0


def strat_bollinger3(row: pd.Series, params: dict) -> tuple[float, float]:
    """Bollinger 3-tier on weekly BB(140, 2σ):
       below lower band   → 3x
       in band            → 1.5x
       above upper band   → 1x
    """
    lo, up = row.get("bb_lo"), row.get("bb_up")
    if pd.isna(lo) or pd.isna(up):
        return 1.0, 0.0
    c = row["c"]
    if c < lo:
        return 3.0, 0.0
    if c > up:
        return 1.0, 0.0
    return 1.5, 0.0


def strat_lumpsum(row: pd.Series, params: dict) -> tuple[float, float]:
    """Invest the full planned budget on day 1, nothing after.

    Reads params['lump_total_thb'] and params['lump_already_done'].
    """
    if params.get("lump_already_done"):
        return 0.0, 0.0
    total = params.get("lump_total_thb", 0.0)
    params["lump_already_done"] = True
    # Express as absolute lump (engine treats as daily_amount * 0 + lump amount)
    return 0.0, total


STRATEGIES: dict[str, StrategyFn] = {
    "flat":       strat_flat,
    "sma2x":      strat_sma2x,
    "mayer":      strat_mayer,
    "bollinger3": strat_bollinger3,
    "lumpsum":    strat_lumpsum,
}


# ──────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────
@dataclass
class Trade:
    date: pd.Timestamp
    price: float
    gross_thb: float        # before fee
    fee_thb: float
    net_thb: float          # gross - fee, the THB that bought BTC
    btc_bought: float


@dataclass
class BacktestResult:
    strategy: str
    params: dict
    start: pd.Timestamp
    end: pd.Timestamp
    days: int
    daily_amount: int
    trades: list[Trade]
    equity: pd.DataFrame      # date, btc, invested, value, drawdown
    final_btc: float
    total_invested: float     # sum of gross THB (fees + net)
    total_fees: float
    final_price: float
    final_value: float

    @property
    def roi(self) -> float:
        return (self.final_value - self.total_invested) / self.total_invested if self.total_invested else 0.0

    @property
    def avg_buy_price(self) -> float:
        return self.total_invested / self.final_btc if self.final_btc else 0.0


# ──────────────────────────────────────────────────────────
# Core engine
# ──────────────────────────────────────────────────────────
def run_dca(
    prices: pd.DataFrame,
    *,
    strategy: str,
    daily_amount: float = 1000.0,
    fee_rate: float = DEFAULT_FEE,
    extra_params: Optional[dict] = None,
    price_field: str = "c",
) -> BacktestResult:
    """Execute DCA on a price DataFrame.

    prices: columns date, o, h, l, c, v + indicators (call add_indicators first
            for non-flat strategies).
    daily_amount: BASE daily THB. Multiplier from strategy applies.
    fee_rate: 0.0025 = 0.25%.
    extra_params: passed to strategy fn (e.g. lump_total_thb for lumpsum).
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy '{strategy}'. Options: {list(STRATEGIES)}")
    strat_fn = STRATEGIES[strategy]
    params = dict(extra_params or {})

    if "date" not in prices.columns:
        raise ValueError("prices must have 'date' column")
    df = prices.sort_values("date").reset_index(drop=True)
    n = len(df)
    if n == 0:
        raise ValueError("Empty price DataFrame")

    btc = 0.0
    invested = 0.0
    fees = 0.0
    trades: list[Trade] = []
    equity_rows = []
    peak_value = 0.0

    for _, row in df.iterrows():
        price = float(row[price_field])
        mult, lump = strat_fn(row, params)
        gross = daily_amount * mult + lump

        if gross > 0:
            fee = gross * fee_rate
            net = gross - fee
            bought = net / price
            btc += bought
            invested += gross
            fees += fee
            trades.append(Trade(
                date=row["date"], price=price,
                gross_thb=gross, fee_thb=fee, net_thb=net, btc_bought=bought,
            ))

        value = btc * price
        peak_value = max(peak_value, value)
        dd = (peak_value - value) / peak_value if peak_value > 0 else 0.0
        equity_rows.append({
            "date": row["date"],
            "price": price,
            "btc": btc,
            "invested": invested,
            "fees": fees,
            "value": value,
            "drawdown": dd,
        })

    equity = pd.DataFrame(equity_rows)
    last = equity.iloc[-1]
    return BacktestResult(
        strategy=strategy,
        params=params,
        start=df["date"].iloc[0],
        end=df["date"].iloc[-1],
        days=n,
        daily_amount=int(daily_amount),
        trades=trades,
        equity=equity,
        final_btc=btc,
        total_invested=invested,
        total_fees=fees,
        final_price=float(last["price"]),
        final_value=float(last["value"]),
    )
