from __future__ import annotations

import pandas as pd
import pytest

from wc_predictor.models.dixon_coles import DixonColesModel


def _match(mid, date, home, away, home_score, away_score, *, neutral=False, occurrence_index=0):
    return {
        "match_id": mid,
        "date": date,
        "home_team_id": home,
        "away_team_id": away,
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "neutral": neutral,
        "occurrence_index": occurrence_index,
    }


def test_decisive_win_raises_winner_attack_and_loser_defense_weakness():
    """Positive defense = stronger defense (subtracted from the opponent's log-rate)."""

    model = DixonColesModel()
    model.fit(pd.DataFrame([_match("m1", "2020-01-01", "alpha", "beta", 3, 0)]))

    assert model.get_attack("alpha") > 0.0  # scored 3, attack improves
    assert model.get_defense("beta") < 0.0  # conceded 3, defense worsens
    assert model.get_attack("beta") < 0.0  # scored 0, attack worsens
    assert model.get_defense("alpha") > 0.0  # conceded 0, defense improves


def test_predict_match_probabilities_sum_to_one_and_are_bounded():
    model = DixonColesModel()
    model.fit(
        pd.DataFrame(
            [
                _match("m1", "2020-01-01", "alpha", "beta", 2, 1),
                _match("m2", "2020-01-08", "beta", "alpha", 0, 0),
            ]
        )
    )
    row = pd.Series(_match("p1", "2020-02-01", "alpha", "beta", 0, 0))
    pred = model.predict_match(row)

    probs = (pred.prob_home, pred.prob_draw, pred.prob_away)
    assert sum(probs) == pytest.approx(1.0, abs=1e-9)
    assert all(0.0 <= p <= 1.0 for p in probs)
    assert pred.home_expected_goals > 0.0
    assert pred.away_expected_goals > 0.0


def test_predict_scoreline_grid_mass_is_near_complete():
    model = DixonColesModel()
    model.fit(pd.DataFrame([_match("m1", "2020-01-01", "alpha", "beta", 1, 1)]))
    row = pd.Series(_match("p1", "2020-02-01", "alpha", "beta", 0, 0))

    distribution = model.predict_scoreline(row)
    finite_mass = sum(distribution.probabilities.values())
    assert finite_mass + distribution.tail_probability == pytest.approx(1.0, abs=1e-6)
    assert finite_mass > 0.99


def test_unknown_teams_default_to_neutral_zero_ratings():
    model = DixonColesModel()
    row = pd.Series(_match("p1", "2020-02-01", "unseen_a", "unseen_b", 0, 0))
    pred = model.predict_match(row)

    assert pred.prob_home > pred.prob_away  # default home edge still applies
    assert pred.prob_home == pytest.approx(1.0 - pred.prob_draw - pred.prob_away, abs=1e-9)


def test_neutral_venue_removes_home_edge_asymmetry():
    model = DixonColesModel()
    neutral_row = pd.Series(_match("p1", "2020-02-01", "alpha", "beta", 0, 0, neutral=True))
    pred = model.predict_match(neutral_row)
    assert pred.home_expected_goals == pytest.approx(pred.away_expected_goals, abs=1e-9)


def test_fit_is_order_independent_of_input_row_order_given_same_chronology():
    rows = [
        _match("m1", "2020-01-01", "alpha", "beta", 2, 0),
        _match("m2", "2020-01-08", "beta", "alpha", 1, 1),
        _match("m3", "2020-01-15", "alpha", "gamma", 0, 0),
    ]
    forward = DixonColesModel()
    forward.fit(pd.DataFrame(rows))

    shuffled = DixonColesModel()
    shuffled.fit(pd.DataFrame([rows[2], rows[0], rows[1]]))

    assert forward.get_attack("alpha") == pytest.approx(shuffled.get_attack("alpha"))
    assert forward.home_edge == pytest.approx(shuffled.home_edge)
