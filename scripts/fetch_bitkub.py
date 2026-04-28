"""Fetch BTC/THB daily OHLC from Bitkub TradingView endpoint.

Output: data/btc_thb_daily.json with schema:
{
  "source": "bitkub",
  "symbol": "BTC_THB",
  "resolution": "1D",
  "fetched_at": "2026-04-28T...",
  "range": {"from": "...", "to": "..."},
  "bars": [
    {"date": "YYYY-MM-DD", "ts": <unix>, "o": ..., "h": ..., "l": ..., "c": ..., "v": ...},
    ...
  ]
}
"""
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

BITKUB_TV = "https://api.bitkub.com/tradingview/history"
SYMBOL = "BTC_THB"
RESOLUTION = "1D"
YEARS_BACK = 5

OUT = Path(__file__).resolve().parent.parent / "data" / "btc_thb_daily.json"


def fetch(symbol: str, resolution: str, ts_from: int, ts_to: int) -> dict:
    r = requests.get(
        BITKUB_TV,
        params={"symbol": symbol, "resolution": resolution, "from": ts_from, "to": ts_to},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    now = int(time.time())
    ts_from = now - YEARS_BACK * 365 * 86400

    print(f"[bitkub] fetching {SYMBOL} resolution={RESOLUTION}")
    print(f"[bitkub] range: {datetime.fromtimestamp(ts_from, timezone.utc):%Y-%m-%d} to {datetime.fromtimestamp(now, timezone.utc):%Y-%m-%d}")

    raw = fetch(SYMBOL, RESOLUTION, ts_from, now)
    if raw.get("s") != "ok" and not raw.get("t"):
        print(f"[bitkub] ERROR: API returned status={raw.get('s')}", file=sys.stderr)
        return 1

    ts = raw["t"]
    o, h, l, c, v = raw["o"], raw["h"], raw["l"], raw["c"], raw["v"]
    n = len(ts)
    if not (n == len(o) == len(h) == len(l) == len(c) == len(v)):
        print(f"[bitkub] ERROR: array length mismatch", file=sys.stderr)
        return 2

    bars_raw = []
    for i in range(n):
        d = datetime.fromtimestamp(ts[i], timezone.utc)
        bars_raw.append({
            "date": d.strftime("%Y-%m-%d"),
            "ts": ts[i],
            "o": float(o[i]),
            "h": float(h[i]),
            "l": float(l[i]),
            "c": float(c[i]),
            "v": float(v[i]),
        })

    # Dedupe: Bitkub occasionally returns 2 bars for the same date
    # (e.g. 2024-01-31, 2024-02-01, 2025-04-25). Keep the one with higher
    # volume = more complete daily aggregation.
    by_date = {}
    duplicates_log = []
    for b in bars_raw:
        existing = by_date.get(b["date"])
        if existing is None:
            by_date[b["date"]] = b
        else:
            duplicates_log.append({"date": b["date"], "kept_v": max(existing["v"], b["v"]),
                                   "dropped_v": min(existing["v"], b["v"])})
            if b["v"] > existing["v"]:
                by_date[b["date"]] = b
    bars = sorted(by_date.values(), key=lambda x: x["ts"])
    if duplicates_log:
        print(f"[bitkub] deduped {len(duplicates_log)} duplicate date(s):")
        for d in duplicates_log:
            print(f"         {d['date']}: kept v={d['kept_v']:.2f}, dropped v={d['dropped_v']:.2f}")

    payload = {
        "source": "bitkub",
        "endpoint": BITKUB_TV,
        "symbol": SYMBOL,
        "resolution": RESOLUTION,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "range": {
            "from": bars[0]["date"],
            "to": bars[-1]["date"],
            "from_ts": ts_from,
            "to_ts": now,
        },
        "raw_count": n,
        "count": len(bars),
        "deduplicated": duplicates_log,
        "bars": bars,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"[bitkub] wrote {n} bars to {OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT} ({size_mb:.2f} MB)")
    print(f"[bitkub] first: {bars[0]['date']} close={bars[0]['c']:,.2f}")
    print(f"[bitkub] last:  {bars[-1]['date']} close={bars[-1]['c']:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
