"""Scratch (not committed): coarse hyperparameter sweep for DixonColesModel on history."""

from __future__ import annotations

import json

from wc_predictor.lab import eval_harness as eh
from wc_predictor.models.dixon_coles import DixonColesModel

matches = eh.load_history_matches()


def score(**kwargs):
    model = DixonColesModel(**kwargs)
    result = eh.score_on_history(model, matches=matches)
    return result["rps"]


def main() -> None:
    # Round 1: learning_rate x shrinkage (the two knobs controlling online
    # convergence speed/stability -- analogous to Elo's K-factor).
    round1 = []
    for lr in (0.03, 0.06, 0.10, 0.15):
        for shrink in (0.0002, 0.0008, 0.002, 0.005):
            rps = score(learning_rate=lr, shrinkage=shrink)
            round1.append({"learning_rate": lr, "shrinkage": shrink, "rps": rps})
    round1.sort(key=lambda r: r["rps"])
    print("=== round 1: learning_rate x shrinkage ===")
    for r in round1[:8]:
        print(r)
    best1 = round1[0]

    # Round 2: rho (low-score correction) at the best lr/shrinkage.
    round2 = []
    for rho in (-0.25, -0.20, -0.15, -0.10, -0.05, 0.0):
        rps = score(
            learning_rate=best1["learning_rate"], shrinkage=best1["shrinkage"], rho=rho
        )
        round2.append({"rho": rho, "rps": rps})
    round2.sort(key=lambda r: r["rps"])
    print("=== round 2: rho ===")
    for r in round2:
        print(r)
    best2 = round2[0]

    # Round 3: home_edge_init x home_edge_learning_rate.
    round3 = []
    for hei in (0.0, 0.10, 0.18, 0.25, 0.32):
        for helr in (0.0, 0.01, 0.02, 0.04):
            rps = score(
                learning_rate=best1["learning_rate"],
                shrinkage=best1["shrinkage"],
                rho=best2["rho"],
                home_edge_init=hei,
                home_edge_learning_rate=helr,
            )
            round3.append({"home_edge_init": hei, "home_edge_learning_rate": helr, "rps": rps})
    round3.sort(key=lambda r: r["rps"])
    print("=== round 3: home_edge_init x home_edge_learning_rate ===")
    for r in round3[:8]:
        print(r)
    best3 = round3[0]

    best_config = {
        "learning_rate": best1["learning_rate"],
        "shrinkage": best1["shrinkage"],
        "rho": best2["rho"],
        "home_edge_init": best3["home_edge_init"],
        "home_edge_learning_rate": best3["home_edge_learning_rate"],
    }
    final_rps = score(**best_config)
    print("=== best config ===")
    print(json.dumps({**best_config, "history_rps": final_rps}, indent=2))
    with open("runs/dixon_coles_scratch/sweep_best.json", "w", encoding="utf-8") as f:
        json.dump({**best_config, "history_rps": final_rps}, f, indent=2)


if __name__ == "__main__":
    main()
