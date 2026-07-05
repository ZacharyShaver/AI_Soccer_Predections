"""Scratch (not committed): pi-rating falsification rung on the history walk.

Coarse (lam, gamma) sweep scored on the FIRST HALF of the eval window only,
best config then scored on the SECOND HALF (holdout) with a paired CI vs
elo_recalibrated on the same matches. Cheap honest split for a first look:
if the holdout paired CI vs recalibrated excludes 0 in pi's favor, graduate
it to the full blocked-walk-forward protocol; if pi is clearly worse, record
the null and stop.
"""

from __future__ import annotations

import json
import sys

import pandas as pd

sys.path.insert(0, "runs/pi_rating_scratch")
from pi_model import PiRatingModel  # noqa: E402

from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score
from wc_predictor.lab import eval_harness as eh

LAM_GRID = [0.03, 0.06, 0.1, 0.15]
GAMMA_GRID = [0.3, 0.5, 0.7]
TOTAL_GRID = [2.4, 2.6]
SEED = 20260702


def _outcome(home_score, away_score) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def walk(config: dict, matches: pd.DataFrame, start: pd.Timestamp) -> list[float]:
    model = PiRatingModel(**config)
    rps: list[float] = []
    for row in matches.itertuples(index=False):
        record = row._asdict()
        series = pd.Series(record)
        if record["date"] >= start:
            p = model.predict_match(series)
            probs = eh._normalize((p.prob_home, p.prob_draw, p.prob_away))
            rps.append(ranked_probability_score(probs, _outcome(record["home_score"], record["away_score"])))
        model._update_from_match(series)
    return rps


def main() -> None:
    matches = eh.load_history_matches()
    start = pd.Timestamp(eh.HISTORY_EVAL_START)

    elo = eh.recalibrated_elo()
    elo_rps: list[float] = []
    for row in matches.itertuples(index=False):
        record = row._asdict()
        series = pd.Series(record)
        if record["date"] >= start:
            p = elo.predict_match(series)
            probs = eh._normalize((p.prob_home, p.prob_draw, p.prob_away))
            elo_rps.append(ranked_probability_score(probs, _outcome(record["home_score"], record["away_score"])))
        elo._update_from_match(series)
    n = len(elo_rps)
    half = n // 2

    results = []
    best = None
    for lam in LAM_GRID:
        for gamma in GAMMA_GRID:
            for total in TOTAL_GRID:
                config = {"lam": lam, "gamma": gamma, "total_goals": total}
                rps = walk(config, matches, start)
                first_half = sum(rps[:half]) / half
                results.append({**config, "first_half_rps": first_half})
                if best is None or first_half < best[0]:
                    best = (first_half, config, rps)
                print(f"lam={lam} gamma={gamma} T={total}: first-half RPS {first_half:.5f}", flush=True)

    _, best_config, best_rps = best
    holdout_pi = best_rps[half:]
    holdout_elo = elo_rps[half:]
    diffs = [a - b for a, b in zip(holdout_pi, holdout_elo)]
    point, low, high, _ = bootstrap_ci(diffs, n_boot=1000, alpha=0.05, seed=SEED)

    out = {
        "n_eval": n,
        "elo_recalibrated_full_rps": sum(elo_rps) / n,
        "sweep_first_half": sorted(results, key=lambda r: r["first_half_rps"])[:5],
        "best_config": best_config,
        "holdout_second_half": {
            "n": len(holdout_pi),
            "pi_rps": sum(holdout_pi) / len(holdout_pi),
            "elo_rps": sum(holdout_elo) / len(holdout_elo),
            "paired_mean_diff_pi_minus_elo": point,
            "ci95": [low, high],
            "excludes_0": (low > 0.0) or (high < 0.0),
        },
    }
    print(json.dumps(out, indent=1), flush=True)
    with open("runs/pi_rating_scratch/evaluate.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
