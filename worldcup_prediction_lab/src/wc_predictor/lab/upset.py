"""Second-pass upset-risk signals for forecast displays.

The upset definition is soccer-specific: the underdog "upsets" the favorite by
avoiding defeat, either through a win or a draw. This module is deliberately
pure and report-layer only; it does not train on or rewrite immutable forecast
ledgers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpsetRisk:
    favorite: str
    underdog: str
    favorite_win_probability: float
    underdog_avoid_defeat_probability: float
    percent: float
    label: str


def assess_upset_risk(probs: tuple[float, float, float]) -> UpsetRisk:
    """Return upset risk from normalized ``(home, draw, away)`` probabilities."""

    prob_home, prob_draw, prob_away = _normalize(probs)
    if prob_home >= prob_away:
        favorite = "home"
        underdog = "away"
        favorite_win_probability = prob_home
        avoid_defeat_probability = prob_draw + prob_away
    else:
        favorite = "away"
        underdog = "home"
        favorite_win_probability = prob_away
        avoid_defeat_probability = prob_draw + prob_home

    percent = max(0.0, min(100.0, avoid_defeat_probability * 100.0))
    return UpsetRisk(
        favorite=favorite,
        underdog=underdog,
        favorite_win_probability=favorite_win_probability,
        underdog_avoid_defeat_probability=avoid_defeat_probability,
        percent=percent,
        label=_risk_label(percent),
    )


def format_upset_risk(risk: UpsetRisk) -> str:
    return f"{risk.percent:.0f}% {risk.label}"


def _normalize(probs: tuple[float, float, float]) -> tuple[float, float, float]:
    if len(probs) != 3:
        raise ValueError("probs must be a three-item (home, draw, away) tuple")
    prob_home, prob_draw, prob_away = (max(0.0, float(prob)) for prob in probs)
    total = prob_home + prob_draw + prob_away
    if total <= 0.0:
        raise ValueError("probabilities have no mass")
    return prob_home / total, prob_draw / total, prob_away / total


def _risk_label(percent: float) -> str:
    if percent < 30.0:
        return "Low"
    if percent < 45.0:
        return "Medium"
    return "High"
