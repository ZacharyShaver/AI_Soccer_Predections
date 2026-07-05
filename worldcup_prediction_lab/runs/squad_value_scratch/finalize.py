"""Scratch (not committed): wc76 + market964 for squad_value, then ledger entry."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from wc_predictor.lab import eval_harness as eh
from wc_predictor.lab import fusion_ledger, registry
from wc_predictor.lab.variants.elo_recalibrated import recalibrated_elo_kwargs
from wc_predictor.lab.variants.squad_value import CAP, COEF, MIN_VALUED_PLAYERS, SquadValueEloModel


def main() -> None:
    out: dict = {}

    out["wc_played"] = eh.score_on_wc60(
        lambda **kw: registry.build("squad_value", **kw)
    )
    print("wc_played:", json.dumps(out["wc_played"], indent=1), flush=True)

    frame = eh.build_market964_frame(
        model_factory=lambda: SquadValueEloModel(**recalibrated_elo_kwargs())
    )
    out["market964"] = eh.score_on_market964(None, frame=frame)
    print("market964:", json.dumps(out["market964"], indent=1), flush=True)

    with open("runs/squad_value_scratch/verify_inwalk.json", encoding="utf-8") as f:
        inwalk = json.load(f)
    with open("runs/squad_value_scratch/evaluate.json", encoding="utf-8") as f:
        evaluate = json.load(f)

    fusion_ledger.record(
        {
            "agent": "claude",
            "task": "new_strength_data",
            "exp_id": "squad_value",
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "config": {
                "variant_id": "squad_value",
                "signal": (
                    "Transfermarkt monthly squad value (top-15 citizen market values, "
                    "730-day staleness), strictly-before-match lookup"
                ),
                "delta": f"clip({COEF} * ln(V_home/V_away), +/-{CAP})",
                "min_valued_players": MIN_VALUED_PLAYERS,
                "coverage_share_history": evaluate["coverage"]["share"],
                "selection": "6-block time-ordered walk-forward (out-of-fold), frozen full argmin",
                "promotion_rule": (
                    "beat elo_recalibrated on history out-of-fold with paired CI excluding 0"
                ),
            },
            "samples": {
                "hist_15k_inwalk": {
                    "n": inwalk["n"],
                    "rps": inwalk["squad_value_rps"],
                    "elo_recalibrated_rps": inwalk["elo_recalibrated_rps"],
                },
                "wc_played": out["wc_played"],
                "market964": out["market964"],
            },
            "history_oof_vs_recalibrated_paired": evaluate["oof"]["vs_base_paired"],
            "history_inwalk_vs_recalibrated_paired": {
                "n": inwalk["n"],
                "mean_diff": inwalk["paired_mean_diff"],
                "ci95": inwalk["ci95"],
                "excludes_0": inwalk["excludes_0"],
                "better_on_n_matches": inwalk["better_on_n_matches"],
            },
            "covered_subsample_paired": evaluate["covered_subsample_full_argmin_vs_base"],
            "notes": (
                "First non-scoreline strength signal to clear the bar (transfermarkt-datasets, "
                "CC0). Out-of-fold config selection AND true in-walk verification both exclude 0. "
                "Effect concentrated on the covered 59% of matches; uncovered matches fall back "
                "to plain elo_recalibrated. Next: stack the delta under dc_elo_fusion's Elo "
                "constituent."
            ),
            "promote": True,
        }
    )
    print("ledger entry written", flush=True)


if __name__ == "__main__":
    main()
