# Stanford Model Citizens 2026 — Congressional Forecasting Entry

A reproducible, market-anchored forecasting pipeline for the **2026 U.S. Senate
(35 races)** and **full Congress (470 races)**. It reconstructs November-1 Kalshi
benchmark prices, forecasts each race with the freshest pre-election market
information, and selects each pick to maximize the competition's scoring rule —
then uses an out-of-sample backtest to avoid the trap that a naive reading of the
rules walks straight into.

> **Submission note:** the recommended entries are
> `outputs/submission_full_recommended.csv` and
> `outputs/submission_senate_recommended.csv`. Nothing is auto-submitted or
> published. See **[Submit-ready checklist](SUBMISSION_CHECKLIST.md)**.

---

## 📊 View it: the dashboard

Open **`outputs/report.html`** in any browser (double-click, or `open
outputs/report.html`). It is a **single self-contained file** — no server, no
internet, no dependencies — built for the best-explanation / best-visuals award:

- the scoring rule and the **all-underdog trap**, in plain language;
- summary metrics + an **animated projected-chamber-control** bar (House 218
  majority line; Senate seats-up), toggling most-likely winners vs our picks;
- a **Senate tile-grid map** (one square per state, colored by our pick) and a
  **House seat spectrum** (435 districts ordered safe-R → safe-D), with gold rings
  on the seats where we bet the underdog; hover any cell for detail;
- an **EV-vs-price scatter** of all 460 priced races (filled = underdog bet,
  hollow = favorite) — the whole strategy in one chart;
- an **interactive explorer for all 470 races** — sort, filter, search, and click
  any race for an **animated reward-curve** (`-log2(p)`) plotting each candidate
  plus the per-candidate `q` / expected-points breakdown;
- the strategy comparison table.

The UI was built and refined against the **[impeccable](https://github.com/pbakaus/impeccable)**
design skill (Operate/Read mode — precision and restraint): themed browser surfaces
(selection, scrollbars, focus rings), tabular numerals throughout, no colored
`border-left` callouts, keyboard-accessible sortable headers, and a reduced-motion
fallback. Verified across desktop and mobile widths via headless screenshots.

Regenerate it with `python scripts/make_report.py`.

Two standalone figures also live in `outputs/`:
`figure_strategy_evidence.png` (why we cap longshot bets) and
`figure_pick_vs_likely.png` (one race: contest pick vs most-likely winner).

---

## The scoring rule (non-negotiable)

```
reward(p)          = -log2(max(0.01, p))        # 1% floor ONLY inside reward
expected_points(c) = q(c) * reward(p(c))
pick               = argmax_c expected_points(c) # wrong picks score 0
```

- `p` = November-1 Kalshi benchmark price of the candidate (drives the reward).
- `q` = our forecast probability for the same event (latest pre-election snapshot).

Implemented in `forecast/scoring.py`, unit-tested against the spec's worked
examples (threshold `0.1718555092`, max reward `≈ 6.643856`, observed-0 → floor vs
missing, wrong-pick → 0, a favorite-optimal case).

---

## Strategy — the key decision (full rationale in [DECISIONS.md](DECISIONS.md))

A literal reading ("maximize expected points") picks the **underdog** in almost
every race, because a longshot's huge `reward` outweighs its low `q`. **That is a
trap.** Replaying FiveThirtyEight's 2018 final forecasts under this exact rule:

| rule | realized points | hit % |
|---|---|---|
| all-favorites | **41.0** | 97% |
| all-underdog (q=p expected-points) | 23.1 | 22% |
| underdog-switch @0.30 | 33.1 | 93% |

**221 sub-1% underdog picks won 0 times.** Deep longshots floor at reward 6.64 but
essentially never hit. A correlated Monte-Carlo with a tail-overconfidence stress
test confirms all-underdog only wins if Kalshi is *perfectly* tail-calibrated and
collapses otherwise.

**Recommended strategy: `threshold@0.15`** — take the expected-points (underdog)
pick only when its forecast `q ≥ 0.15` (a genuine tossup), otherwise the favorite.
This keeps real upside, cuts the deep-longshot waste, and is the robust choice for
*probability of winning*. Four variants ship in `outputs/variants/` so the risk
posture is a one-line change: `ev` (pure all-underdog, max ceiling), `thr015`
(recommended), `thr025`, `favorite` (max robustness).

---

## Data pipeline

1. **Discover markets** (`scripts/refresh.py`): the omnibus `KXHOUSERACE` series
   (351 House races) **plus** per-district series for the ~85 battleground seats it
   omits, and per-state Senate series. Every event is verified to the **2026**
   cycle from metadata, not ticker spelling (`SENATEGA-28` is 2028 and rejected).
2. **Reconstruct `p`** — Nov-1 yes-bid/ask midpoint of the last hourly candle ≤
   23:59 ET, with per-row provenance (source, staleness, volume).
3. **Snapshot `q`** (`scripts/refresh_q.py`) — the latest pre-election price for
   every discovered market.
4. **Build + validate** (`scripts/run_offline.py`) — assemble races, apply the
   strategy, write submissions + audit, run schema checks.

Every raw API response is cached under `data/cache/`, so steps 1–3 are **online
and separable**, while the build (step 4) is **offline, deterministic, seed-free**.

---

## Repository layout

```
forecast/
  scoring.py      scoring rule + selection strategies (ev / favorite / threshold)
  kalshi.py       cached Kalshi client + Nov-1 price reconstruction (certifi TLS)
  races.py        race→series mapping, 2026-cycle verification, party lookup
  fallbacks.py    documented candidates for the 10 unpriced races
  build.py        assemble races, estimate q, select picks, export
  validate.py     schema + release checks
  replay.py       538 2018 out-of-sample strategy backtest
  simulate.py     correlated Monte-Carlo + tail-overconfidence stress test
scripts/
  refresh.py      ONLINE: discover markets + reconstruct Nov-1 p
  refresh_q.py    ONLINE: latest pre-election q snapshot
  run_offline.py  OFFLINE: build all strategy variants + validate
  analyze.py      replay + Monte-Carlo report
  make_figure.py  per-race figure
  make_strategy_figure.py  strategy-evidence figure
  make_report.py  self-contained interactive HTML dashboard
outputs/
  submission_{senate,full}_recommended.csv   <-- SUBMIT THESE
  submission_{senate,full}_mostlikely.csv
  variants/submission_{track}_{ev,thr015,thr025,favorite}.csv
  picks_audit_{senate,full}.csv   assumptions.md   analysis_report.txt
  report.html   figure_strategy_evidence.png   figure_pick_vs_likely.png
data/
  templates/   cache/ (raw API JSON)   reference/ (538 2018)
  reconstructed_odds_{senate,house,full}.csv   q_snapshot.csv
tests/          test_scoring.py  test_analysis.py  test_release.py
DECISIONS.md  WRITEUP.md  ORGANIZER_QUESTIONS.md  SUBMISSION_CHECKLIST.md
```

---

## Reproduce

Offline (from cached inputs — no network, deterministic):

```bash
pip install -r requirements.txt       # certifi (refresh) + matplotlib (figures); build is stdlib
python scripts/run_offline.py all     # build + validate both tracks and all variants
python scripts/analyze.py             # 2018 replay + Monte-Carlo stress tests
python scripts/make_figure.py AK-SEN  # per-race figure
python scripts/make_strategy_figure.py
python scripts/make_report.py         # outputs/report.html
python tests/test_scoring.py && python tests/test_analysis.py && python tests/test_release.py
```

Refresh source data from Kalshi (separate online step; re-caches raw responses):

```bash
python scripts/refresh.py all         # senate + house discovery + Nov-1 p
python scripts/refresh_q.py           # latest pre-election q snapshot
```

---

## Results at a glance

- **Full Congress:** 470 rows, **460 priced** + 10 flagged fallbacks. Recommended
  (`thr015`): 397 favorites, 63 underdog bets.
- **Senate:** 35 rows, 34 priced + 1 fallback. Recommended: 24 favorites, 10
  underdogs. Senate rows identical across both tracks.
- Headers (exact): `race_id,chamber,predicted_winner_party,candidate_name,win_probability`.
- All submission + variant files pass schema validation; offline rebuild is
  byte-identical.

---

## Caveats (see [WRITEUP.md](WRITEUP.md) and `outputs/assumptions.md`)

- Odds are **reconstructed** from Kalshi's public API (yes-bid/ask midpoint,
  last candle ≤ Nov-1 23:59 ET) and **labelled unverified** — not the organizers'
  official pull.
- The `0.15` threshold is tuned on **one** low-upset cycle (2018); 2020/2022 538
  data were unavailable. A judgement call, supported by the Monte-Carlo as robust.
- No fundamentals blend (`w = 0`) — deliberate and disclosed (a real-world prior
  would fight this environment's market).
- 10 unpriced races use documented, flagged fallbacks; they contribute no scored
  points. We never invent a price.

## Attribution

The market/model (`q` vs `p`) separation and expected-points framing were informed
by the public `ariohamrah/democracyday26` reference; **all code here is
independent.** Historical replay uses FiveThirtyEight's published 2018
forecast-review data. Nothing is auto-submitted or published externally.
