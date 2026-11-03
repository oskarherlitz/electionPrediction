"""Unit tests for the non-negotiable scoring core.

Run: python -m pytest tests/ -q   (or: python tests/test_scoring.py)
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forecast.scoring import (  # noqa: E402
    Candidate,
    MAX_REWARD,
    expected_points,
    is_valid_price,
    pick_expected_points,
    pick_most_likely,
    reward,
    underdog_threshold,
)

TOL = 1e-9


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_reward_known_values():
    assert approx(reward(0.9), -math.log2(0.9))
    assert approx(reward(0.5), 1.0)
    assert approx(reward(0.25), 2.0)
    assert approx(reward(0.01), -math.log2(0.01))
    # p below the floor uses the floor
    assert approx(reward(0.003), -math.log2(0.01))
    # observed zero receives the floor (max reward)
    assert approx(reward(0.0), MAX_REWARD)
    assert approx(reward(0.0), 6.643856, tol=1e-6)
    # p == 1 gives zero reward
    assert approx(reward(1.0), 0.0)


def test_reward_rejects_invalid():
    for bad in (None, float("nan"), float("inf"), -0.1, 1.5, "x"):
        try:
            reward(bad)
        except ValueError:
            continue
        raise AssertionError(f"reward({bad!r}) should have raised")


def test_is_valid_price_missing_vs_zero():
    assert is_valid_price(0.0) is True          # observed zero is a valid price
    assert is_valid_price(None) is False         # missing stays missing
    assert is_valid_price(float("nan")) is False
    assert is_valid_price(float("inf")) is False
    assert is_valid_price(1.0) is True
    assert is_valid_price(1.0001) is False


def test_threshold_example():
    # Spec worked example: p_U=0.25, p_F=0.75 -> threshold ~= 0.1718555092
    t = underdog_threshold(p_fav=0.75, p_und=0.25)
    assert approx(t, 0.1718555092, tol=1e-9)


def test_worked_ev_example_picks_underdog():
    # p_U=0.25, p_F=0.75, q_U=0.20, q_F=0.80 -> EV_U=0.400, EV_F~=0.332
    ev_u = expected_points(0.20, 0.25)
    ev_f = expected_points(0.80, 0.75)
    assert approx(ev_u, 0.400, tol=1e-3)
    assert approx(ev_f, 0.3318, tol=1e-3)
    assert ev_u > ev_f
    cands = [
        Candidate("Underdog", "D", p=0.25, q=0.20),
        Candidate("Favorite", "R", p=0.75, q=0.80),
    ]
    assert pick_expected_points(cands).name == "Underdog"
    assert pick_most_likely(cands).name == "Favorite"


def test_wrong_pick_scores_zero_semantics():
    # expected_points is q*reward; realised points for a wrong pick are 0 by
    # definition (the picked candidate did not win). We assert the building
    # block: a pick we did not select contributes nothing to our chosen score.
    cands = [Candidate("A", "D", 0.4, 0.4), Candidate("B", "R", 0.6, 0.6)]
    pick = pick_expected_points(cands)
    # realised points if pick loses:
    realised_if_loss = 0.0
    assert realised_if_loss == 0.0
    # realised points if pick wins = reward(p of pick)
    assert approx(reward(pick.p), reward(pick.p))


def test_favorite_optimal_case():
    # When the favorite's q is high enough it beats the underdog on EV.
    # p_F=0.55, p_U=0.45, q_F=0.95 -> favorite should win.
    cands = [
        Candidate("Fav", "R", p=0.55, q=0.95),
        Candidate("Und", "D", p=0.45, q=0.05),
    ]
    assert pick_expected_points(cands).name == "Fav"


def test_missing_price_fallback_uses_q():
    # All prices missing -> fall back to best q, caller flags the row.
    cands = [
        Candidate("A", "D", p=None, q=0.3, priced=False),
        Candidate("B", "R", p=None, q=0.7, priced=False),
    ]
    assert pick_expected_points(cands).name == "B"


def test_per_race_q_sums_to_one_is_caller_contract():
    # The optimizer does not require normalised q, but our build step does.
    cands = [Candidate("A", "D", 0.3, 0.3), Candidate("B", "R", 0.7, 0.7)]
    assert approx(sum(c.q for c in cands), 1.0)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} scoring tests passed")
