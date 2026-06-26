"""Recalibrated host-aware Elo: faster K and a wider, fuller draw mass.

Pure reparameterization of the baseline Elo (no new feature) found via a weight
sweep on 2026-06-26. Three changes, each validated to help on BOTH the WC-2026
walk-forward backtest AND a 15.8k-match online walk-forward over full history
(so it is signal, not overfit to the tournament):

- ``k_factor`` 20 -> 30: ratings adapt faster (echoes the P5 K=30 hint).
- ``draw_base_probability`` 0.27 -> 0.33: more (but still argmax-safe) draw mass.
- ``draw_rating_scale`` 400 -> 600: draw mass decays more slowly as the rating
  gap widens, fixing draws being under-priced in close-ish matches.

Home advantage is deliberately LEFT at 75: lowering it looked best on the 60-match
WC sample but was strictly worse on 15.8k historical matches (classic overfitting).

Sweep result: RPS 0.1762 -> 0.1748 (history) and 0.1763 -> 0.1739 (WC-60), with
log loss and Brier improving on both samples.
"""

from __future__ import annotations

VARIANT_ID = "elo_calibrated"
DESCRIPTION = "Host-aware Elo with faster K and recalibrated draw mass (no new feature)."
FEATURE_IDEA = "none (reparameterization): k_factor 30, draw_base 0.33, draw_rating_scale 600."


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn
    from wc_predictor.models.elo import EloModel

    return EloModel(
        k_factor=30.0,
        home_advantage=75.0,
        draw_base_probability=0.33,
        draw_rating_scale=600.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
