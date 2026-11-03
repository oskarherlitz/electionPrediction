"""Cheap release checks for a submission CSV.

Validates schema, row set, cell admissibility, and (optionally) Senate-pick
consistency across the two tracks. Returns (ok, errors, warnings).
"""
from __future__ import annotations

import csv
import math
import os

HEADER = ["race_id", "chamber", "predicted_winner_party", "candidate_name", "win_probability"]
ALLOWED_PARTIES = {"D", "R", "I", "L", "G", "IND", "DFL"}


def _read(path):
    with open(path, newline="") as fh:
        return list(csv.reader(fh))


def validate_submission(path: str, template_path: str):
    errors, warnings = [], []
    rows = _read(path)
    if not rows:
        return False, ["empty file"], []
    header = rows[0]
    if header != HEADER:
        errors.append(f"header mismatch: {header} != {HEADER}")
    body = rows[1:]

    # exact template order + identity
    tmpl = _read(template_path)[1:]
    tmpl_ids = [r[0].strip() for r in tmpl if r and r[0].strip()]
    got_ids = [r[0].strip() for r in body]
    if got_ids != tmpl_ids:
        errors.append(f"race_id set/order mismatch: got {len(got_ids)} rows, "
                      f"template {len(tmpl_ids)}")
        # pinpoint first diff
        for i, (a, b) in enumerate(zip(got_ids, tmpl_ids)):
            if a != b:
                errors.append(f"  first diff at row {i}: {a!r} != {b!r}")
                break
    if len(set(got_ids)) != len(got_ids):
        errors.append("duplicate race_id rows present")

    for i, r in enumerate(body):
        where = f"row {i} ({r[0] if r else '?'})"
        if len(r) != 5:
            errors.append(f"{where}: expected 5 columns, got {len(r)}")
            continue
        rid, chamber, party, cand, wp = r
        if not rid or not chamber or not party or not cand or wp == "":
            errors.append(f"{where}: blank cell(s)")
        if party and party not in ALLOWED_PARTIES:
            warnings.append(f"{where}: unusual party {party!r}")
        if cand.strip().upper() in ("UNKNOWN", "NAN", ""):
            errors.append(f"{where}: invalid candidate {cand!r}")
        try:
            v = float(wp)
            if math.isnan(v) or math.isinf(v):
                errors.append(f"{where}: non-finite win_probability {wp!r}")
            elif not (0.0 <= v <= 1.0):
                errors.append(f"{where}: win_probability out of [0,1]: {v}")
        except ValueError:
            errors.append(f"{where}: non-numeric win_probability {wp!r}")
    return (len(errors) == 0), errors, warnings


def senate_consistency(senate_csv: str, full_csv: str):
    """Senate picks/probabilities must match across both tracks."""
    errs = []
    if not (os.path.exists(senate_csv) and os.path.exists(full_csv)):
        return ["missing one of the track files"]
    s = {r[0]: r for r in _read(senate_csv)[1:]}
    f = {r[0]: r for r in _read(full_csv)[1:] if len(r) == 5 and r[1] == "Senate"}
    for rid, sr in s.items():
        fr = f.get(rid)
        if fr is None:
            errs.append(f"{rid} missing in full track")
        elif sr != fr:
            errs.append(f"{rid} differs: senate={sr} full={fr}")
    return errs


if __name__ == "__main__":
    import sys
    ok, e, w = validate_submission(sys.argv[1], sys.argv[2])
    for x in e:
        print("ERROR", x)
    for x in w:
        print("WARN ", x)
    print("VALID" if ok else "INVALID")
    sys.exit(0 if ok else 1)
