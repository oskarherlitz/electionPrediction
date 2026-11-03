"""Non-negotiable scoring core for the Stanford Model Citizens 2026 entry.

Scoring rules (fixed by the competition):

    reward(p)          = -log2(max(0.01, p))
    expected_points(c) = q(c) * reward(p(c))
    pick               = argmax_c expected_points(c)

Where, for a single graded event / candidate ``c``:

* ``p(c)`` is the November-1 benchmark (Kalshi) price for that event. The 1%
  floor is applied ONLY inside ``reward``; the raw ``p`` is preserved elsewhere
  and never renormalised after flooring.
* ``q(c)`` is the forecaster's probability estimate for the same graded event.
* A wrong pick scores zero.

These functions are deliberately dependency-free and side-effect-free so they
can be unit-tested exactly against the worked examples in the task spec.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# 1% price floor used inside reward(). This is NOT a probability estimate and
# must never be used to renormalise p or to alter q.
PRICE_FLOOR = 0.01

# Maximum attainable reward, at the floor: -log2(0.01) ~= 6.643856.
MAX_REWARD = -math.log2(PRICE_FLOOR)


def is_valid_price(p) -> bool:
    """A price is admissible iff it is a finite real in [0, 1].

    Missing (None) stays missing (returns False). NaN / +-inf are rejected.
    Observed p == 0 is admissible here (it receives the floor only inside
    reward); callers decide whether a *missing* price blocks export.
    """
    if p is None:
        return False
    try:
        pf = float(p)
    except (TypeError, ValueError):
        return False
    if math.isnan(pf) or math.isinf(pf):
        return False
    return 0.0 <= pf <= 1.0


def reward(p: float) -> float:
    """reward(p) = -log2(max(0.01, p)).

    ``p`` must be an admissible price (finite, in [0, 1]); an observed 0 maps to
    the floor. Raises ValueError on invalid/NaN/infinite input so bugs surface
    rather than silently scoring.
    """
    if not is_valid_price(p):
        raise ValueError(f"reward() received an invalid price: {p!r}")
    return -math.log2(max(PRICE_FLOOR, float(p)))


def expected_points(q: float, p: float) -> float:
    """expected_points = q * reward(p).

    ``q`` is a probability in [0, 1]; ``p`` is the benchmark price.
    """
    if q is None or (isinstance(q, float) and (math.isnan(q) or math.isinf(q))):
        raise ValueError(f"expected_points() received an invalid q: {q!r}")
    q = float(q)
    if not (0.0 <= q <= 1.0):
        raise ValueError(f"expected_points() q out of [0,1]: {q!r}")
    return q * reward(p)


@dataclass
class Candidate:
    """One graded outcome within a race."""

    name: str
    party: str
    p: float          # November-1 benchmark price (raw, un-floored)
    q: float          # forecaster probability for this same event
    ticker: str = ""  # Kalshi market ticker, for provenance
    priced: bool = True  # False => price was missing / fallback used


def pick_expected_points(candidates: list[Candidate]) -> Candidate:
    """Return the candidate maximising expected_points = q * reward(p).

    Only candidates with an admissible price participate in the EV ranking. If
    *no* candidate is priced, the best-q candidate is returned (documented
    fallback; callers should flag the row). Ties broken by higher q, then by
    name for determinism.
    """
    priced = [c for c in candidates if c.priced and is_valid_price(c.p)]
    pool = priced if priced else candidates
    return max(pool, key=lambda c: (expected_points(c.q, c.p) if is_valid_price(c.p) else -1.0,
                                     c.q, c.name))


def pick_most_likely(candidates: list[Candidate]) -> Candidate:
    """Return the most-likely winner (argmax q). Ties broken by name."""
    return max(candidates, key=lambda c: (c.q, c.name))


def pick_threshold(candidates: list[Candidate], tau: float) -> Candidate:
    """Expected-points pick, but if that pick's q < tau, take the most-likely
    winner instead. Avoids dumping picks into deep longshots that (per the 2018
    replay) essentially never hit and score zero. tau=0 reduces to pure EV."""
    ev = pick_expected_points(candidates)
    fav = pick_most_likely(candidates)
    if ev.name != fav.name and ev.q < tau:
        return fav
    return ev


def underdog_threshold(p_fav: float, p_und: float) -> float:
    """Return the q_underdog above which picking the underdog beats the favorite.

    Derived from q_U * reward(p_U) > q_F * reward(p_F) with the favorite treated
    as the complement of the underdog in a binary race (q_F = 1 - q_U):

        q_U > reward(p_F) / (reward(p_U) + reward(p_F))
    """
    rU, rF = reward(p_und), reward(p_fav)
    return rF / (rU + rF)
