import pytest
import pandas as pd

from wc_predictor.models.base import ScorelineDistribution
from wc_predictor.models.baseline import baseline_climatology


def _training_matches(home_scores, away_scores):
    return pd.DataFrame(
        [
            {
                "match_id": f"train-{index}",
                "date": f"2026-01-{index + 1:02d}",
                "home_team": f"Home {index}",
                "away_team": f"Away {index}",
                "home_score": home_score,
                "away_score": away_score,
                "neutral": False,
            }
            for index, (home_score, away_score) in enumerate(
                zip(home_scores, away_scores)
            )
        ]
    )


def _fixture(match_id="fixture-1", home_team="Argentina", away_team="Brazil"):
    return pd.Series(
        {
            "match_id": match_id,
            "home_team": home_team,
            "away_team": away_team,
            "neutral": True,
        }
    )


def test_baseline_climatology_predicts_normalized_probabilities_and_scoreline_distribution():
    model = baseline_climatology(max_goals=10)
    model.fit(_training_matches([2, 1, 0, 3], [1, 1, 2, 0]))

    prediction = model.predict_match(_fixture())

    assert prediction.prob_home + prediction.prob_draw + prediction.prob_away == pytest.approx(1.0)
    assert prediction.prob_home >= 0.0
    assert prediction.prob_draw >= 0.0
    assert prediction.prob_away >= 0.0
    assert isinstance(prediction.scoreline_distribution, ScorelineDistribution)

    scoreline = prediction.scoreline_distribution
    assert all(probability >= 0.0 for probability in scoreline.probabilities.values())
    assert scoreline.tail_probability >= 0.0
    assert sum(scoreline.probabilities.values()) + scoreline.tail_probability == pytest.approx(
        1.0
    )


def test_baseline_climatology_fit_uses_only_passed_training_rows():
    low_scoring = baseline_climatology(max_goals=10).fit(
        _training_matches([0, 1, 1, 0], [0, 0, 1, 1])
    )
    high_scoring = baseline_climatology(max_goals=10).fit(
        _training_matches([4, 5, 3, 6], [3, 4, 5, 2])
    )

    low_prediction = low_scoring.predict_match(_fixture())
    high_prediction = high_scoring.predict_match(_fixture())

    assert low_prediction.scoreline_distribution.home_expected_goals == pytest.approx(0.5)
    assert low_prediction.scoreline_distribution.away_expected_goals == pytest.approx(0.5)
    assert high_prediction.scoreline_distribution.home_expected_goals == pytest.approx(4.5)
    assert high_prediction.scoreline_distribution.away_expected_goals == pytest.approx(3.5)
    assert (
        low_prediction.scoreline_distribution.home_expected_goals
        != high_prediction.scoreline_distribution.home_expected_goals
    )


def test_baseline_climatology_ignores_team_strength_in_match_row():
    model = baseline_climatology(max_goals=10).fit(
        _training_matches([2, 2, 1, 0], [0, 1, 1, 2])
    )

    argentina_brazil = model.predict_match(
        _fixture(match_id="match-1", home_team="Argentina", away_team="Brazil")
    )
    tahiti_france = model.predict_match(
        _fixture(match_id="match-2", home_team="Tahiti", away_team="France")
    )

    assert argentina_brazil.prob_home == pytest.approx(tahiti_france.prob_home)
    assert argentina_brazil.prob_draw == pytest.approx(tahiti_france.prob_draw)
    assert argentina_brazil.prob_away == pytest.approx(tahiti_france.prob_away)
    assert (
        argentina_brazil.scoreline_distribution.probabilities
        == tahiti_france.scoreline_distribution.probabilities
    )
