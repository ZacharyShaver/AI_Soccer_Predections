"""Tests for the elo_recalibrated variant (calibrated + flat tournament weights)."""

from __future__ import annotations

from wc_predictor.lab import registry
from wc_predictor.models.elo import DEFAULT_TOURNAMENT_WEIGHTS


def test_registry_discovers_elo_recalibrated():
    found = registry.discover()
    assert "elo_recalibrated" in found
    model = registry.build("elo_recalibrated", generated_at_utc="2026-06-26T00:00:00Z")
    assert hasattr(model, "fit") and hasattr(model, "predict_match")


def test_elo_recalibrated_keeps_calibrated_weights():
    model = registry.build("elo_recalibrated", generated_at_utc="2026-06-26T00:00:00Z")
    assert model.k_factor == 30.0
    assert model.home_advantage == 75.0  # lowering it overfit the WC sample
    assert model.draw_base_probability == 0.33
    assert model.draw_rating_scale == 600.0


def test_elo_recalibrated_flattens_tournament_weights():
    model = registry.build("elo_recalibrated", generated_at_utc="2026-06-26T00:00:00Z")
    # Every tournament the default table up/down-weights is flattened to 1.0.
    for tournament, default_weight in DEFAULT_TOURNAMENT_WEIGHTS.items():
        if default_weight != 1.0:
            assert model.tournament_weights[tournament] == 1.0
    assert model.default_tournament_weight == 1.0
