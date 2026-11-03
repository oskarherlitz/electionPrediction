# Submit-ready checklist

## What to submit

The form allows **both tracks** (judged separately). Submit:

| track | file | rows |
|---|---|---|
| Full Congress | `outputs/submission_full_recommended.csv` | 470 |
| Senate | `outputs/submission_senate_recommended.csv` | 35 |

Both use the **threshold@0.15** strategy (Senate rows are identical across them).
Exact headers: `race_id,chamber,predicted_winner_party,candidate_name,win_probability`.

To switch risk posture, copy a variant over the recommended file, e.g.
`cp outputs/variants/submission_full_favorite.csv outputs/submission_full_recommended.csv`
(variants: `ev`, `thr015`, `thr025`, `favorite`).

## Required materials (per the rules)

- [x] **Exact-predictions CSV(s)** — the two files above, validated.
- [x] **Reproducible code + README** — this repo; `README.md`, offline + refresh commands.
- [x] **Method / data / limitations paragraph** — `WRITEUP.md` (150 words).
- [x] **Substantive technical model** — expected-points optimizer + out-of-sample
      strategy selection (538 replay) + correlated Monte-Carlo; see `DECISIONS.md`.
- [x] **Explanation / visualization** — `outputs/report.html` (interactive) +
      two figures.

## Pre-submit verification (run these)

```bash
python scripts/run_offline.py all        # must end: "all files valid: True ... consistent: True"
python tests/test_scoring.py             # 9/9
python tests/test_analysis.py            # PASSED
python tests/test_release.py             # RELEASE CHECKS PASSED
python forecast/validate.py outputs/submission_full_recommended.csv data/templates/full_congress_template.csv
python forecast/validate.py outputs/submission_senate_recommended.csv data/templates/senate_template.csv
```

Spot-check the CSV you open: 470 (or 35) data rows, 5 columns, no blank cells, no
`NaN`/`UNKNOWN`, `win_probability` in [0,1], first/last rows match the template order.

## Things to confirm with organizers (draft in `ORGANIZER_QUESTIONS.md`, not sent)

- [ ] Deadline **timezone** (form says "Nov 2nd, 11:59pm", no zone).
- [ ] Whether a **reconstructed** (non-official) Nov-1 odds snapshot is acceptable.
- [ ] Winner/event definition for **same-party** contests (CA/LA/AK) and
      **unpriced** races (KY-SEN).
- [ ] That both tracks may be submitted.

## Optional: put the repo on GitHub

Not done automatically (and nothing is pushed). When you're ready:

```bash
git checkout -b model-citizens-2026
git add -A && git commit -m "Model Citizens 2026 forecasting entry"
# then: create a repo and `git push` — review first; data/cache/ is included for reproducibility
```
