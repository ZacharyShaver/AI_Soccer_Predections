"""Draw-aware Elo challenger.

The live miss pattern showed that top-pick accuracy was being dragged down by
draws. This variant does not rewrite history or force draws to be the top pick;
it tests a forward-looking probability calibration hypothesis: the baseline Elo
may be too thin on draw mass, especially for tournament fixtures.
"""

from __future__ import annotations

from wc_predictor.models.elo import EloModel, EloPrediction


VARIANT_ID = "draw_guard"
DESCRIPTION = "Host-aware Elo with a small capped draw-probability guardrail."
FEATURE_IDEA = (
    "Move a modest amount of mass from home/away outcomes into draw probability "
    "to test whether the live ledger is under-pricing draws."
)

DRAW_BOOST = 0.06
DRAW_CAP = 0.34


class DrawGuardElo(EloModel):
    """Elo model that modestly boosts draw probability after baseline scoring."""

    model_version = "draw_guard_v1"

    def predict_match(self, match_row):
        prediction = super().predict_match(match_row)
        target_draw = min(DRAW_CAP, prediction.prob_draw + DRAW_BOOST)
        added_draw_mass = max(0.0, target_draw - prediction.prob_draw)
        non_draw_mass = prediction.prob_home + prediction.prob_away
        if added_draw_mass <= 0.0 or non_draw_mass <= 0.0:
            return prediction

        scale = max(0.0, (non_draw_mass - added_draw_mass) / non_draw_mass)
        prob_home = prediction.prob_home * scale
        prob_draw = prediction.prob_draw + added_draw_mass
        prob_away = prediction.prob_away * scale
        total = prob_home + prob_draw + prob_away
        if total <= 0.0:
            raise ValueError("draw_guard probabilities have no mass")

        prob_home /= total
        prob_draw /= total
        prob_away = max(0.0, 1.0 - prob_home - prob_draw)
        return EloPrediction(
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
            pre_match_home_rating=prediction.pre_match_home_rating,
            pre_match_away_rating=prediction.pre_match_away_rating,
            home_advantage_elo=prediction.home_advantage_elo,
        )


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return DrawGuardElo(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
