# Decision log — why the entry is built this way

This document records every non-obvious choice and the reasoning behind it, so a
reviewer can audit the judgement, not just the code. Ordered roughly by the
pipeline. Short version: **we anchor on the market, forecast with the freshest
market info, and let out-of-sample evidence — not the literal rules — choose the
selection strategy.**

---

## 0. Goal and the scoring rule

The competition scores each pick with `reward(p) = -log2(max(0.01, p))` if the
picked candidate wins, else **0**, where `p` is the candidate's November-1 Kalshi
price. We optimize for **probability of winning the competition**, which is not
the same as maximizing a single entry's expected points (see §5–6).

`forecast/scoring.py` implements the rule exactly and is unit-tested against the
spec's worked examples (threshold `0.1718555092`, max reward `6.643856`, the
`p_U=.25/p_F=.75` case, observed-0→floor vs missing, wrong-pick→0).

---

## 1. Market discovery (the hard part)

Kalshi's election markets are **fragmented and inconsistently named**. Decisions:

- **House = two sources.** The omnibus `KXHOUSERACE` series covers 351 (mostly
  safer) districts with `sub_title` equal to the race id. The ~85 **battleground**
  districts live in individual per-district series with inconsistent spellings
  (`HOUSEAZ1`, `KXHOUSEUT01`, `HOUSENJ9` with no leading zero, specials with an
  `S` suffix). We generate candidate tickers for each missing district and probe
  them (`_individual_series_candidates`). Missing the battlegrounds would have
  been a silent, catastrophic coverage hole — they are the highest-value races.
- **Senate = per-state legacy series**, chosen from a prioritized list per race,
  preferring person-level ("…winner? (Person)") markets for same-party/jungle
  contests (AK, ME, NE, LA, MT).
- **Cycle verified from metadata, never ticker spelling.** `SENATEGA-28` is the
  2028 race; `SENATEGA-26` is 2026. `event_is_2026()` requires a 2026 marker in
  title/sub_title and rejects 2024/2028 signals. This directly follows the
  "confusing legacy tickers" warning.
- **SSL:** macOS system Python can't verify Kalshi's TLS with urllib; we use the
  `certifi` CA bundle (curl worked, urllib didn't — caught during the first run).
- **Caching:** every raw API response is written under `data/cache/` so the build
  reproduces offline and deterministically, and so a refresh is separable from the
  scored run.

---

## 2. Benchmark price `p` (what reward is computed on)

- **Convention:** midpoint of the closing **yes_bid / yes_ask** of the **last
  completed hourly candle ending at or before 2026-11-01 23:59:59 America/New_York**
  (= 2026-11-02 04:59:59 UTC; EST, UTC-5). Typical chosen candle ends 23:00 ET
  (~1h staleness), recorded per row.
- **Why midpoint:** it is the cleanest single-number summary of a two-sided quote
  and is robust to one-sided staleness. If a side is missing we fall back to the
  trade close, then a single side, each flagged in `price_source`.
- **Raw `p` is preserved**; the 1% floor is applied *only inside* `reward()`. We
  never renormalize `p` after flooring.
- **We verified a surprising price rather than "fixing" it.** Kansas showed
  Marshall (R) ≈ 0.40 with 2.5M open interest; we pulled the raw candle and
  confirmed it (bid 0.40 / ask 0.41, heavy volume). `p` is *defined* as the Kalshi
  price, so we use it. This environment's market simply prices an unusual
  D-leaning reality; fighting it with real-world priors would be a mistake (§8).

---

## 3. Forecast `q` (what we believe, used to pick)

- `q` ≠ `p` on purpose. The benchmark `p` is fixed at Nov-1, but our **forecast
  may use any admissible pre-election information**. It is election eve, markets
  still trade, so we set `q` to the **normalized latest pre-election Kalshi
  snapshot** — strictly more informed than the Nov-1 benchmark.
- Impact is honest-small: it flips 6/460 EV picks (the market was stable Nov-1→2).
  We keep it because it is free, defensible, and occasionally reveals a Nov-1-cheap
  contract that has since firmed up (high reward × high win prob).
- `q` is normalized within a race so per-race probabilities sum to one. `p`
  (for reward) and `q` (for selection) are stored and timestamped separately.
- We did **not** invent a fundamentals-blended `q` (`w = 0`); see §8.

---

## 4. Candidate & party correctness

- **Party from the contract** (`-D/-R/-DEM/-GOP/-DFL/-I`) where present; otherwise
  from a small curated roster for person-level markets (`PERSON_PARTY`). Every
  *selected* candidate must have a party (validated).
- **Same-party contests** (CA top-two, LA jungle, AK): party-win probability can't
  identify a winner, so we use candidate contracts. Where none exist (9 CA seats),
  we use a documented candidate fallback and flag scoring ambiguity.
- **Stray / primary person contracts** that coexist with canonical `-D`/`-R`
  markets (e.g., CA-06 "Kevin Kiley", IL-04) are dropped **only** when the race
  already offers both a D and an R outcome, so the mutually-exclusive outcome set
  and the q-normalization stay clean. Explicit independents (NE Osborn, MT Bodnar)
  are kept.

---

## 5. Why the literal rule says "bet the underdog" (and why that's a trap)

With `q = p`, the expected points of picking candidate `c` is `p·(-log2 p)`, which
peaks at `p ≈ 0.368` and, for any binary race, is **higher for the underdog** than
the favorite. So a naive reading of "maximize expected points" bets the priced
underdog in essentially every race. Our first draft did exactly this (458/460
underdogs). It is internally correct **and a losing strategy** — because it bets
that the market is *perfectly* tail-calibrated.

---

## 6. The selection-strategy decision (the heart of the entry)

We stopped assuming and ran evidence.

**Out-of-sample replay (`forecast/replay.py`, 538 final 2018 forecasts, 468 called
House+Senate races, real outcomes):**

| rule | realized points | hit % |
|---|---|---|
| all-favorites | **41.0** | 97% |
| all-underdog (q=p EV) | 23.1 | 22% |
| underdog-switch @0.3 | 33.1 | 93% |

The calibration bins are decisive: **221 sub-1% underdog picks won 0 times; 0.01–
0.03 picks won 0/23.** Deep longshots floor at reward 6.64 but essentially never
hit, so they contribute nothing to a *single* entry.

**Correlated Monte Carlo (`forecast/simulate.py`, 2026 entry, shared national
swing):** if the market is *perfectly* calibrated, all-underdog reliably wins over
460 races (diversification). But that test is circular — it assumes the thing in
question. So we added a **tail-overconfidence stress** (sharpen the true DGP toward
favorites, modeling the 2018 pattern). Result for Full Congress `P(best strategy)`:

| strategy | DGP calibrated | mild overconf. | strong overconf. |
|---|---|---|---|
| favorite | .00 | .25 | **.48** |
| all-underdog | **1.00** | .17 | .01 |
| threshold@0.15 | .00 | **.27** | .10 |

**Decision: `threshold@0.15`** — take the expected-points (underdog) pick only when
its forecast `q ≥ 0.15`, else the favorite. Rationale:
- It keeps the genuine-tossup underdog bets (high reward, plausible win) where the
  EV logic is sound.
- It cuts the deep-longshot waste that sank the 2018 all-underdog entry.
- It is the **robust P(win) choice**: best under the empirically-supported
  "mild overconfidence" regime and never catastrophic. All-underdog only wins if
  Kalshi tails are perfect — a bet the one real data point argues against.
- **Field effect:** many entrants will submit the literal all-underdog entry. In
  the modal outcome (favorites mostly win), those entries score ~low; a
  threshold/favorite entry beats that crowd.
- `τ = 0.15` is a judgement, acknowledged (§9): tuned on one low-upset cycle. We
  ship `ev`, `thr015`, `thr025`, `favorite` variants so the risk posture is a
  one-line change.

The user selected `threshold@0.15` as the recommended default.

---

## 7. Fallbacks for unpriced races

Ten races have no usable market: **KY-SEN** (Kalshi lists only primary-nominee
markets) and **9 California seats** (safe / top-two same-party generals). For each
we use a documented candidate (incumbent or frontrunner) with a party and a
seat-safety `q`, flagged `FALLBACK_NO_MARKET`. These are **unpriced**, so they
contribute **no scored expected-points** — only a valid, defensible row. We never
invent a price, and fallbacks never displace score-based picks in priced races.

---

## 8. What we deliberately did NOT do

- **No real-world fundamentals blend (`w=0`).** This environment's market encodes
  an unusual D-leaning reality. A fundamentals model fit on real-world 2024 lean
  would systematically fight the market and most likely *hurt*. The task permits
  keeping the market-only baseline and disclosing it rather than inventing a
  weight. The blend hook exists (`build_track(blend_w=…)`) if a within-environment
  prior ever becomes available.
- **No polling/demographic/ensemble modeling.** Not required; the replay showed the
  decisive lever is the selection strategy, not a marginal `q` edge.
- **No 2020/2022 replay.** Those 538 directories contain only READMEs (data
  external/unavailable); we did not delay the entry hunting for inaccessible data.

---

## 9. Validation, reproducibility, and open risks

- **Tests:** `test_scoring` (9/9), `test_analysis` (replay + sim + threshold),
  `test_release` (schema, template order, 5 columns, finite `wp∈[0,1]`, no
  blanks/NaN, selected-candidate-`q` export, Senate cross-track identity).
- **Determinism:** offline rebuild yields byte-identical recommended CSVs; no RNG
  in the build; the simulator is seeded.
- **Both tracks** use the same strategy so the 35 Senate rows are identical across
  the Senate entry and the Senate portion of the Full Congress entry.
- **Known risks:** (a) the 0.15 threshold rests on one cycle; (b) reconstructed
  odds are **not** the organizers' official pull; (c) 10 fallback rows carry small
  candidate-identity risk (zero scoring impact); (d) deadline timezone unconfirmed.
