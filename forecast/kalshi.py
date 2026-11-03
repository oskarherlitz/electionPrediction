"""Minimal, cached Kalshi public-API client for reproducible reconstruction.

Design goals:
* Every raw response is written to ``data/cache/`` so the offline build can run
  without network access and reproduce identical picks.
* Price reconstruction uses a single documented convention (see
  ``reconstruct_nov1_price``): the yes_bid/yes_ask midpoint from the latest
  completed hourly candle ending at or before the cutoff instant.

This implementation was written independently from public API docs; it does not
copy third-party code. Endpoints verified against docs.kalshi.com on 2026-11-02.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import os
import ssl
import time
import urllib.request
import urllib.error

# macOS system Python often lacks a usable CA store for urllib; prefer certifi.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover - last-resort for public read-only data
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")

# America/New_York is UTC-5 on 2026-11-01 (standard time began Nov 1 2026 02:00).
# The cutoff is 2026-11-01 23:59:59 America/New_York == 2026-11-02 04:59:59 UTC.
NOV1_CUTOFF_UTC = dt.datetime(2026, 11, 2, 4, 59, 59, tzinfo=dt.timezone.utc)


def _utc_ts(d: dt.datetime) -> int:
    return calendar.timegm(d.utctimetuple())


def _cache_path(subdir: str, key: str) -> str:
    safe = key.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-")
    d = os.path.join(CACHE_DIR, subdir)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, safe + ".json")


def _get(url: str, subdir: str, key: str, use_cache: bool, offline: bool,
         retries: int = 3, pause: float = 0.25):
    path = _cache_path(subdir, key)
    if use_cache and os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    if offline:
        raise FileNotFoundError(f"offline mode but no cache for {key} ({path})")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "model-citizens-2026/1.0"})
            with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
                data = json.loads(resp.read().decode())
            tmp = path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(data, fh)
            os.replace(tmp, path)
            time.sleep(pause)
            return data
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(pause * (attempt + 1) * 2)
    raise RuntimeError(f"GET failed for {url}: {last}")


def get_events(series_ticker: str, offline: bool = False, use_cache: bool = True) -> list[dict]:
    """Return all events for a series, paginating via cursor."""
    out, cursor = [], ""
    page = 0
    while True:
        url = f"{BASE}/events?series_ticker={series_ticker}&limit=200&with_nested_markets=true"
        if cursor:
            url += f"&cursor={cursor}"
        data = _get(url, "events", f"{series_ticker}_p{page}", use_cache, offline)
        out.extend(data.get("events", []))
        cursor = data.get("cursor", "")
        page += 1
        if not cursor:
            break
    return out


def get_event(event_ticker: str, offline: bool = False, use_cache: bool = True) -> dict:
    url = f"{BASE}/events/{event_ticker}?with_nested_markets=true"
    data = _get(url, "events", f"event_{event_ticker}", use_cache, offline)
    return data.get("event", data)


def get_candles(series_ticker: str, market_ticker: str, start_ts: int, end_ts: int,
                period: int = 60, offline: bool = False, use_cache: bool = True) -> list[dict]:
    url = (f"{BASE}/series/{series_ticker}/markets/{market_ticker}/candlesticks"
           f"?start_ts={start_ts}&end_ts={end_ts}&period_interval={period}")
    key = f"{market_ticker}_{start_ts}_{end_ts}_{period}"
    data = _get(url, "candles", key, use_cache, offline)
    return data.get("candlesticks", [])


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def reconstruct_nov1_price(series_ticker: str, market_ticker: str,
                           cutoff_utc: dt.datetime = NOV1_CUTOFF_UTC,
                           window_hours: int = 72, offline: bool = False,
                           use_cache: bool = True) -> dict:
    """Reconstruct the November-1 benchmark YES price for one market.

    Convention: take the latest *completed* hourly candle whose period end is at
    or before the cutoff, and use the midpoint of its closing yes_bid / yes_ask.
    Falls back to the close trade price if a bid/ask side is missing. Returns a
    dict with the price plus provenance (UTC candle endpoint, staleness, source).
    """
    end_ts = _utc_ts(cutoff_utc)
    start_ts = end_ts - window_hours * 3600
    candles = get_candles(series_ticker, market_ticker, start_ts, end_ts, 60,
                           offline=offline, use_cache=use_cache)
    chosen = None
    for c in candles:  # candles are ascending; keep the last at/<= cutoff
        if c.get("end_period_ts", 0) <= end_ts:
            chosen = c
    if chosen is None:
        return {"p": None, "source": "none", "candle_end_utc": None,
                "staleness_hours": None, "n_candles": len(candles)}
    yb = _f((chosen.get("yes_bid") or {}).get("close_dollars"))
    ya = _f((chosen.get("yes_ask") or {}).get("close_dollars"))
    price_close = _f((chosen.get("price") or {}).get("close_dollars"))
    source = "yes_bid_ask_midpoint"
    if yb is not None and ya is not None:
        p = (yb + ya) / 2.0
    elif price_close is not None:
        p, source = price_close, "trade_close"
    elif yb is not None:
        p, source = yb, "yes_bid_only"
    elif ya is not None:
        p, source = ya, "yes_ask_only"
    else:
        p, source = None, "empty_candle"
    cend = chosen.get("end_period_ts")
    staleness = round((end_ts - cend) / 3600.0, 2) if cend else None
    return {
        "p": p,
        "yes_bid": yb,
        "yes_ask": ya,
        "trade_close": price_close,
        "source": source,
        "candle_end_utc": dt.datetime.fromtimestamp(cend, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if cend else None,
        "staleness_hours": staleness,
        "n_candles": len(candles),
        "volume": _f(chosen.get("volume_fp")),
        "open_interest": _f(chosen.get("open_interest_fp")),
    }
