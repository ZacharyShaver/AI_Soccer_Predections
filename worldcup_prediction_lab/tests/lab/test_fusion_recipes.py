import math

import pytest

from wc_predictor.lab import fusion_recipes


def test_linear_opinion_pool_uses_normalized_weights():
    probs = [
        (0.60, 0.25, 0.15),
        (0.30, 0.35, 0.35),
        (0.20, 0.30, 0.50),
    ]

    pooled = fusion_recipes.linear_opinion_pool(probs, weights=[2.0, 1.0, 1.0])

    assert pooled == pytest.approx((0.425, 0.2875, 0.2875))
    assert sum(pooled) == pytest.approx(1.0)


def test_logarithmic_opinion_pool_normalizes_geometric_mean():
    probs = [
        (0.60, 0.25, 0.15),
        (0.30, 0.35, 0.35),
    ]

    pooled = fusion_recipes.logarithmic_opinion_pool(probs, weights=[0.75, 0.25])

    raw = [
        (0.60**0.75) * (0.30**0.25),
        (0.25**0.75) * (0.35**0.25),
        (0.15**0.75) * (0.35**0.25),
    ]
    total = sum(raw)
    assert pooled == pytest.approx(tuple(value / total for value in raw))
    assert sum(pooled) == pytest.approx(1.0)


def test_logarithmic_opinion_pool_rejects_zero_probability_without_floor():
    with pytest.raises(ValueError, match="strictly positive"):
        fusion_recipes.logarithmic_opinion_pool(
            [(0.7, 0.3, 0.0), (0.5, 0.2, 0.3)],
            weights=[1.0, 1.0],
            floor=0.0,
        )


def test_weight_schemes_prefer_lower_rps_variants():
    scores = {"steady": 0.16, "champion": 0.14, "laggard": 0.20}

    inverse = fusion_recipes.inverse_rps_weights(scores)
    softmax = fusion_recipes.softmax_rps_weights(scores, temperature=0.02)

    assert inverse["champion"] > inverse["steady"] > inverse["laggard"]
    assert softmax["champion"] > softmax["steady"] > softmax["laggard"]
    assert math.isclose(sum(inverse.values()), 1.0)
    assert math.isclose(sum(softmax.values()), 1.0)


def test_ranked_variant_selection_supports_top_k_and_trim():
    scores = {
        "elo_recalibrated": 0.1574,
        "ensemble_top_k": 0.1582,
        "form_trend": 0.1610,
        "bad_overfit": 0.1800,
    }

    assert fusion_recipes.select_top_k(scores, k=2) == [
        "elo_recalibrated",
        "ensemble_top_k",
    ]
    assert fusion_recipes.select_rank_and_trim(scores, trim_worst=1) == [
        "elo_recalibrated",
        "ensemble_top_k",
        "form_trend",
    ]


def test_weight_vector_follows_selected_variant_order():
    scores = {
        "elo_recalibrated": 0.1574,
        "ensemble_top_k": 0.1582,
        "form_trend": 0.1610,
    }

    weights = fusion_recipes.weight_vector_for_variants(
        scores,
        ["form_trend", "elo_recalibrated"],
        scheme="inverse_rps",
    )

    expected = fusion_recipes.inverse_rps_weights(
        {"form_trend": 0.1610, "elo_recalibrated": 0.1574}
    )
    assert weights == pytest.approx([expected["form_trend"], expected["elo_recalibrated"]])


def test_weight_vector_rejects_unknown_scheme_and_missing_variant():
    scores = {"elo_recalibrated": 0.1574}

    with pytest.raises(ValueError, match="unknown weight scheme"):
        fusion_recipes.weight_vector_for_variants(
            scores,
            ["elo_recalibrated"],
            scheme="mystery",
        )

    with pytest.raises(ValueError, match="missing scores"):
        fusion_recipes.weight_vector_for_variants(
            scores,
            ["elo_recalibrated", "ensemble_top_k"],
            scheme="uniform",
        )


def test_probability_validation_catches_bad_shapes_and_mass():
    with pytest.raises(ValueError, match="three probabilities"):
        fusion_recipes.linear_opinion_pool([(0.5, 0.5)], weights=[1.0])

    with pytest.raises(ValueError, match="positive total mass"):
        fusion_recipes.linear_opinion_pool([(0.0, 0.0, 0.0)], weights=[1.0])

    with pytest.raises(ValueError, match="same length"):
        fusion_recipes.linear_opinion_pool([(0.5, 0.3, 0.2)], weights=[1.0, 2.0])
