"""ONLINE: pull the LATEST pre-election market snapshot to use as the forecast q,
keeping p fixed at the November-1 benchmark. The competition grades picks with
reward(p) at the Nov-1 price, but our FORECAST may use strictly more informed
pre-election information. q and p are kept distinct (different timestamps).

Reads the tickers already discovered in data/reconstructed_odds_{senate,house}.csv
and writes data/q_snapshot.csv keyed by market_ticker.

Usage: python scripts/refresh_q.py [--offline]
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from forecast import kalshi  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FIELDS = ["market_ticker", "series_ticker", "q_price", "q_yes_bid", "q_yes_ask",
          "q_source", "q_candle_end_utc", "q_staleness_hours", "q_volume"]


def main():
    offline = "--offline" in sys.argv
    now = dt.datetime.now(dt.timezone.utc)
    seen = {}
    for track in ("senate", "house"):
        p = os.path.join(DATA, f"reconstructed_odds_{track}.csv")
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p)):
            mt, st = r.get("market_ticker"), r.get("series_ticker")
            if mt and st:
                seen[mt] = st
    print(f"pulling latest snapshot for {len(seen)} markets at {now.isoformat()}")
    rows = []
    for i, (mt, st) in enumerate(seen.items()):
        rec = kalshi.reconstruct_nov1_price(st, mt, cutoff_utc=now, window_hours=72,
                                            offline=offline)
        rows.append({
            "market_ticker": mt, "series_ticker": st, "q_price": rec["p"],
            "q_yes_bid": rec.get("yes_bid"), "q_yes_ask": rec.get("yes_ask"),
            "q_source": rec["source"], "q_candle_end_utc": rec["candle_end_utc"],
            "q_staleness_hours": rec["staleness_hours"], "q_volume": rec.get("volume"),
        })
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(seen)}")
    out = os.path.join(DATA, "q_snapshot.csv")
    tmp = out + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, out)
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
