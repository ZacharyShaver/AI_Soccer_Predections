"""Scratch (not committed): fusion-ledger entry for dc_squad_fusion."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from wc_predictor.lab import fusion_ledger

with open("runs/dc_squad_fusion_scratch/results.json", encoding="utf-8") as f:
    r = json.load(f)

fusion_ledger.record(
    {
        "agent": "claude",
        "task": "dc_elo_fusion_stacking",
        "exp_id": "dc-squad-fusion",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": {
            "variant_id": "dc_squad_fusion",
            "constituents": ["dixon_coles_tuned", "squad_value"],
            "pool": "log",
            "lam": 0.7,
            "test_design": (
                "cleanest test: champion's FROZEN weight 0.7, swap only the Elo leg "
                "(zero selection freedom); OOF-weight version run as confirmation"
            ),
            "promotion_rule": "beat the CURRENT CHAMPION dc_elo_fusion paired, CI excluding 0",
        },
        "samples": {
            "hist_15k": {
                "n": r["n"],
                "rps": r["squad_leg_frozen_0.7_rps"],
                "champion_dc_elo_fusion_rps": r["champion_dc_recal_rps"],
            },
            "market964": {
                key: value
                for key, value in r["market964"]["challenger_squad_leg"].items()
            },
        },
        "history_frozen_vs_champion_paired": r["frozen_0.7_vs_champion_paired"],
        "history_oof_vs_champion_paired": r["oof"]["vs_champion_paired"],
        "market964_vs_champion_paired": r["market964"]["challenger_vs_champion_paired"],
        "notes": (
            "Stacks the two 2026-07-02 promotions: dc_elo_fusion's Elo leg swapped for "
            "squad_value so the pool inherits the Transfermarkt squad signal the goal-based "
            "DC leg cannot see. Beats the incumbent champion on history (frozen-weight test, "
            "CI excl 0) AND on market964 (CI excl 0). Full-argmin lam == frozen 0.7. "
            "Champion chain: elo_recalibrated 0.17438 -> dixon_coles_tuned 0.17262 -> "
            "dc_elo_fusion 0.17230 -> dc_squad_fusion 0.17219."
        ),
        "promote": True,
    }
)
print("ledger entry written")
