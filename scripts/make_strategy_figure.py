"""Strategy-evidence figure: why the recommended entry uses a threshold, not
pure all-underdog. Left: 2018 out-of-sample realized points by rule. Right:
deep-longshot calibration (underdog picks that essentially never hit).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from forecast import replay  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    races = replay.load_races()
    rules = {
        "favorites": replay.pick_favorite,
        "underdog@.15": replay.pick_threshold(0.15),
        "underdog@.30": replay.pick_threshold(0.30),
        "all-underdog\n(q=p EV)": replay.pick_underdog_ev,
    }
    pts = {}
    for name, fn in rules.items():
        p, _, _ = replay.realized_points(races, fn)
        pts[name] = p

    bins = replay.calibration_bins(races)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    names = list(pts)
    vals = [pts[n] for n in names]
    colors = ["#2a7", "#4a90c0", "#4a90c0", "#d33"]
    ax1.bar(names, vals, color=colors)
    for i, v in enumerate(vals):
        ax1.text(i, v + 0.4, f"{v:.1f}", ha="center", fontsize=10)
    ax1.set_ylabel("realized competition points")
    ax1.set_title("2018 out-of-sample: all-underdog is a trap\n"
                  "(468 House+Senate races, 538 final probs)")

    labels = [f"[{lo:.0%},{hi:.0%})" if hi <= 1 else f"[{lo:.0%},100%)"
              for lo, hi, *_ in bins[:-1]]
    ns = [b[2] for b in bins[:-1]]
    wins = [b[3] for b in bins[:-1]]
    exp = [b[4] for b in bins[:-1]]
    x = range(len(labels))
    w = 0.38
    ax2.bar([i - w/2 for i in x], exp, w, label="expected upsets (sum of prob)", color="#bbb")
    ax2.bar([i + w/2 for i in x], wins, w, label="actual upsets", color="#d33")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels, fontsize=9)
    ax2.set_ylabel("count of underdog-pick wins")
    ax2.set_title("Deep longshots barely hit\n(underdog picks by predicted prob bin)")
    ax2.legend(fontsize=9)
    for i, (n, e, wi) in enumerate(zip(ns, exp, wins)):
        ax2.text(i, max(e, wi) + 0.3, f"n={n}", ha="center", fontsize=8, color="#555")

    fig.suptitle("Why the recommended entry caps deep-longshot bets (threshold "
                 "strategy), not pure expected-points", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = os.path.join(ROOT, "outputs", "figure_strategy_evidence.png")
    fig.savefig(out, dpi=130)
    print("wrote", out)


if __name__ == "__main__":
    main()
