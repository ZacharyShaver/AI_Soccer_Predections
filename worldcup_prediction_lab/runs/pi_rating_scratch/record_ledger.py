"""Scratch (not committed): fusion-ledger entry for the pi-rating null."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from wc_predictor.lab import fusion_ledger

with open("runs/pi_rating_scratch/evaluate.json", encoding="utf-8") as f:
    r = json.load(f)

fusion_ledger.record(
    {
        "agent": "claude",
        "task": "new_model_class",
        "exp_id": "pi-rating",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": {
            "model_class": (
                "pi-ratings (Constantinou & Fenton 2013): per-team home/away rating pair, "
                "goal-difference discrepancy updates with cross-ground gamma flow; adapted "
                "with neutral-venue mean-rating convention and a Poisson goal-split "
                "probability layer (T=2.6)"
            ),
            "sweep": "lam x gamma x total_goals (24 configs) on the FIRST half of the eval window",
            "best_config": r["best_config"],
            "protocol": "winner scored on the untouched SECOND half, paired vs elo_recalibrated",
        },
        "samples": {
            "hist_second_half_holdout": {
                "n": r["holdout_second_half"]["n"],
                "rps": r["holdout_second_half"]["pi_rps"],
                "elo_recalibrated_rps": r["holdout_second_half"]["elo_rps"],
            }
        },
        "holdout_vs_recalibrated_paired": {
            "mean_diff": r["holdout_second_half"]["paired_mean_diff_pi_minus_elo"],
            "ci95": r["holdout_second_half"]["ci95"],
            "excludes_0": r["holdout_second_half"]["excludes_0"],
            "positive_means_pi_worse": True,
        },
        "notes": (
            "NULL RESULT. Best swept pi-rating config is +0.0010 RPS WORSE than "
            "elo_recalibrated on the holdout half (CI spans 0 -> tie-to-worse), far from "
            "the dixon_coles/fusion champions. The model class's differentiator (per-team "
            "learned home advantage) is diluted in neutral-heavy international football. "
            "Not graduated to the full blocked protocol; scratch under runs/pi_rating_scratch/. "
            "Bradley-Terry-Davidson deprioritized on the same evidence base: its one "
            "differentiator is an explicit draw parameter, and the edge-hunt decomposition "
            "showed our draw model is already market-grade (the market gap is in H/A, not "
            "draws) - noting that Dixon-Coles was also once deprioritized and later won, so "
            "BTD stays on the backlog rather than closed."
        ),
        "promote": False,
    }
)
print("ledger entry written")
