"""Scratch (not committed): verify the sweep-best DixonColes config on all 3 bars + paired CI."""

from __future__ import annotations

import json

import pandas as pd

from wc_predictor.evaluation.elo_vs_market import (
    MARKET_ODDS_FILE,
    MATCHES_FILE,
    _read_parquet,
    align_matches_with_market,
)
from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score
from wc_predictor.config import settings
from wc_predictor.lab import eval_harness as eh
from wc_predictor.lab.registry import build as registry_build
from wc_predictor.models.dixon_coles import DixonColesModel

BEST = {
    "learning_rate": 0.03,
    "shrinkage": 0.0002,
    "rho": -0.05,
    "home_edge_init": 0.32,
    "home_edge_learning_rate": 0.0,
}


def _outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def paired_history(matches: pd.DataFrame) -> dict:
    start = pd.Timestamp(eh.HISTORY_EVAL_START)
    dc = DixonColesModel(**BEST)
    elo = eh.recalibrated_elo()
    dc_rps, elo_rps = [], []
    for row in matches.itertuples(index=False):
        record = row._asdict()
        series = pd.Series(record)
        if record["date"] >= start:
            actual = _outcome(record["home_score"], record["away_score"])
            dp = dc.predict_match(series)
            dc_rps.append(
                ranked_probability_score(
                    eh._normalize((dp.prob_home, dp.prob_draw, dp.prob_away)), actual
                )
            )
            ep = elo.predict_match(series)
            elo_rps.append(
                ranked_probability_score(
                    eh._normalize((ep.prob_home, ep.prob_draw, ep.prob_away)), actual
                )
            )
        dc._update_from_match(series)
        elo._update_from_match(series)

    n = len(dc_rps)
    diffs = [d - e for d, e in zip(dc_rps, elo_rps)]
    point, low, high, _ = bootstrap_ci(diffs, n_boot=1000, alpha=0.05, seed=20260630)
    return {
        "n": n,
        "dixon_coles_mean_rps": sum(dc_rps) / n,
        "elo_recalibrated_mean_rps": sum(elo_rps) / n,
        "paired_mean_diff_dc_minus_elo": point,
        "ci95": [low, high],
        "excludes_0": (low > 0.0) or (high < 0.0),
        "dixon_coles_better_on_n_matches": sum(1 for d in diffs if d < 0),
        "total_matches": n,
    }


def main() -> None:
    matches = eh.load_history_matches()
    out: dict = {}

    out["history_point"] = eh.score_on_history(DixonColesModel(**BEST), matches=matches)
    print("history_point:", json.dumps(out["history_point"], indent=2))

    out["history_paired_vs_elo_recalibrated"] = paired_history(matches)
    print("paired vs elo:", json.dumps(out["history_paired_vs_elo_recalibrated"], indent=2))

    def build_dc(**kw):
        return DixonColesModel(**BEST, **kw)

    out["wc_played"] = eh.score_on_wc60(build_dc)
    print("wc_played:", json.dumps(out["wc_played"], indent=2))

    raw_matches = _read_parquet(settings.SILVER_DIR / MATCHES_FILE)
    market_odds = _read_parquet(settings.SILVER_DIR / MARKET_ODDS_FILE)
    aligned, _alignment = align_matches_with_market(raw_matches, market_odds)

    # Reuse the same leak-free walk-forward attach helper as scratch.py, with BEST kwargs.
    import sys

    sys.path.insert(0, "runs/dixon_coles_scratch")
    from scratch import attach_dixon_coles_predictions  # noqa: E402

    def attach_with_best(aligned_df, matches_df):
        from wc_predictor.evaluation.elo_vs_market import _has_value, _normalize_dates

        evaluation = _normalize_dates(aligned_df)
        train_matches = _normalize_dates(matches_df)
        train_matches = train_matches[
            _has_value(train_matches["home_team_id"])
            & _has_value(train_matches["away_team_id"])
            & train_matches["home_score"].notna()
            & train_matches["away_score"].notna()
        ].copy()
        sort_columns = ["date"]
        if "occurrence_index" in train_matches.columns:
            sort_columns.append("occurrence_index")
        if "match_id" in train_matches.columns:
            sort_columns.append("match_id")
        train_matches = train_matches.sort_values(sort_columns, kind="mergesort").reset_index(
            drop=True
        )
        evaluation = evaluation.sort_values(
            ["date", "match_id", "market_row_id"], kind="mergesort"
        ).reset_index(drop=True)

        model = DixonColesModel(**BEST)
        train_index = 0
        predictions = []
        for match_date, date_matches in evaluation.groupby("date", sort=True):
            while (
                train_index < len(train_matches)
                and train_matches.iloc[train_index]["date"] < match_date
            ):
                model._update_from_match(train_matches.iloc[train_index])
                train_index += 1
            for _, row in date_matches.iterrows():
                prediction = model.predict_match(row)
                predictions.append(
                    {
                        "dc_prob_home": prediction.prob_home,
                        "dc_prob_draw": prediction.prob_draw,
                        "dc_prob_away": prediction.prob_away,
                    }
                )
        return pd.concat([evaluation, pd.DataFrame(predictions)], axis=1)

    frame = attach_with_best(aligned, raw_matches)

    def predict_fn(row: pd.Series):
        return (row["dc_prob_home"], row["dc_prob_draw"], row["dc_prob_away"])

    out["market964"] = eh.score_on_market964(predict_fn, frame=frame)
    print("market964:", json.dumps(out["market964"], indent=2))

    with open("runs/dixon_coles_scratch/verify_best.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
