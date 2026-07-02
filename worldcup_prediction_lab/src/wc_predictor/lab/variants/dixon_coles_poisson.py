"""Dixon-Coles-style online Poisson attack/defense rating, as a lab variant.

Every other variant in this registry is an ``EloModel`` subclass tweaking a
feature that nudges the home-advantage delta -- still scoring outcomes
directly. This one is a genuinely different model class: it scores *goals*
(team attack/defense ratings in log-rate space, bivariate Poisson with the
Dixon-Coles low-score correction) rather than win probability, then derives
H/D/A by summing the scoreline grid. See ``wc_predictor.models.dixon_coles``
for the full design notes and the online-vs-batch-MLE tradeoff.
"""

from __future__ import annotations

VARIANT_ID = "dixon_coles_poisson"
DESCRIPTION = "Online Dixon-Coles bivariate-Poisson attack/defense rating (not Elo-derived)."
FEATURE_IDEA = (
    "Team attack/defense ratings in log-goal-rate space, online Poisson-regression "
    "gradient updates, Dixon-Coles low-score tau correction, host-aware home edge."
)


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn
    from wc_predictor.models.dixon_coles import DixonColesModel

    return DixonColesModel(
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
