"""Log opinion pool of dixon_coles_tuned and elo_recalibrated.

First fusion in this lab to beat its best single constituent. The prior
fusion null (Codex T2: "no recipe beats the best constituent") tested only
near-identical Elo-family variants; dixon_coles_tuned broke that precondition
— it beats elo_recalibrated on the 15.9k history walk-forward on the mean yet
wins only ~50.7% of individual matches, i.e. the two models' errors are
genuinely decorrelated.

Evidence (runs/dc_fusion_scratch/experiment.py, 2026-07-02; ledger entries
``claude__fuse-dc-elo-{linear,log}``):

* History walk-forward, weight chosen OUT-OF-FOLD (6 time blocks, each block
  scored with the weight picked only on earlier blocks; n=13,249): fused RPS
  0.17111 vs dixon_coles_tuned 0.17141 on the same matches — paired 95% CI
  [-0.00048, -0.00011] EXCLUDES 0. Beats elo_recalibrated by -0.00188
  (CI excludes 0). The selected weight was stable across blocks
  (0.85 -> 0.70), so the deployed weight freezes the full-history argmin 0.7.
* Played-WC 2026 (n=76): fused 0.1583 vs DC 0.1588 vs Elo 0.1594 — best of
  the three (small sample; treated as "no regression", not proof).
* market964: fused 0.1556 vs DC 0.1560 (right direction, CI spans 0); still
  loses to the de-vigged market 0.1496 like every model so far.

The magnitude is small (~0.2% relative RPS) but statistically real under the
same paired-CI standard every other promotion here has met.
"""

from __future__ import annotations

from wc_predictor.models.elo import EloPrediction

VARIANT_ID = "dc_elo_fusion"
DESCRIPTION = (
    "Log opinion pool of dixon_coles_tuned (w=0.7) and elo_recalibrated — "
    "first fusion to beat its best constituent."
)
FEATURE_IDEA = (
    "Weighted geometric mean of the H/D/A probabilities from the two best, genuinely "
    "decorrelated model classes (goal-based Dixon-Coles + outcome-based recalibrated Elo); "
    "scoreline shape delegated to the Dixon-Coles component."
)

COMPONENT_VARIANTS = ("dixon_coles_tuned", "elo_recalibrated")
DC_WEIGHT = 0.7  # full-history argmin on the log pool; out-of-fold path was 0.85 -> 0.70


class DcEloFusionModel:
    model_version = "dc_elo_fusion_v1"

    def __init__(self, *, generated_at_utc: str) -> None:
        from wc_predictor.lab import registry

        self.generated_at_utc = generated_at_utc
        self.dixon_coles, self.elo = (
            registry.build(variant_id, generated_at_utc=generated_at_utc)
            for variant_id in COMPONENT_VARIANTS
        )

    def fit(self, train_matches_df):
        self.dixon_coles.fit(train_matches_df)
        self.elo.fit(train_matches_df)
        return self

    def _update_from_match(self, match_row) -> None:
        self.dixon_coles._update_from_match(match_row)
        self.elo._update_from_match(match_row)

    def predict_match(self, match_row):
        from wc_predictor.lab.fusion_recipes import logarithmic_opinion_pool

        dc = self.dixon_coles.predict_match(match_row)
        elo = self.elo.predict_match(match_row)
        prob_home, prob_draw, prob_away = logarithmic_opinion_pool(
            [
                (dc.prob_home, dc.prob_draw, dc.prob_away),
                (elo.prob_home, elo.prob_draw, elo.prob_away),
            ],
            weights=[DC_WEIGHT, 1.0 - DC_WEIGHT],
        )
        # Rating context comes from the Elo component: Dixon-Coles ratings live
        # in log-goal-rate space, not Elo points, so they can't be averaged in.
        return EloPrediction(
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
            pre_match_home_rating=elo.pre_match_home_rating,
            pre_match_away_rating=elo.pre_match_away_rating,
            home_advantage_elo=elo.home_advantage_elo,
        )

    def predict_scoreline(self, match_row):
        return self.dixon_coles.predict_scoreline(match_row)


def build_model(*, generated_at_utc: str):
    return DcEloFusionModel(generated_at_utc=generated_at_utc)
