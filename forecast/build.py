"""OFFLINE build: assemble races from reconstructed odds, estimate q, run the
expected-points optimizer, and export submission CSVs + audit.

Two selection strategies per race:
  * recommended  : pick = argmax_c q(c) * reward(p(c))   (score-based)
  * most_likely  : pick = argmax_c q(c)                  (transparency)

q model (baseline): market-only. Within a race, q(c) = p(c) / sum_j p(j) so that
per-race probabilities sum to one (the raw p is preserved for reward()). An
optional fundamentals blend can override q via a supplied column.
"""
from __future__ import annotations

import csv
import math
import os
from collections import OrderedDict, defaultdict

from forecast.scoring import (
    Candidate, expected_points, is_valid_price, pick_expected_points,
    pick_most_likely, reward,
)
from forecast.races import party_for

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "outputs")
SUBMISSION_HEADER = ["race_id", "chamber", "predicted_winner_party",
                     "candidate_name", "win_probability"]


def _f(x):
    if x is None or x == "":
        return None
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def read_template_order(path: str) -> "OrderedDict[str, str]":
    """Return race_id -> chamber in exact template order."""
    order = OrderedDict()
    with open(path, newline="") as fh:
        r = csv.DictReader(fh)
        # strip a possible artificial leading index column
        for row in r:
            rid = (row.get("race_id") or "").strip()
            if not rid:
                continue
            order[rid] = (row.get("chamber") or "").strip()
    return order


def read_odds(path: str) -> "dict[str, list[dict]]":
    races = defaultdict(list)
    if not os.path.exists(path):
        return races
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            rid = (row.get("race_id") or "").strip()
            if rid:
                races[rid].append(row)
    return races


def build_candidates(rows: list[dict], blend_w: float = 0.0,
                     fundamentals: dict | None = None,
                     q_latest: dict | None = None) -> list[Candidate]:
    """Construct Candidate objects. ``p`` is always the November-1 benchmark price
    (drives reward). ``q`` is the forecast: the normalised *latest pre-election*
    price when ``q_latest`` (ticker -> latest price) is supplied, else the
    normalised Nov-1 price. An optional fundamentals blend can adjust q.
    """
    cands = []
    total_p = sum(p for p in (_f(r.get("p")) for r in rows) if is_valid_price(p))
    # q anchor prices: latest snapshot if available, else Nov-1
    def q_price(r):
        if q_latest is not None:
            v = q_latest.get(r.get("market_ticker"))
            if is_valid_price(v):
                return float(v)
        return _f(r.get("p"))
    total_q = sum(v for v in (q_price(r) for r in rows) if is_valid_price(v))
    for r in rows:
        name = (r.get("candidate_name") or "").strip()
        if not name:
            continue
        p = _f(r.get("p"))
        priced = is_valid_price(p)
        qp = q_price(r)
        base = total_q if (total_q and total_q > 0) else total_p
        qm = (qp / base) if (is_valid_price(qp) and base and base > 0) else (qp if is_valid_price(qp) else 0.0)
        qf = None
        if fundamentals:
            qf = fundamentals.get((r.get("race_id"), name))
        if blend_w > 0 and qf is not None:
            q = (1 - blend_w) * qm + blend_w * qf
        else:
            q = qm
        party = (r.get("party") or "").strip()
        if not party:  # backfill from the current lookup without re-refreshing
            party = party_for(r.get("market_ticker") or "", name) or ""
        cands.append(Candidate(name=name, party=party,
                               p=p if priced else None, q=q,
                               ticker=(r.get("market_ticker") or ""),
                               priced=priced))
    # Drop stray unknown-party contracts (non-canonical / primary person markets)
    # when the race already offers canonical D and R outcomes. This avoids
    # double-counting in the q normalisation and prevents picking an unlabelled
    # contract. Legitimate independents keep an explicit party and are not dropped.
    parties = {c.party for c in cands if c.priced}
    if "D" in parties and "R" in parties and any(not c.party for c in cands):
        cands = [c for c in cands if c.party]

    # renormalise q within race to sum to 1 (defensive)
    sq = sum(c.q for c in cands)
    if sq and sq > 0:
        for c in cands:
            c.q = c.q / sq
    return cands


def build_track(template_path: str, odds_path: str, fallbacks: dict | None = None,
                blend_w: float = 0.0, fundamentals: dict | None = None,
                q_latest: dict | None = None, strategy: str = "ev", tau: float = 0.0):
    """Return (recommended_rows, most_likely_rows, audit_rows, stats).

    strategy: 'ev' (argmax q*reward(p)), 'favorite' (argmax q), or
    'threshold' (EV pick unless its q < tau, then favorite).
    """
    from forecast.scoring import pick_threshold
    order = read_template_order(template_path)
    odds = read_odds(odds_path)
    fallbacks = fallbacks or {}
    rec_rows, ml_rows, audit = [], [], []
    stats = {"n_races": 0, "n_priced_races": 0, "n_fallback": 0,
             "rec_favorite": 0, "rec_underdog": 0, "ev_priced_sum": 0.0,
             "n_rec_priced": 0}

    for rid, chamber in order.items():
        stats["n_races"] += 1
        rows = odds.get(rid, [])
        cands = build_candidates(rows, blend_w=blend_w, fundamentals=fundamentals,
                                 q_latest=q_latest)
        priced_cands = [c for c in cands if c.priced]
        note = ""

        if not cands:
            # No market and no candidate rows: use a documented fallback roster.
            fb = fallbacks.get(rid)
            if fb is None:
                note = "NO_MARKET_NO_FALLBACK"
                rec_pick = Candidate(name="UNKNOWN", party="", p=None, q=0.0, priced=False)
                ml_pick = rec_pick
            else:
                note = "FALLBACK_NO_MARKET"
                fq = float(fb.get("q", 0.9))
                rec_pick = Candidate(name=fb["candidate_name"], party=fb["party"],
                                     p=None, q=fq, priced=False)
                ml_pick = rec_pick
            stats["n_fallback"] += 1
        else:
            if priced_cands:
                stats["n_priced_races"] += 1
            else:
                note = "UNPRICED_FALLBACK_BEST_Q"
                stats["n_fallback"] += 1
            if strategy == "favorite":
                rec_pick = pick_most_likely(cands)
            elif strategy == "threshold":
                rec_pick = pick_threshold(cands, tau)
            else:
                rec_pick = pick_expected_points(cands)
            ml_pick = pick_most_likely(cands)

        # win_probability = the SELECTED candidate's model probability q
        rec_wp = round(float(rec_pick.q), 6)
        ml_wp = round(float(ml_pick.q), 6)

        rec_rows.append([rid, chamber, rec_pick.party, rec_pick.name, f"{rec_wp:.6f}"])
        ml_rows.append([rid, chamber, ml_pick.party, ml_pick.name, f"{ml_wp:.6f}"])

        # audit + stats on the recommended pick
        is_fav = (rec_pick.name == ml_pick.name)
        rec_ev = None
        if rec_pick.priced and is_valid_price(rec_pick.p):
            rec_ev = expected_points(rec_pick.q, rec_pick.p)
            stats["ev_priced_sum"] += rec_ev
            stats["n_rec_priced"] += 1
            if is_fav:
                stats["rec_favorite"] += 1
            else:
                stats["rec_underdog"] += 1

        audit.append({
            "race_id": rid, "chamber": chamber,
            "n_candidates": len(cands),
            "rec_candidate": rec_pick.name, "rec_party": rec_pick.party,
            "rec_p": "" if rec_pick.p is None else f"{rec_pick.p:.4f}",
            "rec_q": f"{rec_pick.q:.4f}",
            "rec_reward": "" if (rec_pick.p is None or not is_valid_price(rec_pick.p)) else f"{reward(rec_pick.p):.4f}",
            "rec_expected_points": "" if rec_ev is None else f"{rec_ev:.4f}",
            "ml_candidate": ml_pick.name, "ml_party": ml_pick.party,
            "ml_q": f"{ml_pick.q:.4f}",
            "pick_type": "favorite" if is_fav else "underdog",
            "differs": "" if is_fav else "YES",
            "ticker": rec_pick.ticker, "note": note,
        })
    return rec_rows, ml_rows, audit, stats


def write_submission(rows: list[list], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(SUBMISSION_HEADER)
        w.writerows(rows)
    os.replace(tmp, path)


def write_audit(audit: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = ["race_id", "chamber", "n_candidates", "rec_candidate", "rec_party",
              "rec_p", "rec_q", "rec_reward", "rec_expected_points",
              "ml_candidate", "ml_party", "ml_q", "pick_type", "differs",
              "ticker", "note"]
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(audit)
    os.replace(tmp, path)
