import pandas as pd
import pytest

from wc_predictor.evaluation.metrics import (
    brier_score,
    home_draw_away_log_loss,
    ranked_probability_score,
)
from wc_predictor.evaluation.scorecard import build_scorecard


def _prediction(
    prediction_id: str,
    match_id: str,
    *,
    prob_home: float,
    prob_draw: float,
    prob_away: float,
) -> dict:
    return {
        "prediction_id": prediction_id,
        "match_id": match_id,
        "model_id": "unit_elo",
        "generated_at_utc": "2026-06-21T12:00:00Z",
        "training_cutoff": "2026-06-20",
        "as_of": "2026-06-21",
        "prob_home": prob_home,
        "prob_draw": prob_draw,
        "prob_away": prob_away,
    }


def _results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"match_id": "m-home", "home_score": 2, "away_score": 1},
            {"match_id": "m-draw", "home_score": 1, "away_score": 1},
            {"match_id": "m-away", "home_score": 0, "away_score": 2},
        ]
    )


def test_build_scorecard_reports_our_metrics_and_paired_market_subset():
    predictions = [
        _prediction("p-home", "m-home", prob_home=0.70, prob_draw=0.20, prob_away=0.10),
        _prediction("p-draw", "m-draw", prob_home=0.20, prob_draw=0.55, prob_away=0.25),
        _prediction("p-away", "m-away", prob_home=0.25, prob_draw=0.25, prob_away=0.50),
        _prediction("p-pending", "m-pending", prob_home=0.45, prob_draw=0.30, prob_away=0.25),
    ]
    market = pd.DataFrame(
        [
            {
                "match_id": "m-home",
                "market_prob_home": 0.60,
                "market_prob_draw": 0.25,
                "market_prob_away": 0.15,
            },
            {
                "match_id": "m-away",
                "market_prob_home": 0.30,
                "market_prob_draw": 0.30,
                "market_prob_away": 0.40,
            },
            {
                "match_id": "market-only",
                "market_prob_home": 0.10,
                "market_prob_draw": 0.20,
                "market_prob_away": 0.70,
            },
        ]
    )

    report = build_scorecard(predictions, _results(), market_df=market)

    assert report.aggregate["n_total"] == 4
    assert report.aggregate["n_scored"] == 3
    assert report.aggregate["n_pending"] == 1
    assert report.our_metrics["rps"].point == pytest.approx(
        (
            ranked_probability_score([0.70, 0.20, 0.10], "home")
            + ranked_probability_score([0.20, 0.55, 0.25], "draw")
            + ranked_probability_score([0.25, 0.25, 0.50], "away")
        )
        / 3
    )
    assert report.our_metrics["log_loss"].point == pytest.approx(
        (
            home_draw_away_log_loss([0.70, 0.20, 0.10], "home")
            + home_draw_away_log_loss([0.20, 0.55, 0.25], "draw")
            + home_draw_away_log_loss([0.25, 0.25, 0.50], "away")
        )
        / 3
    )
    assert report.our_metrics["brier"].point == pytest.approx(
        (
            brier_score([0.70, 0.20, 0.10], "home")
            + brier_score([0.20, 0.55, 0.25], "draw")
            + brier_score([0.25, 0.25, 0.50], "away")
        )
        / 3
    )

    comparison = report.market_comparison
    assert comparison.paired_n == 2
    assert comparison.metrics["rps"]["ours"].point == pytest.approx(
        (
            ranked_probability_score([0.70, 0.20, 0.10], "home")
            + ranked_probability_score([0.25, 0.25, 0.50], "away")
        )
        / 2
    )
    assert comparison.metrics["rps"]["market"].point == pytest.approx(
        (
            ranked_probability_score([0.60, 0.25, 0.15], "home")
            + ranked_probability_score([0.30, 0.30, 0.40], "away")
        )
        / 2
    )
    assert comparison.metrics["rps"]["diff_market_minus_ours"].point == pytest.approx(
        comparison.metrics["rps"]["market"].point - comparison.metrics["rps"]["ours"].point
    )


def test_build_scorecard_omits_small_sample_cis_but_adds_them_at_or_above_floor():
    predictions = [
        _prediction("p-home", "m-home", prob_home=0.70, prob_draw=0.20, prob_away=0.10),
        _prediction("p-draw", "m-draw", prob_home=0.20, prob_draw=0.55, prob_away=0.25),
        _prediction("p-away", "m-away", prob_home=0.25, prob_draw=0.25, prob_away=0.50),
    ]
    market = pd.DataFrame(
        [
            {"match_id": "m-home", "prob_home": 0.60, "prob_draw": 0.25, "prob_away": 0.15},
            {"match_id": "m-away", "prob_home": 0.30, "prob_draw": 0.30, "prob_away": 0.40},
        ]
    )

    small = build_scorecard(predictions, _results(), market_df=market, ci_floor=30)
    assert small.our_metrics["rps"].ci is None
    assert small.our_metrics["rps"].ci_omitted_reason == "n=3 < ci_floor=30"
    assert small.market_comparison.metrics["rps"]["diff_market_minus_ours"].ci is None

    with_cis = build_scorecard(predictions, _results(), market_df=market, ci_floor=2)
    assert with_cis.our_metrics["rps"].ci is not None
    assert with_cis.our_metrics["rps"].ci.n == 3
    assert with_cis.market_comparison.metrics["rps"]["diff_market_minus_ours"].ci is not None
    assert with_cis.market_comparison.metrics["rps"]["diff_market_minus_ours"].ci.n == 2


def test_build_scorecard_handles_no_resolved_ledger_forecasts():
    predictions = [
        _prediction("p-pending", "m-pending", prob_home=0.45, prob_draw=0.30, prob_away=0.25)
    ]
    results = pd.DataFrame(columns=["match_id", "home_score", "away_score"])

    report = build_scorecard(predictions, results)

    assert report.aggregate["n_total"] == 1
    assert report.aggregate["n_scored"] == 0
    assert report.our_metrics["rps"].point is None
    assert report.market_comparison.paired_n == 0
    assert "No ledger forecasts have resolved yet." in report.messages


def test_build_scorecard_is_deterministic_for_identical_inputs():
    predictions = [
        _prediction("p-home", "m-home", prob_home=0.70, prob_draw=0.20, prob_away=0.10),
        _prediction("p-draw", "m-draw", prob_home=0.20, prob_draw=0.55, prob_away=0.25),
        _prediction("p-away", "m-away", prob_home=0.25, prob_draw=0.25, prob_away=0.50),
    ]
    market = pd.DataFrame(
        [
            {"match_id": "m-home", "prob_home": 0.60, "prob_draw": 0.25, "prob_away": 0.15},
            {"match_id": "m-away", "prob_home": 0.30, "prob_draw": 0.30, "prob_away": 0.40},
        ]
    )

    first = build_scorecard(predictions, _results(), market_df=market, ci_floor=2)
    second = build_scorecard(predictions, _results(), market_df=market, ci_floor=2)

    assert first == second
