"""Scratch (not committed): score dixon_coles_poisson on the three established bars."""

from __future__ import annotations

import json

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.elo_vs_market import (
    MARKET_ODDS_FILE,
    MATCHES_FILE,
    _has_value,
    _normalize_dates,
    _read_parquet,
    align_matches_with_market,
)
from wc_predictor.lab import eval_harness as eh
from wc_predictor.lab import registry
from wc_predictor.models.dixon_coles import DixonColesModel


def attach_dixon_coles_predictions(aligned: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    evaluation = _normalize_dates(aligned)
    train_matches = _normalize_dates(matches)
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
    train_matches = train_matches.sort_values(sort_columns, kind="mergesort").reset_index(drop=True)
    evaluation = evaluation.sort_values(
        ["date", "match_id", "market_row_id"], kind="mergesort"
    ).reset_index(drop=True)

    model = DixonColesModel()
    train_index = 0
    predictions: list[dict[str, float]] = []
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


def main() -> None:
    results: dict[str, dict] = {}

    # 1) 15.8k-match online walk-forward history.
    hist = eh.score_on_history(DixonColesModel())
    results["history"] = hist
    print("history:", json.dumps(hist, indent=2))

    # 2) Leak-free WC-2026 walk-forward (played matches so far).
    wc = eh.score_on_wc60(lambda **kw: registry.build("dixon_coles_poisson", **kw))
    results["wc_played"] = wc
    print("wc_played:", json.dumps(wc, indent=2))

    # 3) 964-match market join, paired against the de-vigged market.
    matches = _read_parquet(settings.SILVER_DIR / MATCHES_FILE)
    market_odds = _read_parquet(settings.SILVER_DIR / MARKET_ODDS_FILE)
    aligned, _alignment = align_matches_with_market(matches, market_odds)
    frame = attach_dixon_coles_predictions(aligned, matches)

    def predict_fn(row: pd.Series):
        return (row["dc_prob_home"], row["dc_prob_draw"], row["dc_prob_away"])

    market = eh.score_on_market964(predict_fn, frame=frame)
    results["market964"] = market
    print("market964:", json.dumps(market, indent=2))

    with open("runs/dixon_coles_scratch/results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
