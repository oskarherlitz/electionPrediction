# Assumptions, reconstructed odds, and open questions

This file records every judgement call behind the submission. The reconstructed
snapshot is **explicitly not** the organizers' verified odds pull; it supports the
recommended entry while remaining labelled unverified.

## Odds reconstruction convention
- **Source:** Kalshi public API `GET /trade-api/v2/series/{series}/markets/{ticker}/candlesticks`
  (`period_interval=60`), verified against docs.kalshi.com on 2026-11-02.
- **`p` (benchmark price):** midpoint of the **closing yes_bid / yes_ask** of the
  **last completed hourly candle ending at or before the cutoff**.
- **Cutoff:** 2026-11-01 23:59:59 America/New_York = **2026-11-02 04:59:59 UTC**
  (EST, UTC-5). Typical chosen candle ends 2026-11-02 04:00:00 UTC (23:00 ET),
  i.e. ~1h staleness — recorded per row in `data/reconstructed_odds_*.csv`.
- **Fallbacks within a market:** if a bid/ask side is missing we use the trade
  close, then a single side; each is flagged in `price_source`.
- Raw `p` is preserved; the 1% floor is applied **only inside** `reward()` and `p`
  is never renormalized after flooring.

## Forecast `q`
- **Market-only baseline, blend weight `w = 0`.** `q` is the within-race
  normalized candidate price. We did **not** fit a fundamentals blend before the
  deadline and disclose that rather than inventing an empirical weight.
- `p` (benchmark) and `q` (forecast) are kept distinct even when numerically equal.

## Cycle verification (legacy-ticker hazard)
Senate markets are fragmented across many legacy series. We select the **2026**
event from event metadata (`title/sub_title` "In 2026", post-election close),
**not** ticker spelling — e.g. `SENATEGA-28` is the 2028 race and is rejected;
`SENATEGA-26` is used.

## Specials & at-large
- **FL-SEN** → `SENATEFLS` (2026 Florida special, Rubio seat): Moody (R) vs Nixon (D).
- **OH-SEN** → `SENATEOHS` (2026 Ohio special, Vance seat): Husted (R) vs Brown (D).
- House at-large IDs preserved exactly (`AK-AL`, `DE-AL`, `ND-AL`, `SD-AL`,
  `VT-AL`, `WY-AL`).

## Missing / ambiguous / flagged rows
- **KY-SEN — FALLBACK (no general-winner market).** Kalshi lists only primary
  nominee markets. Pick: Andy Barr (R), `q=0.95`, Safe-R open seat. No price
  invented; row contributes no scored expected-points.
- **Same-party / jungle fields (candidate contracts used):** AK, ME, NE, LA, MT
  use person-level markets so a specific candidate (not just a party) is identified.
- **Low-information / surprising prices used as-is and flagged:** KS (Marshall R
  priced ~0.40 despite large open interest — verified against raw candle, not a
  bug), MT (person market, incumbent framing differs), ME (person market: Troy
  Jackson priced as D frontrunner). We use the benchmark price per the rules and
  note the data-quality caveat.
- **Independents:** Dan Osborn (NE) and Seth Bodnar (MT) are recorded as `I`.

## Scoring selection & strategy (updated after historical analysis)
- **Forecast `q` = latest pre-election Kalshi snapshot** (normalized per race),
  distinct from the Nov-1 benchmark `p` which drives `reward`. Using election-eve
  info is explicitly permitted; it flips 6/460 EV picks vs `q=p` (market stable).
- Selection formula is always `argmax q·reward(p)` ("ev"). But pure ev picks the
  priced **underdog** in nearly every race, and a proxy replay on 538's 2018 final
  forecasts shows that is a **trap**: all-underdog realized **23.1** pts vs **41.0**
  for favorites; 221 sub-1% underdog picks won **0** times. See
  `outputs/analysis_report.txt` and `figure_strategy_evidence.png`.
- **Recommended default = threshold@0.15**: take the ev (underdog) pick only when
  its `q ≥ 0.15`, else the favorite. This keeps genuine-tossup underdog upside
  (63/460 Full, 10/35 Senate) while cutting deep-longshot waste. A correlated Monte
  Carlo shows this is the robust P(win) choice unless Kalshi is *perfectly*
  tail-calibrated (in which case pure ev wins). Variants shipped in
  `outputs/variants/`: `ev`, `thr015`, `thr025`, `favorite`.
- Same strategy is used for both tracks so Senate rows are identical across them.
- `win_probability` is the **selected candidate's** `q`, exported even when `< 0.5`.

## Coverage & recommended track (final)
- **Senate:** 35 rows, 34 priced + 1 fallback (KY). All picks underdogs. Partial
  expected-points (priced subset) = **8.907**. VALID.
- **Full Congress:** 470 rows, **460 priced + 10 fallbacks** (KY-SEN + 9 CA
  safe/same-party seats). Recommended picks: 458 priced underdogs, 2 priced
  favorites (CA-06, IL-04 after dropping stray contracts), 10 fallbacks. Partial
  expected-points (priced subset) = **93.048**. VALID. Senate rows are identical
  across both tracks.
- **Recommended track: Full Congress** (`outputs/submission_full_recommended.csv`)
  — all 470 rows pass the correctness checks and it has ~10x the scored surface of
  Senate. Senate (`outputs/submission_senate_recommended.csv`) is retained as the
  safe earlier fallback. The form permits only ONE track; submit one.
- Market discovery: House = omnibus `KXHOUSERACE` (351 races) **plus** individual
  per-district series for the 85 battleground seats it omits (`HOUSEAZ1`,
  `KXHOUSEUT01`, `HOUSENJ9`, ...), verified to 2026 from event metadata.

## Mixed party+person events
Some events list canonical `-D`/`-R` (or `-DEM`/`-GOP`) contracts alongside stray
person contracts (e.g. CA-06 Kevin Kiley, IL-04). When a race already offers
canonical D and R outcomes we drop unlabelled stray contracts so the
mutually-exclusive outcome set and q-normalization stay clean. Explicit
independents (NE Osborn, MT Bodnar, AK-AL Bill Hill) keep their party and are kept.

## Eligibility questions (unconfirmed — see ORGANIZER_QUESTIONS.md)
- Deadline **"Nov 2nd, 11:59pm"**, timezone **not stated on the form** — treated
  as the binding constraint; assume the earlier (Pacific→Eastern ambiguous) time.
- Form says **"You can submit for one track"** → we prepare both but submit one.
- Whether a reconstructed (non-official) odds snapshot and this technical model
  are acceptable is unconfirmed.
