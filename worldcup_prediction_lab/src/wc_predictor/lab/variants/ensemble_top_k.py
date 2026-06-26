"""Top-model probability ensemble.

Combines the current walk-forward leaders by averaging their H/D/A outcome
probabilities. This is intentionally simple and falsifiable: if the ensemble
does not beat the baseline out-of-sample, it should be retired like any other
variant.
"""

from __future__ import annotations

from wc_predictor.models.elo import EloPrediction


VARIANT_ID = "ensemble_top_k"
DESCRIPTION = "Equal-weight ensemble of the strongest walk-forward form variants."
FEATURE_IDEA = (
    "Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; "
    "delegate scoreline shape to ewma_goal_form."
)
COMPONENT_VARIANTS = ("ewma_goal_form", "form_trend", "opp_adj_form")


class EnsembleTopKModel:
    model_version = "ensemble_top_k_v1"

    def __init__(self, *, generated_at_utc: str) -> None:
        from wc_predictor.lab import registry

        self.generated_at_utc = generated_at_utc
        self.components = [
            registry.build(variant_id, generated_at_utc=generated_at_utc)
            for variant_id in COMPONENT_VARIANTS
        ]

    def fit(self, train_matches_df):
        for component in self.components:
            component.fit(train_matches_df)
        return self

    def predict_match(self, match_row):
        predictions = [component.predict_match(match_row) for component in self.components]
        n = float(len(predictions))
        prob_home = sum(prediction.prob_home for prediction in predictions) / n
        prob_draw = sum(prediction.prob_draw for prediction in predictions) / n
        prob_away = sum(prediction.prob_away for prediction in predictions) / n
        total = prob_home + prob_draw + prob_away
        if total <= 0.0:
            raise ValueError("ensemble probabilities have no mass")

        return EloPrediction(
            prob_home=prob_home / total,
            prob_draw=prob_draw / total,
            prob_away=prob_away / total,
            pre_match_home_rating=sum(
                prediction.pre_match_home_rating for prediction in predictions
            )
            / n,
            pre_match_away_rating=sum(
                prediction.pre_match_away_rating for prediction in predictions
            )
            / n,
            home_advantage_elo=sum(
                prediction.home_advantage_elo for prediction in predictions
            )
            / n,
        )

    def predict_scoreline(self, match_row):
        return self.components[0].predict_scoreline(match_row)


def build_model(*, generated_at_utc: str):
    return EnsembleTopKModel(generated_at_utc=generated_at_utc)
