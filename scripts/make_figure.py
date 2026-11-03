"""Explanatory figure: a race where the most-likely winner != the contest pick.

Shows, per candidate, the benchmark price p, forecast q, and the expected-points
bar q*reward(p). The favorite has the highest q but a low EV; the underdog is the
expected-points pick. Numbers agree with picks_audit_senate.csv.

Usage: python scripts/make_figure.py [RACE_ID]   (default AK-SEN)
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from forecast.scoring import reward, is_valid_price  # noqa: E402
from forecast.build import build_candidates  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RACE = sys.argv[1] if len(sys.argv) > 1 else "AK-SEN"


def load_q_latest():
    p = os.path.join(ROOT, "data", "q_snapshot.csv")
    d = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            if r.get("q_price") not in (None, ""):
                try:
                    d[r["market_ticker"]] = float(r["q_price"])
                except ValueError:
                    pass
    return d


def load(race_id):
    rows = []
    for p in ("reconstructed_odds_senate.csv", "reconstructed_odds_house.csv"):
        fp = os.path.join(ROOT, "data", p)
        if os.path.exists(fp):
            rows += [r for r in csv.DictReader(open(fp)) if r["race_id"] == race_id]
    return rows


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = load(RACE)
    cands = [c for c in build_candidates(rows, q_latest=load_q_latest())
             if c.priced and is_valid_price(c.p)]
    cands = [c for c in cands if c.p >= 0.01]            # drop noise candidates
    cands.sort(key=lambda c: c.q, reverse=True)
    names = [f"{c.name}\n({c.party})" for c in cands]
    ps = [c.p for c in cands]
    qs = [c.q for c in cands]
    evs = [c.q * reward(c.p) for c in cands]

    likely = max(cands, key=lambda c: c.q)
    pick = max(cands, key=lambda c: c.q * reward(c.p))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
    x = range(len(cands))
    w = 0.38
    ax1.bar([i - w/2 for i in x], ps, w, label="p (Nov-1 price)", color="#8aa")
    ax1.bar([i + w/2 for i in x], qs, w, label="q (forecast)", color="#48c")
    ax1.set_xticks(list(x)); ax1.set_xticklabels(names, fontsize=9)
    ax1.set_ylabel("probability"); ax1.set_ylim(0, 1)
    ax1.set_title(f"{RACE}: price vs forecast")
    ax1.legend(fontsize=9)
    for i, (p, q) in enumerate(zip(ps, qs)):
        ax1.text(i - w/2, p + .02, f"{p:.2f}", ha="center", fontsize=8)
        ax1.text(i + w/2, q + .02, f"{q:.2f}", ha="center", fontsize=8)

    colors = ["#d33" if c is pick else "#bbb" for c in cands]
    ax2.bar(list(x), evs, color=colors)
    ax2.set_xticks(list(x)); ax2.set_xticklabels(names, fontsize=9)
    ax2.set_ylabel("expected points  q · (-log2 max(.01,p))")
    ax2.set_title("Expected-points pick (red) vs most-likely winner")
    for i, ev in enumerate(evs):
        ax2.text(i, ev + .005, f"{ev:.3f}", ha="center", fontsize=8)
    ax2.annotate(f"most-likely: {likely.name}", xy=(0.02, 0.95),
                 xycoords="axes fraction", fontsize=9, color="#333")
    ax2.annotate(f"contest pick: {pick.name}", xy=(0.02, 0.89),
                 xycoords="axes fraction", fontsize=9, color="#d33")

    fig.suptitle(
        f"{RACE}: most-likely winner ({likely.name}) differs from the contest "
        f"pick ({pick.name}) — the underdog's high reward dominates its lower q",
        fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = os.path.join(ROOT, "outputs", "figure_pick_vs_likely.png")
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")
    print(f"  most-likely: {likely.name} (q={likely.q:.3f}, EV={likely.q*reward(likely.p):.3f})")
    print(f"  contest pick: {pick.name} (q={pick.q:.3f}, p={pick.p:.3f}, EV={pick.q*reward(pick.p):.3f})")


if __name__ == "__main__":
    main()
