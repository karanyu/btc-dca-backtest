"""Smoke tests for Phase 1 data deliverable.

Run: .venv/bin/python -m pytest tests/ -v
or:  .venv/bin/python tests/test_data_integrity.py
"""
import sys
from pathlib import Path

# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pandas as pd
from data_loader import load_btc_thb


def test_loads_without_error():
    ps = load_btc_thb()
    assert len(ps) > 0


def test_dates_unique_and_sorted():
    ps = load_btc_thb()
    assert ps.df["date"].is_unique
    assert ps.df["date"].is_monotonic_increasing


def test_continuous_daily():
    ps = load_btc_thb()
    diffs = ps.df["date"].diff().dropna()
    assert (diffs == pd.Timedelta(days=1)).all(), \
        f"Found non-1-day gaps: {diffs[diffs != pd.Timedelta(days=1)].head()}"


def test_prices_positive():
    ps = load_btc_thb()
    for col in ["o", "h", "l", "c"]:
        assert (ps.df[col] > 0).all(), f"Non-positive {col} found"


def test_high_ge_low():
    ps = load_btc_thb()
    assert (ps.df["h"] >= ps.df["l"]).all()


def test_price_range_sanity():
    """BTC/THB never went below 100k or above 10M in 2021-2026."""
    ps = load_btc_thb()
    assert ps.df["c"].min() > 100_000, f"Suspiciously low price: {ps.df['c'].min()}"
    assert ps.df["c"].max() < 10_000_000, f"Suspiciously high price: {ps.df['c'].max()}"


def test_no_extreme_gaps():
    """No single-day move > 30% (sanity)."""
    ps = load_btc_thb()
    rets = ps.df["c"].pct_change().dropna().abs()
    assert rets.max() < 0.30, f"Extreme move detected: {rets.max():.2%}"


def test_slice_works():
    ps = load_btc_thb()
    sub = ps.slice("2024-01-01", "2024-01-31")
    assert len(sub) == 31
    assert sub.df["date"].iloc[0] == pd.Timestamp("2024-01-01")
    assert sub.df["date"].iloc[-1] == pd.Timestamp("2024-01-31")


def test_5y_coverage():
    """Verify ≥ 1825 days (5 years) of data."""
    ps = load_btc_thb()
    span = (ps.df["date"].iloc[-1] - ps.df["date"].iloc[0]).days
    assert span >= 1820, f"Coverage too short: {span} days"


if __name__ == "__main__":
    tests = [
        test_loads_without_error,
        test_dates_unique_and_sorted,
        test_continuous_daily,
        test_prices_positive,
        test_high_ge_low,
        test_price_range_sanity,
        test_no_extreme_gaps,
        test_slice_works,
        test_5y_coverage,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(0 if failed == 0 else 1)
