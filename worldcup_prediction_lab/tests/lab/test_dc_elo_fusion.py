from __future__ import annotations

import math

import pandas as pd
import pytest

from wc_predictor.lab import registry
from wc_predictor.lab.variants.dc_elo_fusion import DC_WEIGHT


def _match(mid, date, home, away, home_score, away_score, *, neutral=False):
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
        "occurrence_index": 0,
        "tournament": "Friendly",
    }


TRAIN = pd.DataFrame(
    [
        _match("m1", "2020-01-01", "alpha", "beta", 3, 0),
        _match("m2", "2020-01-08", "beta", "alpha", 0, 2),
        _match("m3", "2020-01-15", "alpha", "gamma", 1, 1),
    ]
)


def _build():
    return registry.build("dc_elo_fusion", generated_at_utc="2026-07-02T00:00:00Z")


def test_registry_discovers_dc_elo_fusion():
    found = registry.discover()
    assert "dc_elo_fusion" in found
    model = _build()
    assert hasattr(model, "fit")
    assert hasattr(model, "predict_match")
    assert hasattr(model, "predict_scoreline")
    assert hasattr(model, "_update_from_match")


def test_fused_probabilities_are_valid_and_pool_the_components():
    model = _build().fit(TRAIN)
    row = pd.Series(_match("p1", "2020-02-01", "alpha", "beta", 0, 0))

    fused = model.predict_match(row)
    probs = (fused.prob_home, fused.prob_draw, fused.prob_away)
    assert sum(probs) == pytest.approx(1.0, abs=1e-9)
    assert all(0.0 < p < 1.0 for p in probs)

    # The log pool is a weighted geometric mean: reproduce it from the
    # components to pin the wiring (weights, order, normalization).
    dc = model.dixon_coles.predict_match(row)
    elo = model.elo.predict_match(row)
    expected = [
        (d**DC_WEIGHT) * (e ** (1.0 - DC_WEIGHT))
        for d, e in zip(
            (dc.prob_home, dc.prob_draw, dc.prob_away),
            (elo.prob_home, elo.prob_draw, elo.prob_away),
        )
    ]
    total = sum(expected)
    for got, want in zip(probs, expected):
        assert got == pytest.approx(want / total, abs=1e-9)


def test_alpha_is_favored_after_dominant_results():
    model = _build().fit(TRAIN)
    row = pd.Series(_match("p1", "2020-02-01", "alpha", "beta", 0, 0, neutral=True))
    fused = model.predict_match(row)
    assert fused.prob_home > fused.prob_away


def test_scoreline_delegates_to_dixon_coles():
    model = _build().fit(TRAIN)
    row = pd.Series(_match("p1", "2020-02-01", "alpha", "beta", 0, 0))
    scoreline = model.predict_scoreline(row)
    assert scoreline.model_id == model.dixon_coles.model_id
    finite_mass = sum(scoreline.probabilities.values())
    assert math.isfinite(finite_mass) and finite_mass > 0.99


def test_update_from_match_moves_both_components():
    model = _build().fit(TRAIN)
    elo_before = model.elo.get_rating("alpha")
    dc_before = model.dixon_coles.get_attack("alpha")

    model._update_from_match(pd.Series(_match("m4", "2020-02-01", "alpha", "beta", 4, 0)))

    assert model.elo.get_rating("alpha") != elo_before
    assert model.dixon_coles.get_attack("alpha") != dc_before
