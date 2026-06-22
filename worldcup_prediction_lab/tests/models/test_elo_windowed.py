"""Tests for the windowed Elo variant (P5 / R0)."""

import pandas as pd

from wc_predictor.models.elo import EloModel
from wc_predictor.models.elo_windowed import WindowedEloModel


def _matches(rows):
    return pd.DataFrame(
        rows,
        columns=["date", "home_team_id", "away_team_id", "home_score", "away_score", "neutral"],
    )


def test_window_excludes_old_matches_from_ratings():
    # A thrashes B repeatedly long ago, then nothing recent.
    rows = [
        ("2010-01-01", "A", "B", 5, 0, True),
        ("2010-02-01", "A", "B", 5, 0, True),
        ("2024-06-01", "C", "D", 1, 1, True),  # recent anchor so max(date) is 2024
    ]
    windowed = WindowedEloModel(window_years=2).fit(_matches(rows))
    # A's only results are >14 years old -> outside the 2y window -> reverts to base.
    assert windowed.get_rating("A") == windowed.base_rating
    assert windowed.get_rating("B") == windowed.base_rating


def test_within_window_matches_full_model_behaviour():
    rows = [
        ("2024-01-01", "A", "B", 3, 0, True),
        ("2024-03-01", "C", "A", 0, 2, True),
    ]
    full = EloModel().fit(_matches(rows))
    windowed = WindowedEloModel(window_years=5).fit(_matches(rows))
    # All matches are inside a 5y window, so ratings should be identical.
    for team in ("A", "B", "C"):
        assert windowed.get_rating(team) == full.get_rating(team)


def test_windowed_model_supports_prediction_protocol():
    rows = [("2024-01-01", "A", "B", 2, 0, True), ("2024-02-01", "A", "C", 1, 0, True)]
    model = WindowedEloModel(window_years=4).fit(_matches(rows))
    row = pd.Series({"home_team_id": "A", "away_team_id": "B", "neutral": True})
    p = model.predict_match(row)
    assert abs((p.prob_home + p.prob_draw + p.prob_away) - 1.0) < 1e-9
    dist = model.predict_scoreline(row)
    assert dist.model_id == "elo_window_4y"
    assert dist.home_expected_goals > 0
