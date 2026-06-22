from __future__ import annotations

import math

import pytest

from wc_predictor.data.devig import (
    implied_from_decimal,
    no_vig_three_way,
    remove_vig,
)


def test_implied_from_decimal_returns_inverse_of_decimal_odds():
    assert implied_from_decimal(2.0) == pytest.approx(0.5)
    assert implied_from_decimal(4.0) == pytest.approx(0.25)


@pytest.mark.parametrize("odds", [1.0, 0.0, -2.0, None, math.inf, -math.inf, math.nan])
def test_implied_from_decimal_rejects_invalid_odds(odds):
    with pytest.raises(ValueError, match="decimal odds"):
        implied_from_decimal(odds)


def test_no_vig_three_way_removes_bookmaker_margin_proportionally():
    home, draw, away = no_vig_three_way(2.0, 3.5, 4.0)

    assert home + draw + away == pytest.approx(1.0, abs=1e-12)
    assert home > draw > away
    assert home == pytest.approx(14 / 29, abs=1e-9)
    assert draw == pytest.approx(8 / 29, abs=1e-9)
    assert away == pytest.approx(7 / 29, abs=1e-9)


def test_no_vig_three_way_returns_fair_book_unchanged():
    assert no_vig_three_way(2.0, 4.0, 4.0) == pytest.approx(
        (0.5, 0.25, 0.25),
        abs=1e-12,
    )


def test_remove_vig_normalizes_polymarket_style_prices_proportionally():
    probabilities = remove_vig([0.55, 0.30, 0.18])

    assert sum(probabilities) == pytest.approx(1.0, abs=1e-12)
    assert probabilities == pytest.approx(
        [55 / 103, 30 / 103, 18 / 103],
        abs=1e-9,
    )


@pytest.mark.parametrize(
    "probabilities",
    [
        [],
        [0.0, 1.0],
        [-0.1, 1.1],
        [None, 1.0],
        [math.inf, 1.0],
        [math.nan, 1.0],
    ],
)
def test_remove_vig_rejects_malformed_probability_sets(probabilities):
    with pytest.raises(ValueError, match="probabilities"):
        remove_vig(probabilities)
