"""Scratch (not committed): paired history RPS, dixon_coles_poisson vs recalibrated Elo."""

from __future__ import annotations

import json

import pandas as pd

from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score
from wc_predictor.lab import eval_harness as eh
from wc_predictor.models.dixon_coles import DixonColesModel


def _outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def main() -> None:
    matches = eh.load_history_matches()
    start = pd.Timestamp(eh.HISTORY_EVAL_START)

    dc = DixonColesModel()
    elo = eh.recalibrated_elo()

    dc_rps: list[float] = []
    elo_rps: list[float] = []
    for row in matches.itertuples(index=False):
        record = row._asdict()
        series = pd.Series(record)
        if record["date"] >= start:
            actual = _outcome(record["home_score"], record["away_score"])
            dc_pred = dc.predict_match(series)
            dc_probs = eh._normalize((dc_pred.prob_home, dc_pred.prob_draw, dc_pred.prob_away))
            dc_rps.append(ranked_probability_score(dc_probs, actual))

            elo_pred = elo.predict_match(series)
            elo_probs = eh._normalize((elo_pred.prob_home, elo_pred.prob_draw, elo_pred.prob_away))
            elo_rps.append(ranked_probability_score(elo_probs, actual))

        dc._update_from_match(series)
        elo._update_from_match(series)

    n = len(dc_rps)
    diffs = [d - e for d, e in zip(dc_rps, elo_rps)]  # positive -> dixon_coles worse
    point, low, high, _ = bootstrap_ci(diffs, n_boot=1000, alpha=0.05, seed=20260630)
    better_count = sum(1 for d in diffs if d < 0)
    result = {
        "n": n,
        "dixon_coles_mean_rps": sum(dc_rps) / n,
        "elo_recalibrated_mean_rps": sum(elo_rps) / n,
        "paired_mean_diff_dc_minus_elo": point,
        "ci95": [low, high],
        "excludes_0": (low > 0.0) or (high < 0.0),
        "dixon_coles_better_on_n_matches": better_count,
        "total_matches": n,
    }
    print(json.dumps(result, indent=2))
    with open("runs/dixon_coles_scratch/paired_significance.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
