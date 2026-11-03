"""Correlated Monte-Carlo evaluation of selection strategies on the 2026 entry.

We treat the forecast q (latest market snapshot, normalised per race) as the
data-generating process, add a shared national swing so race outcomes are
correlated (dependence changes score *variance*, not the additive EV), draw many
elections, and score each strategy's picks with the competition rule using the
fixed November-1 benchmark p for reward.

Reported: mean/median realized points, P(strategy beats the favorite baseline),
and P(strategy is the unique best among the candidate strategies). This targets
P(win), which is what matters for the competition — not just expected points.

A simulation drawn from q cannot prove q is calibrated; this quantifies strategy
risk *given* the market, complementing the out-of-sample 2018 replay.
"""
from __future__ import annotations

import math
import os
import random

from forecast.scoring import reward, is_valid_price
from forecast.build import read_template_order, read_odds, build_candidates

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _logit(p):
    p = min(1 - 1e-6, max(1e-6, p))
    return math.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + math.exp(-x))


def load_entry(template_path, odds_path, q_latest=None):
    """Return list of races: each a list of (name, party, p_nov1, q_forecast)."""
    order = read_template_order(template_path)
    odds = read_odds(odds_path)
    races = []
    for rid, _ in order.items():
        cands = build_candidates(odds.get(rid, []), q_latest=q_latest)
        cands = [c for c in cands if c.priced and is_valid_price(c.p) and c.q > 0]
        if len(cands) >= 2:
            races.append([(c.name, c.party, c.p, c.q) for c in cands])
    return races


# --- selection strategies operate on a race's candidate list ---
def sel_favorite(cs):
    return max(range(len(cs)), key=lambda i: cs[i][3])


def sel_ev(cs):
    return max(range(len(cs)), key=lambda i: cs[i][3] * reward(cs[i][2]))


def sel_threshold(tau):
    def f(cs):
        e, fav = sel_ev(cs), sel_favorite(cs)
        return fav if (e != fav and cs[e][3] < tau) else e
    return f


STRATS = {
    "favorite": sel_favorite,
    "ev(all-underdog)": sel_ev,
    "threshold@0.15": sel_threshold(0.15),
    "threshold@0.25": sel_threshold(0.25),
    "threshold@0.35": sel_threshold(0.35),
}


def _sharpen(q, temp):
    """Sharpen a per-race distribution toward its favorite by exponent `temp`.
    temp=1 leaves q unchanged; temp>1 makes underdogs LESS likely than priced
    (models a market that overstates upsets, the 2018-observed pattern)."""
    w = [qi ** temp for qi in q]
    s = sum(w) or 1.0
    return [wi / s for wi in w]


def simulate(races, n_draws=20000, swing_sd=0.4, seed=20261103, dgp_temp=1.0):
    """swing_sd: sd (in logit points) of a shared national swing applied to the
    Democratic side of every race, inducing correlation across races.
    dgp_temp: >1 sharpens the true DGP toward favorites (tail-overconfidence
    stress); picks are still made on the ORIGINAL q (what the forecaster sees)."""
    rng = random.Random(seed)
    # precompute picks per strategy (fixed across draws)
    picks = {name: [fn(r) for r in races] for name, fn in STRATS.items()}
    totals = {name: [] for name in STRATS}
    # also an "oracle-ish" ev expected (analytic) for cross-check
    analytic_ev = {name: 0.0 for name in STRATS}
    for name in STRATS:
        for ri, r in enumerate(races):
            i = picks[name][ri]
            analytic_ev[name] += r[i][3] * reward(r[i][2])

    for _ in range(n_draws):
        swing = rng.gauss(0, swing_sd)
        scores = {name: 0.0 for name in STRATS}
        for ri, r in enumerate(races):
            # apply correlated swing to D candidates, draw a winner
            adj = []
            for (name_, party, p, q) in r:
                lq = _logit(q) + (swing if party == "D" else (-swing if party == "R" else 0.0))
                adj.append(_sigmoid(lq))
            s = sum(adj) or 1.0
            adj = [a / s for a in adj]
            if dgp_temp != 1.0:
                adj = _sharpen(adj, dgp_temp)
            x = rng.random()
            cum, winner = 0.0, len(r) - 1
            for i, a in enumerate(adj):
                cum += a
                if x <= cum:
                    winner = i
                    break
            for name in STRATS:
                if picks[name][ri] == winner:
                    scores[name] += reward(r[picks[name][ri]][2])
        for name in STRATS:
            totals[name].append(scores[name])

    def pct(xs, q):
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(q * len(xs)))]

    base = totals["favorite"]
    out = {}
    for name in STRATS:
        t = totals[name]
        mean = sum(t) / len(t)
        beats_fav = sum(1 for a, b in zip(t, base) if a > b) / len(t)
        out[name] = {
            "mean": mean, "median": pct(t, 0.5), "p10": pct(t, 0.10),
            "p90": pct(t, 0.90), "beats_favorite": beats_fav,
            "analytic_ev": analytic_ev[name],
        }
    # P(each strategy is the unique max on a draw)
    winmax = {name: 0 for name in STRATS}
    for k in range(n_draws):
        vals = {name: totals[name][k] for name in STRATS}
        m = max(vals.values())
        leaders = [n for n, v in vals.items() if v == m]
        if len(leaders) == 1:
            winmax[leaders[0]] += 1
    for name in STRATS:
        out[name]["p_best_among_strats"] = winmax[name] / n_draws
    return out


def report(out, label):
    print(f"\n=== correlated MC: {label} ===")
    print(f"{'strategy':20} {'mean':>7} {'median':>7} {'p10':>7} {'p90':>7} "
          f"{'beats_fav':>10} {'p_best':>7} {'analytic':>8}")
    for name, d in out.items():
        print(f"{name:20} {d['mean']:7.2f} {d['median']:7.2f} {d['p10']:7.2f} "
              f"{d['p90']:7.2f} {d['beats_favorite']:10.2f} "
              f"{d['p_best_among_strats']:7.2f} {d['analytic_ev']:8.2f}")
