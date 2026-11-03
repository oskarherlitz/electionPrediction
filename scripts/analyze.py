"""Strategy analysis: 2018 proxy replay + correlated Monte-Carlo on the 2026 entry.

Usage: python scripts/analyze.py [n_draws]
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from forecast import replay, simulate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TPL = os.path.join(DATA, "templates")


def load_q_latest(path=os.path.join(DATA, "q_snapshot.csv")):
    d = {}
    if not os.path.exists(path):
        return d
    for r in csv.DictReader(open(path)):
        v = r.get("q_price")
        if v not in (None, ""):
            try:
                d[r["market_ticker"]] = float(v)
            except ValueError:
                pass
    return d


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    print("########## 2018 PROXY REPLAY ##########")
    replay.run()

    q_latest = load_q_latest()
    print(f"\n########## CORRELATED MC on 2026 (q=latest, {len(q_latest)} mkts) ##########")
    full = simulate.load_entry(os.path.join(TPL, "full_congress_template.csv"),
                               os.path.join(DATA, "reconstructed_odds_full.csv"),
                               q_latest=q_latest)
    sen = simulate.load_entry(os.path.join(TPL, "senate_template.csv"),
                              os.path.join(DATA, "reconstructed_odds_senate.csv"),
                              q_latest=q_latest)
    for temp, lbl in [(1.0, "calibrated"), (1.5, "mild tail-overconfidence"),
                      (2.0, "strong tail-overconfidence")]:
        out_full = simulate.simulate(full, n_draws=n, dgp_temp=temp)
        simulate.report(out_full, f"FULL CONGRESS ({len(full)} races) DGP={lbl}")
    print("\n(If Kalshi overstates upsets like 538 did in 2018, the true DGP is "
          "sharpened toward favorites; see how all-underdog degrades.)")
    out_sen = simulate.simulate(sen, n_draws=n, dgp_temp=1.0)
    simulate.report(out_sen, f"SENATE ({len(sen)} races) DGP=calibrated")
    out_sen2 = simulate.simulate(sen, n_draws=n, dgp_temp=1.5)
    simulate.report(out_sen2, f"SENATE ({len(sen)} races) DGP=mild tail-overconfidence")


if __name__ == "__main__":
    main()
