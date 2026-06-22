import copy
import json
import math

import pandas as pd
import pytest

from wc_predictor.evaluation.metrics import (
    brier_score,
    home_draw_away_log_loss,
    ranked_probability_score,
)
from wc_predictor.evaluation.score_ledger import score_ledger


def _prediction(
    prediction_id: str,
    match_id: str,
    *,
    prob_home: float,
    prob_draw: float,
    prob_away: float,
    scorelines: dict[str, float] | None = None,
) -> dict:
    row = {
        "prediction_id": prediction_id,
        "match_id": match_id,
        "model_id": "unit_elo",
        "model_version": "v1",
        "generated_at_utc": "2026-06-21T12:00:00Z",
        "training_cutoff": "2026-06-20",
        "as_of": "2026-06-21",
        "prob_home": prob_home,
        "prob_draw": prob_draw,
        "prob_away": prob_away,
    }
    if scorelines is not None:
        row["scoreline_distribution"] = {
            "match_id": match_id,
            "model_id": "unit_elo",
            "generated_at_utc": "2026-06-21T12:00:00Z",
            "max_goals": 2,
            "home_expected_goals": 1.0,
            "away_expected_goals": 0.8,
            "probabilities": scorelines,
            "tail_probability": 0.0,
        }
    return row


def test_score_ledger_scores_completed_predictions_without_mutating_inputs():
    predictions = [
        _prediction(
            "p-home",
            "m-home",
            prob_home=0.7,
            prob_draw=0.2,
            prob_away=0.1,
            scorelines={"2-1": 0.6, "1-1": 0.4},
        ),
        _prediction(
            "p-draw",
            "m-draw",
            prob_home=0.2,
            prob_draw=0.6,
            prob_away=0.2,
            scorelines={"1-0": 0.5, "0-0": 0.5},
        ),
        _prediction(
            "p-pending",
            "m-pending",
            prob_home=0.1,
            prob_draw=0.2,
            prob_away=0.7,
        ),
    ]
    original_predictions = copy.deepcopy(predictions)
    results = pd.DataFrame(
        [
            {"match_id": "m-home", "home_score": 2, "away_score": 1},
            {"match_id": "m-draw", "home_score": 0, "away_score": 0},
        ]
    )

    evaluation, aggregate = score_ledger(predictions, results)

    assert predictions == original_predictions
    assert evaluation["prediction_id"].tolist() == ["p-home", "p-draw"]
    assert set(evaluation.columns) >= {
        "prediction_id",
        "match_id",
        "actual_home_score",
        "actual_away_score",
        "actual_outcome",
        "log_loss",
        "brier",
        "rps",
        "called_it",
        "exact_score_hit",
    }

    home_row = evaluation.set_index("prediction_id").loc["p-home"]
    assert home_row["actual_outcome"] == "home"
    assert home_row["log_loss"] == pytest.approx(
        home_draw_away_log_loss([0.7, 0.2, 0.1], "home")
    )
    assert home_row["brier"] == pytest.approx(brier_score([0.7, 0.2, 0.1], "home"))
    assert home_row["rps"] == pytest.approx(
        ranked_probability_score([0.7, 0.2, 0.1], "home")
    )
    assert bool(home_row["called_it"]) is True
    assert home_row["exact_score_hit"] == 1

    draw_row = evaluation.set_index("prediction_id").loc["p-draw"]
    assert draw_row["actual_outcome"] == "draw"
    assert bool(draw_row["called_it"]) is True
    assert draw_row["exact_score_hit"] == 1

    assert aggregate == {
        "n_total": 3,
        "n_scored": 2,
        "n_pending": 1,
        "mean_log_loss": pytest.approx(
            (
                home_draw_away_log_loss([0.7, 0.2, 0.1], "home")
                + home_draw_away_log_loss([0.2, 0.6, 0.2], "draw")
            )
            / 2
        ),
        "mean_brier": pytest.approx(
            (
                brier_score([0.7, 0.2, 0.1], "home")
                + brier_score([0.2, 0.6, 0.2], "draw")
            )
            / 2
        ),
        "mean_rps": pytest.approx(
            (
                ranked_probability_score([0.7, 0.2, 0.1], "home")
                + ranked_probability_score([0.2, 0.6, 0.2], "draw")
            )
            / 2
        ),
        "overall_accuracy": pytest.approx(1.0),
        "decisive_accuracy": pytest.approx(1.0),
        "exact_score_hit_rate": pytest.approx(1.0),
    }

    evaluation_again, aggregate_again = score_ledger(predictions, results)
    pd.testing.assert_frame_equal(evaluation, evaluation_again)
    assert aggregate_again == aggregate


def test_score_ledger_reads_jsonl_paths_and_ignores_non_finite_log_loss_in_mean(tmp_path):
    ledger_path = tmp_path / "predictions.jsonl"
    predictions = [
        _prediction(
            "p-inf-loss",
            "m-away",
            prob_home=1.0,
            prob_draw=0.0,
            prob_away=0.0,
        ),
        _prediction(
            "p-finite-loss",
            "m-home",
            prob_home=0.8,
            prob_draw=0.1,
            prob_away=0.1,
        ),
    ]
    ledger_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in predictions) + "\n",
        encoding="utf-8",
    )
    results = pd.DataFrame(
        [
            {"match_id": "m-away", "home_score": 0, "away_score": 1},
            {"match_id": "m-home", "home_score": 1, "away_score": 0},
        ]
    )

    evaluation, aggregate = score_ledger(ledger_path, results)

    assert evaluation["prediction_id"].tolist() == ["p-inf-loss", "p-finite-loss"]
    assert math.isinf(evaluation.loc[0, "log_loss"])
    assert aggregate["n_scored"] == 2
    assert aggregate["n_pending"] == 0
    assert aggregate["mean_log_loss"] == pytest.approx(-math.log(0.8))
    assert aggregate["mean_brier"] == pytest.approx(
        (
            brier_score([1.0, 0.0, 0.0], "away")
            + brier_score([0.8, 0.1, 0.1], "home")
        )
        / 2
    )
    assert aggregate["mean_rps"] == pytest.approx(
        (
            ranked_probability_score([1.0, 0.0, 0.0], "away")
            + ranked_probability_score([0.8, 0.1, 0.1], "home")
        )
        / 2
    )
    assert aggregate["overall_accuracy"] == pytest.approx(0.5)
    assert aggregate["decisive_accuracy"] == pytest.approx(0.5)
    assert aggregate["exact_score_hit_rate"] is None


def test_score_ledger_all_pending_predictions_do_not_error():
    predictions = [
        _prediction(
            "p-pending",
            "m-pending",
            prob_home=0.3,
            prob_draw=0.4,
            prob_away=0.3,
        )
    ]
    results = pd.DataFrame(columns=["match_id", "home_score", "away_score"])

    evaluation, aggregate = score_ledger(predictions, results)

    assert evaluation.empty
    assert aggregate == {
        "n_total": 1,
        "n_scored": 0,
        "n_pending": 1,
        "mean_log_loss": None,
        "mean_brier": None,
        "mean_rps": None,
        "overall_accuracy": None,
        "decisive_accuracy": None,
        "exact_score_hit_rate": None,
    }
