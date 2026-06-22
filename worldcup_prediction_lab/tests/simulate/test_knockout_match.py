"""Tests for the match-level simulator (P4 / S2)."""

import numpy as np

from wc_predictor.models.elo import EloModel
from wc_predictor.simulate.match_sim import (
    simulate_group_match,
    simulate_knockout,
)


def _model(ratings: dict[str, float]) -> EloModel:
    model = EloModel()
    model.ratings = dict(ratings)
    return model


def test_simulate_knockout_returns_one_of_the_two_teams():
    model = _model({"A": 1800, "B": 1600})
    rng = np.random.default_rng(0)
    winner = simulate_knockout(model, "A", "B", rng, neutral=True)
    assert winner in {"A", "B"}


def test_stronger_team_advances_more_often_in_knockouts():
    model = _model({"A": 2000, "B": 1500})
    rng = np.random.default_rng(42)
    wins_a = sum(simulate_knockout(model, "A", "B", rng, neutral=True) == "A" for _ in range(2000))
    assert wins_a > 1400  # clear favourite advances well over half the time


def test_knockout_is_symmetric_under_neutral_when_swapping_sides():
    # On a neutral tie, the stronger team's advance rate should not depend on
    # whether it is listed home or away.
    model = _model({"A": 1900, "B": 1600})
    a_home = sum(
        simulate_knockout(model, "A", "B", np.random.default_rng(s), neutral=True) == "A"
        for s in range(800)
    )
    a_away = sum(
        simulate_knockout(model, "B", "A", np.random.default_rng(s), neutral=True) == "A"
        for s in range(800)
    )
    assert abs(a_home - a_away) < 60  # within sampling noise; no home-slot bias


def test_simulate_group_match_returns_nonnegative_goals_and_favours_stronger():
    model = _model({"A": 2000, "B": 1500})
    rng = np.random.default_rng(7)
    home_goals_total = away_goals_total = 0
    for _ in range(2000):
        hg, ag = simulate_group_match(model, "A", "B", rng, neutral=True)
        assert hg >= 0 and ag >= 0 and isinstance(hg, int) and isinstance(ag, int)
        home_goals_total += hg
        away_goals_total += ag
    assert home_goals_total > away_goals_total  # stronger team scores more on average


def test_simulation_is_deterministic_for_a_fixed_seed():
    model = _model({"A": 1800, "B": 1700, "C": 1650})
    seq1 = [
        simulate_knockout(model, "A", "B", r, neutral=True)
        for r in [np.random.default_rng(123)]
    ]
    # same seed -> same group-match scoreline and same knockout winner
    s1 = simulate_group_match(model, "A", "C", np.random.default_rng(5), neutral=True)
    s2 = simulate_group_match(model, "A", "C", np.random.default_rng(5), neutral=True)
    assert s1 == s2
    w1 = simulate_knockout(model, "A", "B", np.random.default_rng(9), neutral=True)
    w2 = simulate_knockout(model, "A", "B", np.random.default_rng(9), neutral=True)
    assert w1 == w2
