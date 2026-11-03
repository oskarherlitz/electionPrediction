"""Proxy historical replay on FiveThirtyEight's 2018 final forecasts.

This is a PROXY benchmark (538 final probabilities as a stand-in for market
prices); it cannot establish Kalshi-specific tail bias, but it empirically tests
the key strategic question: under the competition's reward = -log2(max(.01,p))
with wrong-pick = 0, which per-race SELECTION RULE maximizes *realized* points,
and are deep longshots well-calibrated enough that betting them pays off?

We use one declared variant (classic) and one dated row per race (the Nov-6 final).
"""
from __future__ import annotations

import csv
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA2018 = os.path.join(ROOT, "data", "reference", "forecast_results_2018.csv")
FLOOR = 0.01


def reward(p):
    return -math.log2(max(FLOOR, p))


def load_races(variant="classic", branches=("House", "Senate")):
    races = []
    with open(DATA2018) as fh:
        for r in csv.DictReader(fh):
            if r["version"] != variant or r["branch"] not in branches:
                continue
            if r["uncalled"] == "1":
                continue
            try:
                bd = float(r["Democrat_WinProbability"])
                br = float(r["Republican_WinProbability"])
            except (ValueError, KeyError):
                continue
            dw, rw = r["Democrat_Won"], r["Republican_Won"]
            if dw == "1":
                winner = "D"
            elif rw == "1":
                winner = "R"
            else:
                continue
            # two-candidate normalization
            s = bd + br
            if s <= 0:
                continue
            bd, br = bd / s, br / s
            races.append({"race": r["race"], "branch": r["branch"],
                          "b": {"D": bd, "R": br}, "winner": winner})
    return races


def realized_points(races, pick_fn):
    """pick_fn(b) -> 'D'/'R'. Returns (total_points, n_wins, n)."""
    total, wins = 0.0, 0
    for g in races:
        pick = pick_fn(g["b"])
        if pick == g["winner"]:
            total += reward(g["b"][pick])
            wins += 1
    return total, wins, len(races)


def pick_favorite(b):
    return "D" if b["D"] >= b["R"] else "R"


def pick_underdog_ev(b):
    # argmax q*reward(p) with q=b -> the EV-optimal pick (usually the underdog)
    return max(("D", "R"), key=lambda c: b[c] * reward(b[c]))


def pick_threshold(theta):
    """Bet the EV pick, but if the chosen underdog's prob < theta, take favorite
    instead (avoid deep longshots that may be over-rewarded / miscalibrated)."""
    def fn(b):
        ev = pick_underdog_ev(b)
        fav = pick_favorite(b)
        if ev != fav and b[ev] < theta:
            return fav
        return ev
    return fn


def brier_logloss(races):
    """Brier + log-loss of the benchmark prob (prob the race's actual winner)."""
    brier, ll, n = 0.0, 0.0, 0
    for g in races:
        p_win = g["b"][g["winner"]]
        brier += (1 - p_win) ** 2
        ll += -math.log(max(1e-9, p_win))
        n += 1
    return brier / n, ll / n


def calibration_bins(races):
    """For the EV (underdog) pick, bin by picked prob and report observed win rate,
    expected wins, realized points. Tail-focused bins."""
    edges = [(0.0, 0.01), (0.01, 0.03), (0.03, 0.10), (0.10, 0.30),
             (0.30, 0.50), (0.50, 1.01)]
    out = []
    for lo, hi in edges:
        picks = []
        for g in races:
            pick = pick_underdog_ev(g["b"])
            pp = g["b"][pick]
            if lo <= pp < hi:
                picks.append((pp, 1 if pick == g["winner"] else 0, reward(pp)))
        if not picks:
            out.append((lo, hi, 0, 0, 0.0, 0.0, 0.0))
            continue
        n = len(picks)
        wins = sum(w for _, w, _ in picks)
        exp_wins = sum(pp for pp, _, _ in picks)
        pts = sum(rw for _, w, rw in picks if w)
        out.append((lo, hi, n, wins, exp_wins, pts, exp_wins and pts))
    return out


def run():
    races = load_races()
    print(f"2018 proxy replay: {len(races)} called House+Senate races (classic)\n")
    strategies = {
        "all-favorites": pick_favorite,
        "all-underdogs (q=benchmark EV)": pick_underdog_ev,
    }
    for th in (0.005, 0.01, 0.02, 0.03, 0.10, 0.20, 0.30):
        strategies[f"underdog-switch@{th}"] = pick_threshold(th)

    print(f"{'strategy':32} {'points':>9} {'pts/race':>9} {'wins':>6} {'hit%':>6}")
    results = {}
    for name, fn in strategies.items():
        pts, wins, n = realized_points(races, fn)
        results[name] = pts
        print(f"{name:32} {pts:9.2f} {pts/n:9.3f} {wins:6d} {100*wins/n:6.1f}")

    b, ll = brier_logloss(races)
    print(f"\nbenchmark Brier={b:.4f}  log-loss={ll:.4f}")

    print("\ncalibration of EV (underdog) picks by predicted prob bin:")
    print(f"{'bin':>14} {'n':>5} {'wins':>5} {'exp_wins':>9} {'realized_pts':>13}")
    for lo, hi, n, wins, ew, pts, _ in calibration_bins(races):
        print(f"[{lo:.2f},{hi:.2f}) {n:7d} {wins:5d} {ew:9.2f} {pts:13.2f}")

    best = max(results, key=results.get)
    print(f"\nbest realized-points strategy (2018 proxy): {best} ({results[best]:.2f})")
    return results


if __name__ == "__main__":
    run()
