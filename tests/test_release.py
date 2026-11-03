"""Release checks against generated submission files + extra scoring edge cases.

Run after a build:  python tests/test_release.py
Skips track files that do not exist yet (e.g. full track before Checkpoint 2).
"""
from __future__ import annotations

import csv
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from forecast import validate  # noqa: E402
from forecast.scoring import reward, MAX_REWARD, is_valid_price, underdog_threshold  # noqa: E402

OUT = os.path.join(ROOT, "outputs")
TPL = os.path.join(ROOT, "data", "templates")


def _approx(a, b, t=1e-6):
    return abs(a - b) <= t


def check_reward_table():
    cases = {0.9: -math.log2(0.9), 0.5: 1.0, 0.25: 2.0,
             0.01: -math.log2(0.01), 0.003: -math.log2(0.01),
             1.0: 0.0}
    for p, want in cases.items():
        assert _approx(reward(p), want), f"reward({p}) {reward(p)} != {want}"
    assert _approx(reward(0.0), MAX_REWARD)             # observed zero -> floor
    assert _approx(MAX_REWARD, 6.643856, 1e-6)
    # missing vs zero
    assert is_valid_price(0.0) and not is_valid_price(None)
    # threshold example
    assert _approx(underdog_threshold(0.75, 0.25), 0.1718555092, 1e-9)
    # a case where favorite is optimal (high q favorite)
    from forecast.scoring import Candidate, pick_expected_points
    c = [Candidate("F", "R", 0.55, 0.97), Candidate("U", "D", 0.45, 0.03)]
    assert pick_expected_points(c).name == "F"
    print("ok  reward table + threshold + favorite-optimal + missing/zero")


def check_file(path, template, label):
    if not os.path.exists(path):
        print(f"skip {label} (not built yet)")
        return
    ok, errs, warns = validate.validate_submission(path, template)
    for e in errs:
        print("   ERROR", e)
    assert ok, f"{label} invalid"
    # every win_probability finite in [0,1]; exactly 5 cols
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == validate.HEADER
    for r in rows[1:]:
        assert len(r) == 5
        v = float(r[4])
        assert 0.0 <= v <= 1.0 and not math.isnan(v) and not math.isinf(v)
    print(f"ok  {label}: {len(rows)-1} rows, schema valid")


def check_senate_consistency():
    s = os.path.join(OUT, "submission_senate_recommended.csv")
    f = os.path.join(OUT, "submission_full_recommended.csv")
    if not (os.path.exists(s) and os.path.exists(f)):
        print("skip senate cross-track consistency (full not built)")
        return
    errs = validate.senate_consistency(s, f)
    assert not errs, f"senate cross-track mismatch: {errs[:3]}"
    print("ok  senate picks identical across both tracks")


def check_selected_q_exported():
    """Recommended file must export the SELECTED candidate's q (from audit)."""
    apath = os.path.join(OUT, "picks_audit_senate.csv")
    spath = os.path.join(OUT, "submission_senate_recommended.csv")
    if not (os.path.exists(apath) and os.path.exists(spath)):
        print("skip selected-q check")
        return
    audit = {r["race_id"]: r for r in csv.DictReader(open(apath))}
    with open(spath, newline="") as fh:
        for r in list(csv.reader(fh))[1:]:
            rid, _, party, cand, wp = r
            a = audit[rid]
            assert a["rec_candidate"] == cand, f"{rid}: name mismatch"
            assert _approx(float(a["rec_q"]), float(wp), 1e-3), f"{rid}: q mismatch"
    print("ok  recommended exports selected-candidate q (incl. values < 0.5)")


if __name__ == "__main__":
    check_reward_table()
    check_file(os.path.join(OUT, "submission_senate_recommended.csv"),
               os.path.join(TPL, "senate_template.csv"), "senate_recommended")
    check_file(os.path.join(OUT, "submission_senate_mostlikely.csv"),
               os.path.join(TPL, "senate_template.csv"), "senate_mostlikely")
    check_file(os.path.join(OUT, "submission_full_recommended.csv"),
               os.path.join(TPL, "full_congress_template.csv"), "full_recommended")
    check_file(os.path.join(OUT, "submission_full_mostlikely.csv"),
               os.path.join(TPL, "full_congress_template.csv"), "full_mostlikely")
    check_selected_q_exported()
    check_senate_consistency()
    print("\nRELEASE CHECKS PASSED")
