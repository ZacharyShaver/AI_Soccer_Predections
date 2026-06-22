"""Utilities for converting market odds into no-vig probabilities.

This module uses proportional de-vigging: convert each mutually exclusive
outcome to an implied probability, then divide each probability by the total
book. Shin and other margin-removal methods may be useful refinements later,
but proportional normalization is deterministic and transparent for the first
market benchmark slice.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def implied_from_decimal(decimal_odds: float) -> float:
    """Return the raw implied probability from decimal odds."""

    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError) as exc:
        raise ValueError("decimal odds must be a finite number greater than 1.0") from exc

    if not math.isfinite(odds) or odds <= 1.0:
        raise ValueError("decimal odds must be a finite number greater than 1.0")

    return 1.0 / odds


def remove_vig(probabilities: Sequence[float]) -> list[float]:
    """Normalize mutually exclusive outcome probabilities to sum to 1.

    The normalization is proportional: each input probability is divided by the
    raw total. This removes overround while preserving relative prices.
    """

    if not probabilities:
        raise ValueError("probabilities must contain at least one value")

    normalized_inputs: list[float] = []
    for probability in probabilities:
        try:
            value = float(probability)
        except (TypeError, ValueError) as exc:
            raise ValueError("probabilities must be finite positive numbers") from exc

        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("probabilities must be finite positive numbers")
        normalized_inputs.append(value)

    total = sum(normalized_inputs)
    return [probability / total for probability in normalized_inputs]


def no_vig_three_way(
    home_odds: float,
    draw_odds: float,
    away_odds: float,
) -> tuple[float, float, float]:
    """Convert home/draw/away decimal odds to no-vig probabilities."""

    probabilities = remove_vig(
        [
            implied_from_decimal(home_odds),
            implied_from_decimal(draw_odds),
            implied_from_decimal(away_odds),
        ]
    )
    return probabilities[0], probabilities[1], probabilities[2]
