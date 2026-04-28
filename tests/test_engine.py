"""Engine unit tests — invariants that MUST hold for any DCA simulation.

These prevent the class of bugs found in the previous hardcoded backtest
(e.g., BTC accumulation decreasing over time).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import numpy as np
import pandas as pd
from data_loader import load_btc_thb
from engine import (
    BacktestResult,
    add_indicators,
    run_dca,
    DEFAULT_FEE,
    SMA_20W_DAYS,
)
from metrics import compute_metrics


# ──────────────────────────────────────────────────────────
# Fixture: small synthetic price series for deterministic tests
# ──────────────────────────────────────────────────────────
def synthetic_prices(n_days=300, start_price=1_000_000, daily_drift=0.001):
    """Generate deterministic price series with mild upward drift."""
    rng = np.random.default_rng(42)
    rets = rng.normal(daily_drift, 0.02, n_days)
    prices = start_price * np.exp(np.cumsum(rets))
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    return pd.DataFrame({
        "date": dates,
        "ts": dates.astype("int64") // 10**9,
        "o": prices, "h": prices * 1.01, "l": prices * 0.99,
        "c": prices, "v": np.ones(n_days) * 100.0,
    })


# ──────────────────────────────────────────────────────────
# INVARIANT TESTS — these must hold or the engine is broken
# ──────────────────────────────────────────────────────────
def test_btc_monotonic_increasing():
    """The bug from the old backtest: BTC must NEVER decrease in DCA."""
    df = synthetic_prices()
    df = add_indicators(df)
    for strat in ["flat", "sma2x", "mayer", "bollinger3"]:
        r = run_dca(df, strategy=strat, daily_amount=1000)
        eq = r.equity["btc"]
        diffs = eq.diff().dropna()
        assert (diffs >= 0).all(), \
            f"[{strat}] BTC decreased on {(diffs < 0).sum()} days"


def test_invested_monotonic_increasing():
    """Invested amount should never decrease (we never sell)."""
    df = synthetic_prices()
    df = add_indicators(df)
    for strat in ["flat", "sma2x", "mayer", "bollinger3"]:
        r = run_dca(df, strategy=strat)
        diffs = r.equity["invested"].diff().dropna()
        assert (diffs >= 0).all(), f"[{strat}] invested decreased"


def test_fees_correctly_deducted():
    """Verify fee accounting: invested = sum(gross), btc = sum(net)/price."""
    df = synthetic_prices(n_days=10)
    df = add_indicators(df)
    r = run_dca(df, strategy="flat", daily_amount=1000, fee_rate=0.0025)
    expected_invested = sum(t.gross_thb for t in r.trades)
    expected_fees = sum(t.fee_thb for t in r.trades)
    assert abs(r.total_invested - expected_invested) < 1e-6
    assert abs(r.total_fees - expected_fees) < 1e-6
    # Each trade: net + fee = gross
    for t in r.trades:
        assert abs((t.net_thb + t.fee_thb) - t.gross_thb) < 1e-6
        assert abs(t.fee_thb - t.gross_thb * 0.0025) < 1e-6


def test_flat_dca_invested_is_exact():
    """For flat DCA, invested = daily_amount × n_days exactly."""
    df = synthetic_prices(n_days=100)
    r = run_dca(df, strategy="flat", daily_amount=1000)
    assert r.total_invested == 1000 * 100
    assert len(r.trades) == 100


def test_zero_fee_means_btc_x_price_eq_invested():
    """With fee=0, total invested should buy BTC at avg cost."""
    df = synthetic_prices(n_days=50)
    r = run_dca(df, strategy="flat", daily_amount=1000, fee_rate=0.0)
    # Sum of (gross / price) = btc
    expected_btc = sum(t.gross_thb / t.price for t in r.trades)
    assert abs(r.final_btc - expected_btc) < 1e-9


def test_lumpsum_invests_only_on_day_one():
    """Lump-sum strategy invests once on day 1, then 0 forever."""
    df = synthetic_prices(n_days=50)
    r = run_dca(
        df, strategy="lumpsum", daily_amount=0,
        extra_params={"lump_total_thb": 50_000},
    )
    assert len(r.trades) == 1
    assert r.trades[0].gross_thb == 50_000
    assert r.total_invested == 50_000


def test_sma2x_buys_more_below_sma():
    """SMA-2x: total invested should be > flat × n_days when below SMA exists."""
    # Force a price drop after SMA warm-up
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    prices = np.concatenate([
        np.linspace(1_000_000, 2_000_000, 140),  # warmup uptrend
        np.linspace(2_000_000, 800_000, 60),     # then crash below SMA
    ])
    df = pd.DataFrame({
        "date": dates, "ts": dates.astype("int64") // 10**9,
        "o": prices, "h": prices, "l": prices, "c": prices,
        "v": np.ones(n) * 100,
    })
    df = add_indicators(df)
    r_flat = run_dca(df, strategy="flat", daily_amount=1000)
    r_sma = run_dca(df, strategy="sma2x", daily_amount=1000)
    # SMA-2x must invest at least as much as flat (and more if crash hit)
    assert r_sma.total_invested > r_flat.total_invested


def test_metrics_roi_consistency():
    """ROI from result == (value - invested) / invested."""
    df = synthetic_prices()
    df = add_indicators(df)
    r = run_dca(df, strategy="flat")
    m = compute_metrics(r)
    expected = (r.final_value - r.total_invested) / r.total_invested
    assert abs(m.roi - expected) < 1e-9


def test_max_drawdown_is_nonneg_and_lt_1():
    df = synthetic_prices(n_days=500)
    df = add_indicators(df)
    r = run_dca(df, strategy="flat")
    m = compute_metrics(r)
    assert 0.0 <= m.max_drawdown <= 1.0


def test_no_trades_when_warmup_skipped():
    """Mayer strategy waits for SMA200 — first 199 days falls back to 1x flat."""
    df = synthetic_prices(n_days=10)  # very short, no SMA available
    df = add_indicators(df)
    r = run_dca(df, strategy="mayer", daily_amount=1000)
    # Falls back to 1x → 10 trades × 1000 = 10000
    assert r.total_invested == 10000


# ──────────────────────────────────────────────────────────
# REAL DATA TEST — run against actual Bitkub data
# ──────────────────────────────────────────────────────────
def test_real_data_5y_flat_runs_clean():
    """End-to-end: 5y flat DCA on real Bitkub data."""
    ps = load_btc_thb()
    df = add_indicators(ps.df)
    r = run_dca(df, strategy="flat", daily_amount=1000)
    m = compute_metrics(r)
    # Sanity bounds
    assert 1825 <= len(r.trades) <= 1830
    assert 1_800_000 <= r.total_invested <= 1_850_000
    assert r.final_btc > 0.5  # at least half a BTC accumulated
    # ROI should be positive over 5y given BTC went up
    assert m.roi > 0
    # Print for visual cross-check
    print(f"\n  5y Flat DCA on real data:")
    print(f"  invested ฿{r.total_invested:,.0f}, value ฿{r.final_value:,.0f}, "
          f"BTC {r.final_btc:.4f}, ROI {m.roi:.2%}")


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(0 if failed == 0 else 1)
