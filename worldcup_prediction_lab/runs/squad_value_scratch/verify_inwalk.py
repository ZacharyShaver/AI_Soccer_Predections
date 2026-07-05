"""Scratch (not committed): TRUE in-walk verification of the deployed squad_value model.

The grid search re-scored a stored walk offline (delta at prediction time
only). The deployed variant's delta also feeds the rating update's expected
score, so verify the frozen config with the real class end-to-end: paired
walk vs elo_recalibrated, same protocol as verify_best.py in the DC lane.
"""

from __future__ import annotations

import json

import pandas as pd

from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score
from wc_predictor.lab import eval_harness as eh
from wc_predictor.lab.variants.elo_recalibrated import recalibrated_elo_kwargs
from wc_predictor.lab.variants.squad_value import SquadValueEloModel


def _outcome(home_score, away_score) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def main() -> None:
    matches = eh.load_history_matches()
    start = pd.Timestamp(eh.HISTORY_EVAL_START)

    sv = SquadValueEloModel(**recalibrated_elo_kwargs())  # no host fn: bar convention
    elo = eh.recalibrated_elo()

    sv_rps, elo_rps = [], []
    for row in matches.itertuples(index=False):
        record = row._asdict()
        series = pd.Series(record)
        if record["date"] >= start:
            actual = _outcome(record["home_score"], record["away_score"])
            sp = sv.predict_match(series)
            sv_rps.append(
                ranked_probability_score(
                    eh._normalize((sp.prob_home, sp.prob_draw, sp.prob_away)), actual
                )
            )
            ep = elo.predict_match(series)
            elo_rps.append(
                ranked_probability_score(
                    eh._normalize((ep.prob_home, ep.prob_draw, ep.prob_away)), actual
                )
            )
        sv._update_from_match(series)
        elo._update_from_match(series)

    n = len(sv_rps)
    diffs = [s - e for s, e in zip(sv_rps, elo_rps)]
    point, low, high, _ = bootstrap_ci(diffs, n_boot=1000, alpha=0.05, seed=20260702)
    result = {
        "n": n,
        "squad_value_rps": sum(sv_rps) / n,
        "elo_recalibrated_rps": sum(elo_rps) / n,
        "paired_mean_diff": point,
        "ci95": [low, high],
        "excludes_0": (low > 0.0) or (high < 0.0),
        "better_on_n_matches": sum(1 for d in diffs if d < 0),
    }
    print(json.dumps(result, indent=2))
    with open("runs/squad_value_scratch/verify_inwalk.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
