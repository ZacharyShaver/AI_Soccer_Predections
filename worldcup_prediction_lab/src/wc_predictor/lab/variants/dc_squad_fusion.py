"""dc_elo_fusion with the squad_value Elo leg — the stacked champion.

Same log opinion pool (weight 0.7 on dixon_coles_tuned) as ``dc_elo_fusion``,
but the Elo leg is ``squad_value`` (recalibrated Elo + Transfermarkt
squad-value delta) instead of plain ``elo_recalibrated``. The Dixon-Coles leg
cannot see the squad signal (it is goal-rate based), so pooling inherits it.

Evidence (runs/dc_squad_fusion_scratch/experiment.py, 2026-07-02; ledger
``claude__dc-squad-fusion``): on the 15.9k history walk-forward, the CLEANEST
possible test — keep the champion's frozen weight 0.7, swap only the Elo
leg, zero selection freedom — beats dc_elo_fusion: RPS 0.17219 vs 0.17230,
paired 95% CI [-0.00014, -0.00008] EXCLUDES 0. The out-of-fold-weight version
agrees (CI [-0.00016, -0.00002]); the full-sample argmin weight is exactly
the frozen 0.7. Also significant on market964: 0.15547 vs 0.15563, paired CI
[-0.00026, -0.00006] excludes 0 (still behind the de-vigged market 0.14958,
like every model). Champion chain: elo_recalibrated 0.17438 →
dixon_coles_tuned 0.17262 → dc_elo_fusion 0.17230 → THIS 0.17219.
"""

from __future__ import annotations

from wc_predictor.lab.variants.dc_elo_fusion import DcEloFusionModel

VARIANT_ID = "dc_squad_fusion"
DESCRIPTION = (
    "dc_elo_fusion with the squad_value Elo leg — Dixon-Coles pooled with "
    "squad-value-aware Elo (current history champion)."
)
FEATURE_IDEA = (
    "Swap dc_elo_fusion's plain recalibrated-Elo leg for squad_value so the pool "
    "inherits the Transfermarkt squad-value signal the goal-based Dixon-Coles leg cannot see."
)

COMPONENT_VARIANTS = ("dixon_coles_tuned", "squad_value")


class DcSquadFusionModel(DcEloFusionModel):
    model_version = "dc_squad_fusion_v1"

    def __init__(self, *, generated_at_utc: str) -> None:
        super().__init__(generated_at_utc=generated_at_utc, components=COMPONENT_VARIANTS)


def build_model(*, generated_at_utc: str):
    return DcSquadFusionModel(generated_at_utc=generated_at_utc)
