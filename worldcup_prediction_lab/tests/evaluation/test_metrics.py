import math

import pytest

from wc_predictor.evaluation.metrics import (
    bootstrap_ci,
    brier_score,
    calibration_bins,
    exact_score_hit,
    expected_goals_mae,
    home_draw_away_log_loss,
    ranked_probability_score,
    scoreline_log_loss,
    top_k_score_hit,
)


def test_brier_score_uses_multiclass_sum_of_squared_errors():
    # Actual home: (0.7 - 1)^2 + (0.2 - 0)^2 + (0.1 - 0)^2 = 0.14
    assert brier_score([0.7, 0.2, 0.1], "home") == pytest.approx(0.14)


def test_home_draw_away_log_loss_uses_actual_outcome_probability():
    assert home_draw_away_log_loss([0.5, 0.3, 0.2], "home") == pytest.approx(
        -math.log(0.5),
        abs=1e-9,
    )


def test_ranked_probability_score_uses_ordered_home_draw_away_cdfs():
    # Actual draw. Predicted CDF: [0.2, 0.8], actual CDF: [0, 1].
    # RPS = ((0.2 - 0)^2 + (0.8 - 1)^2) / 2 = 0.04
    assert ranked_probability_score([0.2, 0.6, 0.2], "draw") == pytest.approx(0.04)


def test_scoreline_log_loss_uses_exact_score_probability():
    dist = {"1-0": 0.25, "1-1": 0.5, "0-1": 0.25}

    assert scoreline_log_loss(dist, (1, 1)) == pytest.approx(-math.log(0.5))


def test_exact_and_top_k_score_hits_use_scoreline_distribution_ranking():
    dist = {"0-0": 0.10, "1-0": 0.35, "1-1": 0.30, "2-1": 0.25}

    assert exact_score_hit(dist, (1, 0)) == 1
    assert exact_score_hit(dist, (2, 0)) == 0
    assert top_k_score_hit(dist, (1, 1), k=2) == 1
    assert top_k_score_hit(dist, (2, 1), k=2) == 0


def test_probability_vectors_must_sum_to_one():
    with pytest.raises(ValueError, match="sum to 1.0"):
        brier_score([0.5, 0.3, 0.3], "home")

    with pytest.raises(ValueError, match="sum to 1.0"):
        scoreline_log_loss({"1-0": 0.7, "1-1": 0.2}, (1, 0))


def test_expected_goals_mae_averages_home_and_away_absolute_errors():
    # (abs(1.8 - 2) + abs(0.7 - 1)) / 2 = 0.25
    assert expected_goals_mae(1.8, 0.7, 2, 1) == pytest.approx(0.25)


def test_calibration_bins_return_mean_prediction_empirical_rate_and_count():
    bins = calibration_bins(
        probs_list=[0.05, 0.20, 0.40, 0.80],
        outcomes_list=[0, 1, 1, 1],
        n_bins=2,
    )

    assert bins == [
        {"mean_predicted": pytest.approx(0.21666666666666667), "empirical_rate": pytest.approx(2 / 3), "count": 3},
        {"mean_predicted": pytest.approx(0.8), "empirical_rate": pytest.approx(1.0), "count": 1},
    ]


def test_bootstrap_ci_is_deterministic_and_reports_point_estimate_and_n():
    point, lo, hi, n = bootstrap_ci([1.0, 2.0, 3.0], n_boot=20, alpha=0.1, seed=7)

    assert point == pytest.approx(2.0)
    assert lo == pytest.approx(1.0)
    assert hi == pytest.approx(2.35)
    assert n == 3
    assert bootstrap_ci([1.0, 2.0, 3.0], n_boot=20, alpha=0.1, seed=7) == (
        point,
        lo,
        hi,
        n,
    )
