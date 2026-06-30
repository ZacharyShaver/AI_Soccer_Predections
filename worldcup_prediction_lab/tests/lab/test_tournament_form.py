from __future__ import annotations

import pandas as pd
import pytest

from wc_predictor.forecast_live import (
    _fixture_match_row,
    _team_names,
    _training_matches,
    load_silver_data,
    split_live_fixtures,
)
from wc_predictor.config import settings
from wc_predictor.evaluation.elo_vs_market import MATCHES_FILE
from wc_predictor.lab import registry
from wc_predictor.lab.variants.tournament_form import build_model

_HAVE_MATCHES = (settings.SILVER_DIR / MATCHES_FILE).exists()
needs_matches = pytest.mark.skipif(not _HAVE_MATCHES, reason="silver matches parquet absent")


def _generic_match_row() -> pd.Series:
    return pd.Series(
        {
            "match_id": "unit",
            "home_team_id": "HOT",
            "away_team_id": "NEUTRAL",
            "neutral": False,
            "tournament": "FIFA World Cup",
        }
    )


def test_registry_discovers_tournament_form():
    found = registry.discover()
    assert "tournament_form" in found
    model = registry.build("tournament_form", generated_at_utc="2026-06-29T00:00:00Z")
    assert hasattr(model, "fit") and hasattr(model, "predict_match")


def test_tournament_form_adjusts_home_advantage_from_static_residuals():
    model = build_model(generated_at_utc="2026-06-29T00:00:00Z")
    row = _generic_match_row()
    base = model.home_advantage

    model._tform = {"HOT": 0.40, "NEUTRAL": 0.0}
    boosted = model._home_advantage_elo(row, "HOT", "NEUTRAL")
    assert boosted - base > 0.0

    model._tform = {"COLD": -0.40, "NEUTRAL": 0.0}
    docked = model._home_advantage_elo(row, "COLD", "NEUTRAL")
    assert docked - base < 0.0

    model._tform = {"HOT": 1.0, "COLD": -1.0}
    capped_positive = model._home_advantage_elo(row, "HOT", "COLD")
    assert capped_positive - base == pytest.approx(60.0)

    model._tform = {"COLD": -1.0, "HOT": 1.0}
    capped_negative = model._home_advantage_elo(row, "COLD", "HOT")
    assert capped_negative - base == pytest.approx(-60.0)


@needs_matches
def test_tournament_form_fit_emits_normalized_fixture_probabilities():
    matches_df, fixtures_df, teams_df = load_silver_data()
    model = build_model(generated_at_utc="2026-06-29T00:00:00Z")
    model.fit(_training_matches(matches_df, training_cutoff="2026-06-20"))

    forecast_fixtures = split_live_fixtures(
        fixtures_df,
        as_of="2026-06-21",
    ).forecast_fixtures
    assert not forecast_fixtures.empty

    names = _team_names(teams_df)
    match_row = _fixture_match_row(forecast_fixtures.iloc[0], names)
    prediction = model.predict_match(match_row)
    probs = [prediction.prob_home, prediction.prob_draw, prediction.prob_away]

    assert sum(probs) == pytest.approx(1.0)
    assert all(0.0 <= prob <= 1.0 for prob in probs)
