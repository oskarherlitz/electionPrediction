# Method, Data & Limitations (Stanford Model Citizens 2026)

**Method.** For each candidate we fix the November-1 benchmark price `p` (Kalshi
hourly yes-bid/ask midpoint, last candle ≤ 23:59 ET) and set the forecast `q` to
the normalized *latest pre-election* Kalshi price (strictly more informed; kept
distinct from `p`). Each pick maximizes `q·reward(p)`,
`reward(p)=-log2(max(0.01,p))`. An out-of-sample replay on 538's 2018
final forecasts shows pure expected-points (all-underdog) is a trap (23 vs 41 pts
for favorites; deep longshots barely hit), so the recommended entry caps longshot
bets: take the favorite when the EV pick's `q<0.15`.

**Data.** Kalshi public API (omnibus `KXHOUSERACE` + per-district/state series,
verified to 2026 from metadata); 538 forecast-review for the replay. All cached for
deterministic offline reproduction.

**Limitations.** The threshold is tuned on one low-upset cycle; 2020/2022 data were
unavailable. Reconstructed prices aren't the organizers' official pull. Ten races
(KY-SEN, 9 CA same-party seats) lack markets and use flagged fallbacks. No
fundamentals blend was fit (`w=0`), disclosed not invented.
