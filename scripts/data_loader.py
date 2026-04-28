"""Data loader — used by Phase 2 backtest engine.

Provides clean pandas DataFrame interface to BTC/THB daily series.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "data" / "btc_thb_daily.json"


@dataclass
class PriceSeries:
    """BTC/THB daily price series with metadata."""
    df: pd.DataFrame
    source: str
    symbol: str
    resolution: str
    fetched_at: str

    def __len__(self) -> int:
        return len(self.df)

    def slice(self, start: str | pd.Timestamp, end: str | pd.Timestamp) -> "PriceSeries":
        """Return a new PriceSeries restricted to [start, end] inclusive."""
        s = pd.Timestamp(start)
        e = pd.Timestamp(end)
        sub = self.df[(self.df["date"] >= s) & (self.df["date"] <= e)].reset_index(drop=True)
        return PriceSeries(df=sub, source=self.source, symbol=self.symbol,
                           resolution=self.resolution, fetched_at=self.fetched_at)


def load_btc_thb(path: Optional[Path] = None) -> PriceSeries:
    """Load the cached BTC/THB daily series.

    Returns a PriceSeries with columns: date (datetime64), o, h, l, c, v.
    Sorted by date, deduplicated, daily-continuous.
    """
    src = path or DEFAULT_SRC
    if not src.exists():
        raise FileNotFoundError(
            f"Data file not found: {src}. "
            f"Run scripts/fetch_bitkub.py first to populate it."
        )
    payload = json.loads(src.read_text())
    df = pd.DataFrame(payload["bars"])
    df["date"] = pd.to_datetime(df["date"])
    df = df[["date", "ts", "o", "h", "l", "c", "v"]].sort_values("date").reset_index(drop=True)

    # Sanity assertions (cheap)
    assert df["date"].is_unique, "Duplicate dates in dataset — refetch required"
    assert df["date"].is_monotonic_increasing, "Dates not sorted"
    assert (df[["o", "h", "l", "c"]] > 0).all().all(), "Non-positive prices found"

    return PriceSeries(
        df=df,
        source=payload["source"],
        symbol=payload["symbol"],
        resolution=payload["resolution"],
        fetched_at=payload["fetched_at"],
    )


if __name__ == "__main__":
    ps = load_btc_thb()
    print(f"Loaded {len(ps)} bars from {ps.source} ({ps.symbol}@{ps.resolution})")
    print(f"Range: {ps.df['date'].iloc[0].date()} → {ps.df['date'].iloc[-1].date()}")
    print(f"\nFirst 3 bars:")
    print(ps.df.head(3).to_string(index=False))
    print(f"\nLast 3 bars:")
    print(ps.df.tail(3).to_string(index=False))

    # Demo slice
    print(f"\nDemo slice 2024-01-01 to 2024-01-31:")
    jan24 = ps.slice("2024-01-01", "2024-01-31")
    print(f"  {len(jan24)} bars, mean close ฿{jan24.df['c'].mean():,.2f}")
