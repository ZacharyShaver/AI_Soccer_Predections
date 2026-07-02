from __future__ import annotations

import pandas as pd
import pytest

from wc_predictor.config import settings
from wc_predictor.evaluation.elo_vs_market import MATCHES_FILE
from wc_predictor.lab import registry

_HAVE_MATCHES = (settings.SILVER_DIR / MATCHES_FILE).exists()
needs_matches = pytest.mark.skipif(not _HAVE_MATCHES, reason="silver matches parquet absent")


def test_registry_discovers_dixon_coles_poisson():
    found = registry.discover()
    assert "dixon_coles_poisson" in found
    model = registry.build("dixon_coles_poisson", generated_at_utc="2026-06-30T00:00:00Z")
    assert hasattr(model, "fit")
    assert hasattr(model, "predict_match")
    assert hasattr(model, "predict_scoreline")
    assert hasattr(model, "_update_from_match")


@needs_matches
def test_dixon_coles_poisson_fits_and_predicts_on_real_silver_fixtures():
    from wc_predictor.forecast_live import (
        _fixture_match_row,
        _team_names,
        _training_matches,
        load_silver_data,
        split_live_fixtures,
    )

    matches_df, fixtures_df, teams_df = load_silver_data()
    model = registry.build("dixon_coles_poisson", generated_at_utc="2026-06-29T00:00:00Z")
    model.fit(_training_matches(matches_df, training_cutoff="2026-06-20"))

    forecast_fixtures = split_live_fixtures(fixtures_df, as_of="2026-06-21").forecast_fixtures
    assert not forecast_fixtures.empty

    names = _team_names(teams_df)
    match_row = _fixture_match_row(forecast_fixtures.iloc[0], names)
    prediction = model.predict_match(match_row)
    probs = [prediction.prob_home, prediction.prob_draw, prediction.prob_away]

    assert sum(probs) == pytest.approx(1.0, abs=1e-6)
    assert all(0.0 <= p <= 1.0 for p in probs)

    scoreline = model.predict_scoreline(match_row)
    assert scoreline.model_id == "dixon_coles_poisson_v1"
