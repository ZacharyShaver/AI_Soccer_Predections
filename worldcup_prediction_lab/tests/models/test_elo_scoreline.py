import pytest
import pandas as pd

from wc_predictor.models.base import ScorelineDistribution
from wc_predictor.models import elo
from wc_predictor.models.elo import elo_model


OUTCOME_TOLERANCE = 0.015


def _match(
    match_id,
    date,
    home_team_id,
    away_team_id,
    home_score,
    away_score,
    *,
    tournament="Friendly",
    neutral=True,
    occurrence_index=0,
):
    return {
        "match_id": match_id,
        "date": date,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_team": home_team_id,
        "away_team": away_team_id,
        "home_score": home_score,
        "away_score": away_score,
        "tournament": tournament,
        "neutral": neutral,
        "occurrence_index": occurrence_index,
    }


def _fixture(home_team_id="alpha", away_team_id="beta", *, neutral=True):
    return pd.Series(
        {
            "match_id": f"{home_team_id}-{away_team_id}",
            "date": "2026-06-01",
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "home_team": home_team_id,
            "away_team": away_team_id,
            "tournament": "Friendly",
            "neutral": neutral,
            "occurrence_index": 0,
        }
    )


def _training_matches():
    return pd.DataFrame(
        [
            _match("m1", "2026-01-01", "alpha", "beta", 3, 0),
            _match("m2", "2026-01-02", "alpha", "gamma", 2, 0),
            _match("m3", "2026-01-03", "beta", "gamma", 1, 1),
            _match("m4", "2026-01-04", "delta", "alpha", 0, 2),
            _match("m5", "2026-01-05", "beta", "delta", 2, 0),
        ]
    )


def test_elo_scoreline_distribution_has_positive_xg_and_normalized_mass():
    model = elo_model(max_goals=10).fit(_training_matches())

    distribution = model.predict_scoreline(_fixture("alpha", "beta"))

    assert isinstance(distribution, ScorelineDistribution)
    assert distribution.home_expected_goals > 0.0
    assert distribution.away_expected_goals > 0.0
    assert distribution.tail_probability >= 0.0
    assert sum(distribution.probabilities.values()) + distribution.tail_probability == pytest.approx(
        1.0
    )
    assert all(probability >= 0.0 for probability in distribution.probabilities.values())


def test_scoreline_outcome_masses_match_m4_outcome_probabilities_with_documented_tolerance():
    model = elo_model(max_goals=10).fit(_training_matches())
    fixture = _fixture("alpha", "beta")

    outcome = model.predict_match(fixture)
    distribution = model.predict_scoreline(fixture)
    scoreline_home, scoreline_draw, scoreline_away = elo.outcome_probabilities_from_scoreline(
        distribution
    )

    assert scoreline_home == pytest.approx(outcome.prob_home, abs=OUTCOME_TOLERANCE)
    assert scoreline_draw == pytest.approx(outcome.prob_draw, abs=OUTCOME_TOLERANCE)
    assert scoreline_away == pytest.approx(outcome.prob_away, abs=OUTCOME_TOLERANCE)


def test_stronger_team_has_higher_home_win_probability_and_expected_goals():
    model = elo_model(max_goals=10).fit(_training_matches())

    strong_home = model.predict_scoreline(_fixture("alpha", "delta"))
    weak_home = model.predict_scoreline(_fixture("delta", "alpha"))
    strong_home_win, _, _ = elo.outcome_probabilities_from_scoreline(strong_home)
    weak_home_win, _, _ = elo.outcome_probabilities_from_scoreline(weak_home)

    assert strong_home_win > weak_home_win
    assert strong_home.home_expected_goals > weak_home.home_expected_goals


def test_over_under_and_btts_probabilities_are_bounded_and_matrix_consistent():
    model = elo_model(max_goals=10).fit(_training_matches())
    distribution = model.predict_scoreline(_fixture("alpha", "beta"))

    over_25 = elo.over_probability(distribution, 2.5)
    under_25 = elo.under_probability(distribution, 2.5)
    btts = elo.btts_probability(distribution)
    manual_over_25 = sum(
        probability
        for scoreline, probability in distribution.probabilities.items()
        if sum(int(goals) for goals in scoreline.split("-")) > 2.5
    )
    manual_btts = sum(
        probability
        for scoreline, probability in distribution.probabilities.items()
        if all(int(goals) > 0 for goals in scoreline.split("-"))
    )

    assert 0.0 <= over_25 <= 1.0
    assert 0.0 <= under_25 <= 1.0
    assert 0.0 <= btts <= 1.0
    assert over_25 == pytest.approx(manual_over_25)
    assert under_25 == pytest.approx(1.0 - over_25 - distribution.tail_probability)
    assert btts == pytest.approx(manual_btts)


def test_top_scoreline_helpers_are_sorted_and_deterministic():
    model = elo_model(max_goals=10).fit(_training_matches())
    fixture = _fixture("alpha", "beta")

    first = model.predict_scoreline(fixture)
    second = model.predict_scoreline(fixture)

    assert first == second
    assert elo.top_scoreline(first) == elo.top_scorelines(first, 1)[0]
    top_five = elo.top_scorelines(first, 5)
    assert len(top_five) == 5
    assert top_five == sorted(top_five, key=lambda item: (-item[1], item[0]))
