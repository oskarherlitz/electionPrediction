"""ONLINE refresh: discover Kalshi 2026 markets, reconstruct November-1 prices,
and write normalized odds tables. Caches every raw response under data/cache/
so the offline build reproduces identical results.

Usage:
    python scripts/refresh.py senate
    python scripts/refresh.py house
    python scripts/refresh.py all

Separate from the offline build on purpose (source refresh vs. offline run).
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forecast import kalshi
from forecast.races import SENATE_SERIES, event_is_2026, party_for

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

ODDS_FIELDS = [
    "race_id", "chamber", "candidate_name", "party", "market_ticker",
    "series_ticker", "event_ticker", "p", "yes_bid", "yes_ask", "trade_close",
    "price_source", "candle_end_utc", "staleness_hours", "volume", "open_interest",
    "n_candles", "note",
]


def _active_general_markets(event: dict) -> list[dict]:
    """Markets still contesting the general election (exclude finalized primary
    losers). Keep markets with status 'active' or any with a post-2026 close."""
    out = []
    for m in event.get("markets", []):
        status = (m.get("status") or "").lower()
        close = (m.get("close_time") or "")
        if status in ("active", "initialized") or close >= "2026-11-04":
            out.append(m)
    return out


def refresh_senate(offline: bool = False) -> list[dict]:
    rows = []
    for race_id, series_list in SENATE_SERIES.items():
        chosen_event = None
        chosen_series = None
        for series in series_list:
            try:
                events = kalshi.get_events(series, offline=offline)
            except Exception as e:  # noqa: BLE001
                print(f"  [{race_id}] series {series} error: {e}")
                continue
            cands = [e for e in events if event_is_2026(e)]
            # prefer the event with the most active markets / volume
            cands.sort(key=lambda e: len(_active_general_markets(e)), reverse=True)
            if cands:
                chosen_event, chosen_series = cands[0], series
                break
        if chosen_event is None:
            rows.append({"race_id": race_id, "chamber": "Senate", "note": "NO_MARKET_FOUND"})
            print(f"  [{race_id}] NO MARKET FOUND (tried {series_list})")
            continue
        et = chosen_event.get("event_ticker")
        mkts = _active_general_markets(chosen_event)
        print(f"  [{race_id}] {chosen_series} / {et}: {len(mkts)} active markets")
        for m in mkts:
            mt = m.get("ticker")
            name = m.get("yes_sub_title") or m.get("subtitle") or ""
            party = party_for(mt, name)
            rec = kalshi.reconstruct_nov1_price(chosen_series, mt, offline=offline)
            rows.append({
                "race_id": race_id, "chamber": "Senate", "candidate_name": name,
                "party": party or "", "market_ticker": mt,
                "series_ticker": chosen_series, "event_ticker": et,
                "p": rec["p"], "yes_bid": rec.get("yes_bid"), "yes_ask": rec.get("yes_ask"),
                "trade_close": rec.get("trade_close"), "price_source": rec["source"],
                "candle_end_utc": rec["candle_end_utc"], "staleness_hours": rec["staleness_hours"],
                "volume": rec.get("volume"), "open_interest": rec.get("open_interest"),
                "n_candles": rec["n_candles"],
                "note": "" if party else "PARTY_UNKNOWN",
            })
    return rows


def _house_template_ids() -> list[str]:
    import csv as _csv
    p = os.path.join(DATA, "templates", "full_congress_template.csv")
    return [r["race_id"] for r in _csv.DictReader(open(p)) if r.get("chamber") == "House"]


def _individual_series_candidates(rid: str) -> list[str]:
    """Prioritized individual-series tickers for a House district id (XX-NN/XX-AL).

    Kalshi uses inconsistent spellings (HOUSEAZ1 vs KXHOUSEUT01 vs HOUSENJ9 vs
    HOUSENJ09). We try both prefixes, zero-padded and unpadded, plus specials.
    """
    st, dist = rid.split("-")
    out = []
    if dist == "AL":
        for pref in ("HOUSE", "KXHOUSE"):
            out += [f"{pref}{st}AL"]
    else:
        n = int(dist)
        for pref in ("HOUSE", "KXHOUSE"):
            out += [f"{pref}{st}{n}", f"{pref}{st}{dist}",
                    f"{pref}{st}{n}S", f"{pref}{st}{dist}S"]
    return list(dict.fromkeys(out))


def _emit_market_rows(rid, series, event, offline):
    rows = []
    et = event.get("event_ticker")
    for m in _active_general_markets(event):
        mt = m.get("ticker")
        name = m.get("yes_sub_title") or ""
        party = party_for(mt, name)
        rec = kalshi.reconstruct_nov1_price(series, mt, offline=offline)
        rows.append({
            "race_id": rid, "chamber": "House", "candidate_name": name,
            "party": party or "", "market_ticker": mt, "series_ticker": series,
            "event_ticker": et, "p": rec["p"], "yes_bid": rec.get("yes_bid"),
            "yes_ask": rec.get("yes_ask"), "trade_close": rec.get("trade_close"),
            "price_source": rec["source"], "candle_end_utc": rec["candle_end_utc"],
            "staleness_hours": rec["staleness_hours"], "volume": rec.get("volume"),
            "open_interest": rec.get("open_interest"), "n_candles": rec["n_candles"],
            "note": "" if party else "PARTY_UNKNOWN",
        })
    return rows


def refresh_house(offline: bool = False) -> list[dict]:
    """Discover House 2026 markets: the omnibus KXHOUSERACE series plus, for any
    template district it does not cover, the individual per-district series."""
    rows = []
    covered = set()
    events = kalshi.get_events("KXHOUSERACE", offline=offline)
    print(f"  KXHOUSERACE events: {len(events)}")
    for e in events:
        sub = (e.get("sub_title") or "").strip().upper()  # e.g. 'WY-AL', 'AL-01'
        if not sub or not event_is_2026(e):
            continue
        new = _emit_market_rows(sub, "KXHOUSERACE", e, offline)
        if new:
            covered.add(sub)
            rows.extend(new)

    missing = [r for r in _house_template_ids() if r not in covered]
    print(f"  omnibus covered {len(covered)}; probing {len(missing)} via individual series")
    for rid in missing:
        found = False
        for series in _individual_series_candidates(rid):
            try:
                evs = kalshi.get_events(series, offline=offline)
            except Exception:  # noqa: BLE001
                continue
            cands = [e for e in evs if event_is_2026(e) and _active_general_markets(e)]
            if cands:
                cands.sort(key=lambda e: len(_active_general_markets(e)), reverse=True)
                new = _emit_market_rows(rid, series, cands[0], offline)
                if new:
                    rows.extend(new)
                    found = True
                    print(f"    [{rid}] {series}: {len(new)} markets")
                    break
        if not found:
            rows.append({"race_id": rid, "chamber": "House", "note": "NO_MARKET_FOUND"})
            print(f"    [{rid}] NO MARKET FOUND")
    return rows


def write_odds(rows: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ODDS_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in ODDS_FIELDS})
    os.replace(tmp, path)
    print(f"  wrote {len(rows)} rows -> {path}")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "senate"
    offline = "--offline" in sys.argv
    if which in ("senate", "all"):
        print("Refreshing SENATE...")
        write_odds(refresh_senate(offline), os.path.join(DATA, "reconstructed_odds_senate.csv"))
    if which in ("house", "all"):
        print("Refreshing HOUSE...")
        write_odds(refresh_house(offline), os.path.join(DATA, "reconstructed_odds_house.csv"))


if __name__ == "__main__":
    main()
