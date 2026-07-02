from __future__ import annotations

import pytest

from wc_predictor.lab import registry
from wc_predictor.lab.variants.dixon_coles_tuned import TUNED_KWARGS


def test_registry_discovers_dixon_coles_tuned():
    found = registry.discover()
    assert "dixon_coles_tuned" in found
    model = registry.build("dixon_coles_tuned", generated_at_utc="2026-06-30T00:00:00Z")
    assert hasattr(model, "fit") and hasattr(model, "predict_match")


def test_tuned_kwargs_fix_the_home_edge():
    model = registry.build("dixon_coles_tuned", generated_at_utc="2026-06-30T00:00:00Z")
    assert model.home_edge_learning_rate == pytest.approx(0.0)
    assert model.home_edge_init == pytest.approx(TUNED_KWARGS["home_edge_init"])


def test_tuned_home_edge_never_moves_across_updates():
    import pandas as pd

    model = registry.build("dixon_coles_tuned", generated_at_utc="2026-06-30T00:00:00Z")
    starting_edge = model.home_edge
    rows = [
        {
            "match_id": f"m{i}",
            "date": f"2020-01-{i + 1:02d}",
            "home_team_id": "alpha",
            "away_team_id": "beta",
            "home_team": "alpha",
            "away_team": "beta",
            "home_score": 3,
            "away_score": 0,
            "neutral": False,
            "occurrence_index": 0,
        }
        for i in range(5)
    ]
    for row in rows:
        model._update_from_match(pd.Series(row))
    assert model.home_edge == pytest.approx(starting_edge)
