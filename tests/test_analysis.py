"""Smoke tests for the replay + simulation + threshold strategy."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from forecast import replay, simulate  # noqa: E402
from forecast.scoring import Candidate, pick_threshold, pick_expected_points, pick_most_likely  # noqa: E402


def test_threshold_logic():
    # EV pick is the underdog (q=0.08); below tau=0.15 -> switch to favorite.
    cs = [Candidate("Fav", "D", p=0.92, q=0.92), Candidate("Dog", "R", p=0.08, q=0.08)]
    assert pick_expected_points(cs).name == "Dog"       # pure EV takes the longshot
    assert pick_threshold(cs, 0.15).name == "Fav"       # threshold caps it
    assert pick_threshold(cs, 0.05).name == "Dog"       # low tau keeps EV pick
    # a genuine tossup underdog (q=0.4) is kept even at tau=0.15
    cs2 = [Candidate("A", "D", 0.55, 0.6), Candidate("B", "R", 0.45, 0.4)]
    assert pick_threshold(cs2, 0.15).name == pick_expected_points(cs2).name


def test_replay_runs_and_favorite_beats_underdog_2018():
    races = replay.load_races()
    assert len(races) > 300
    fav, _, _ = replay.realized_points(races, replay.pick_favorite)
    und, _, _ = replay.realized_points(races, replay.pick_underdog_ev)
    assert fav > und, "2018 proxy: favorites should beat all-underdog"


def test_sim_ev_matches_analytic_when_calibrated():
    # Small synthetic entry: analytic EV of the ev-pick ~= simulated mean (temp=1).
    races = [[("A", "D", 0.5, 0.5), ("B", "R", 0.5, 0.5)],
             [("C", "D", 0.3, 0.3), ("D", "R", 0.7, 0.7)]]
    out = simulate.simulate(races, n_draws=4000, swing_sd=0.0, dgp_temp=1.0)
    d = out["ev(all-underdog)"]
    assert abs(d["mean"] - d["analytic_ev"]) < 0.15, (d["mean"], d["analytic_ev"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
    print("\nANALYSIS SMOKE TESTS PASSED")
