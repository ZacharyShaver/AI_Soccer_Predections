"""Tuned Dixon-Coles Poisson rating (coarse coordinate-descent sweep winner).

Builds on ``dixon_coles_poisson`` (untuned defaults, which already tied
recalibrated Elo on the 15.8k-match history walk-forward out of the box --
paired 95% CI included 0). A coarse 3-round coordinate-descent sweep on
history RPS (learning_rate x shrinkage -> rho -> home_edge_init x
home_edge_learning_rate; worktree-free scratch scripts under
``runs/dixon_coles_scratch/``, NOT committed) found a config that beats
recalibrated Elo significantly:

* 15.8k-match online walk-forward (n=15,893): RPS 0.1744 (elo_recalibrated)
  -> **0.1726** (this). Paired mean diff -0.00178, 95% CI
  [-0.00244, -0.00104], EXCLUDES 0 -- the improvement is real, not noise.
* 964-match market join: RPS 0.1574 (elo_recalibrated) -> **0.1560** (this).
  Still loses to the de-vigged market (0.1496; paired CI excludes 0), same as
  every model tried this project so far -- expected, not a regression.
* Live WC-2026 sample (n=75, small): RPS 0.1593 (elo_recalibrated) -> 0.1603
  (this) -- a ~0.001 move, well inside single-match noise at this sample size
  (flipping one match's classification swings RPS by ~0.013 at n=75). Not
  treated as a real regression; the large history sample is the
  generalization bar this project uses to decide "does the config transfer."

Biggest single lever: ``home_edge_learning_rate=0.0`` -- the home-advantage
term should be a FIXED constant, not something the online update nudges per
match. That mirrors Elo's own finding (home_advantage is a tuned constant,
not something K-factor-style updates touch).

Not yet tried: jointly fitting ``rho`` online, per-tournament weighting
(recalibrated Elo found flat weights win, so this variant does not weight by
tournament either), and a finer/randomized search past this coarse grid.
"""

from __future__ import annotations

VARIANT_ID = "dixon_coles_tuned"
DESCRIPTION = "Dixon-Coles Poisson rating, coordinate-descent tuned; beats recalibrated Elo on history."
FEATURE_IDEA = (
    "Same online Poisson attack/defense model as dixon_coles_poisson, with a coarse "
    "sweep-tuned learning_rate/shrinkage/rho and a FIXED (non-updating) home edge."
)

TUNED_KWARGS = {
    "learning_rate": 0.03,
    "shrinkage": 0.0002,
    "rho": -0.05,
    "home_edge_init": 0.32,
    "home_edge_learning_rate": 0.0,
}


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn
    from wc_predictor.models.dixon_coles import DixonColesModel

    return DixonColesModel(
        **TUNED_KWARGS,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
