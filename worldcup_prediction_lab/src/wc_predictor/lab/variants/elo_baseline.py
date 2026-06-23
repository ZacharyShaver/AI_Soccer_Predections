"""Control variant: the proven host-aware Elo. Every challenger must beat this."""

from __future__ import annotations

VARIANT_ID = "elo_baseline"
DESCRIPTION = "Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776)."
FEATURE_IDEA = "none (control)"


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn
    from wc_predictor.models.elo import EloModel

    return EloModel(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
