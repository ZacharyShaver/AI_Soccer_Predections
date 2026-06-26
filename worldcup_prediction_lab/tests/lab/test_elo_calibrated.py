"""Tests for the elo_calibrated variant (reparameterized baseline)."""

from __future__ import annotations

from wc_predictor.lab import registry


def test_registry_discovers_elo_calibrated():
    found = registry.discover()
    assert "elo_calibrated" in found
    model = registry.build("elo_calibrated", generated_at_utc="2026-06-26T00:00:00Z")
    assert hasattr(model, "fit") and hasattr(model, "predict_match")


def test_elo_calibrated_uses_swept_weights():
    model = registry.build("elo_calibrated", generated_at_utc="2026-06-26T00:00:00Z")
    assert model.k_factor == 30.0
    # Home advantage is deliberately unchanged (lowering it overfit the WC sample).
    assert model.home_advantage == 75.0
    assert model.draw_base_probability == 0.33
    assert model.draw_rating_scale == 600.0


def test_elo_calibrated_prices_draws_higher_than_baseline_for_even_teams():
    baseline = registry.build("elo_baseline", generated_at_utc="2026-06-26T00:00:00Z")
    calibrated = registry.build("elo_calibrated", generated_at_utc="2026-06-26T00:00:00Z")
    # Two unrated teams => equal ratings => the closest possible matchup.
    base_probs = baseline._outcome_probabilities(1500.0, 1500.0, 0.0)
    cal_probs = calibrated._outcome_probabilities(1500.0, 1500.0, 0.0)
    assert cal_probs[1] > base_probs[1]  # draw probability is higher
    assert abs(sum(cal_probs) - 1.0) < 1e-9  # still a valid distribution
