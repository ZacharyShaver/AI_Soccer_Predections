import math
import json

import pandas as pd
import pytest

from wc_predictor.evaluation.backtest import run_backtest


class StubModel:
    def __init__(self):
        self.fit_dates = []

    def fit(self, train_matches_df):
        self.fit_dates = list(train_matches_df["date"].dt.strftime("%Y-%m-%d"))
        return self

    def predict_match(self, match_row):
        return {"prob_home": 0.60, "prob_draw": 0.25, "prob_away": 0.15}


def _synthetic_matches():
    return pd.DataFrame(
        [
            {
                "match_id": "m1",
                "date": "2026-01-01",
                "home_score": 2,
                "away_score": 0,
            },
            {
                "match_id": "m2",
                "date": "2026-01-03",
                "home_score": 1,
                "away_score": 1,
            },
            {
                "match_id": "m3",
                "date": "2026-01-05",
                "home_score": 0,
                "away_score": 1,
            },
            {
                "match_id": "m4",
                "date": "2026-01-07",
                "home_score": 3,
                "away_score": 1,
            },
            {
                "match_id": "m5",
                "date": "2026-01-09",
                "home_score": 0,
                "away_score": 0,
            },
        ]
    )


def test_walk_forward_backtest_trains_before_cutoff_writes_ledger_and_scores(tmp_path):
    fitted_models = []

    def model_factory():
        model = StubModel()
        fitted_models.append(model)
        return model

    report = run_backtest(
        _synthetic_matches(),
        model_factory=model_factory,
        train_start="2026-01-01",
        first_prediction_date="2026-01-05",
        final_prediction_date="2026-01-10",
        prediction_window_days=2,
        model_id="stub_model",
        runs_dir=tmp_path,
    )

    assert [window.training_cutoff for window in report.windows] == [
        "2026-01-05",
        "2026-01-07",
        "2026-01-09",
    ]
    assert [model.fit_dates for model in fitted_models] == [
        ["2026-01-01", "2026-01-03"],
        ["2026-01-01", "2026-01-03", "2026-01-05"],
        ["2026-01-01", "2026-01-03", "2026-01-05", "2026-01-07"],
    ]

    assert [window.match_ids for window in report.windows] == [["m3"], ["m4"], ["m5"]]
    for window in report.windows:
        assert all(prediction_date >= window.training_cutoff for prediction_date in window.prediction_dates)
        assert all(prediction_date < window.window_end for prediction_date in window.prediction_dates)
        assert all(train_date < window.training_cutoff for train_date in window.training_dates)

    assert report.total_matches_predicted == 3
    assert report.window_count == 3
    assert report.mean_log_loss == pytest.approx(
        (-math.log(0.15) - math.log(0.60) - math.log(0.25)) / 3
    )
    assert len(report.per_match_log_loss) == 3
    assert len(report.per_match_brier) == 3
    assert len(report.per_match_rps) == 3

    ledger_path = tmp_path / "predictions" / "date=2026-01-05" / "predictions.jsonl"
    assert ledger_path.exists()
    ledger_rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["match_id"] for row in ledger_rows] == ["m3", "m4", "m5"]
    assert {row["training_cutoff"] for row in ledger_rows} == {
        "2026-01-05",
        "2026-01-07",
        "2026-01-09",
    }
    assert all(row["as_of"] == row["training_cutoff"] for row in ledger_rows)
