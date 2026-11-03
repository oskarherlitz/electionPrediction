"""OFFLINE build + validate + export. No network; reads reconstructed odds, the
latest-q snapshot, and cached inputs only. Deterministic.

Produces, for each track, a matrix of strategy variants (all using the latest
pre-election q snapshot where available, p fixed at Nov-1), and copies the chosen
default into the canonical submission_*_recommended.csv.

Usage:
    python scripts/run_offline.py all
"""
from __future__ import annotations

import csv
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forecast import build, validate
from forecast.fallbacks import SENATE_FALLBACKS, HOUSE_FALLBACKS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "outputs")
TPL = os.path.join(DATA, "templates")

# Default recommended strategy per track (see WRITEUP.md / analysis). A threshold
# entry is the robust P(win) choice; all-underdog only wins if Kalshi is perfectly
# tail-calibrated (2018 evidence says it is not).
# Same strategy for both tracks so the 35 Senate rows stay identical across the
# Senate entry and the Senate portion of the Full Congress entry.
DEFAULT = {"senate": ("threshold", 0.15), "full": ("threshold", 0.15)}

STRATEGIES = [("ev", 0.0), ("threshold", 0.15), ("threshold", 0.25), ("favorite", 0.0)]


def load_q_latest():
    p = os.path.join(DATA, "q_snapshot.csv")
    d = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            v = r.get("q_price")
            if v not in (None, ""):
                try:
                    d[r["market_ticker"]] = float(v)
                except ValueError:
                    pass
    return d


def _tag(strategy, tau):
    return "ev" if strategy == "ev" else ("favorite" if strategy == "favorite"
                                          else f"thr{str(tau).replace('.', '')}")


def merge_full_odds():
    sen = os.path.join(DATA, "reconstructed_odds_senate.csv")
    hou = os.path.join(DATA, "reconstructed_odds_house.csv")
    merged = os.path.join(DATA, "reconstructed_odds_full.csv")
    rows, header = [], None
    for p in (sen, hou):
        if os.path.exists(p):
            with open(p, newline="") as fh:
                r = csv.reader(fh)
                header = next(r)
                rows.extend(list(r))
    if header:
        with open(merged, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
    return merged


def build_variants(track, template, odds, fb, q_latest):
    stats_by = {}
    dstrat, dtau = DEFAULT[track]
    dtag = _tag(dstrat, dtau)
    for strategy, tau in STRATEGIES:
        rec, ml, audit, stats = build.build_track(
            template, odds, fallbacks=fb, q_latest=q_latest,
            strategy=strategy, tau=tau)
        tag = _tag(strategy, tau)
        build.write_submission(rec, os.path.join(OUT, f"variants/submission_{track}_{tag}.csv"))
        if strategy == "favorite":
            build.write_submission(ml, os.path.join(OUT, f"submission_{track}_mostlikely.csv"))
        if tag == dtag:  # audit reflects the RECOMMENDED strategy
            build.write_audit(audit, os.path.join(OUT, f"picks_audit_{track}.csv"))
        stats_by[tag] = stats
    shutil.copyfile(os.path.join(OUT, f"variants/submission_{track}_{dtag}.csv"),
                    os.path.join(OUT, f"submission_{track}_recommended.csv"))
    return stats_by, dtag


def summarize(track, stats_by, dtag):
    print(f"\n== {track.upper()} (recommended strategy: {dtag}) ==")
    for tag, s in stats_by.items():
        mark = "  <-- recommended" if tag == dtag else ""
        print(f"  {tag:10} priced_rec={s['n_rec_priced']:3d} "
              f"fav={s['rec_favorite']:3d} und={s['rec_underdog']:3d} "
              f"partialEV={s['ev_priced_sum']:7.2f}{mark}")


def main():
    os.makedirs(os.path.join(OUT, "variants"), exist_ok=True)
    q_latest = load_q_latest()
    print(f"loaded latest-q snapshot: {len(q_latest)} markets")
    fb_full = dict(SENATE_FALLBACKS)
    fb_full.update(HOUSE_FALLBACKS)
    merged = merge_full_odds()

    s_sen, d_sen = build_variants("senate", os.path.join(TPL, "senate_template.csv"),
                                  os.path.join(DATA, "reconstructed_odds_senate.csv"),
                                  SENATE_FALLBACKS, q_latest)
    s_full, d_full = build_variants("full", os.path.join(TPL, "full_congress_template.csv"),
                                    merged, fb_full, q_latest)
    summarize("senate", s_sen, d_sen)
    summarize("full", s_full, d_full)

    # validate canonical + all variants
    print("\n-- validation --")
    ok_all = True
    checks = [("senate", "senate_template.csv"), ("full", "full_congress_template.csv")]
    for track, tmpl in checks:
        for path in [os.path.join(OUT, f"submission_{track}_recommended.csv"),
                     os.path.join(OUT, f"submission_{track}_mostlikely.csv")] + \
                    [os.path.join(OUT, "variants", f) for f in os.listdir(os.path.join(OUT, "variants"))
                     if f.startswith(f"submission_{track}_")]:
            ok, errs, _ = validate.validate_submission(path, os.path.join(TPL, tmpl))
            ok_all = ok_all and ok
            if not ok:
                print(f"  INVALID {os.path.basename(path)}: {errs[:2]}")
    errs = validate.senate_consistency(
        os.path.join(OUT, "submission_senate_recommended.csv"),
        os.path.join(OUT, "submission_full_recommended.csv"))
    print(f"  all files valid: {ok_all} | senate cross-track consistent: {not errs}")


if __name__ == "__main__":
    main()
