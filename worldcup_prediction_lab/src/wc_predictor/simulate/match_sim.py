"""Match-level simulation helpers for the tournament Monte Carlo.

Group games sample a full scoreline from the Elo model's calibrated
``ScorelineDistribution`` (so goal difference / goals scored feed the FIFA
tiebreakers). Knockout games resolve to a single winner: regulation uses the
M4 three-way outcome probabilities, and a drawn regulation result is taken to
extra-time/penalties modelled as conditional-on-not-draw — i.e. the stronger
side advances with probability ``prob_home / (prob_home + prob_away)``. This is
a documented modelling choice (a middle ground between pure 50/50 penalties and
full skill); its effect on championship odds is second-order.

All randomness flows through an injected ``numpy.random.Generator`` so a fixed
seed reproduces identical tournaments.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _match_row(home_team_id: str, away_team_id: str, *, neutral: bool, **extra) -> pd.Series:
    data = {"home_team_id": home_team_id, "away_team_id": away_team_id, "neutral": neutral}
    data.update(extra)
    return pd.Series(data)


def sample_scoreline(model, match_row: pd.Series, rng: np.random.Generator) -> tuple[int, int]:
    """Sample ``(home_goals, away_goals)`` from the model's scoreline grid.

    The finite grid is normalized (folding the small tail mass in proportionally)
    so sampling is well-defined. Iteration is over sorted scoreline keys for
    determinism given the generator state.
    """

    dist = model.predict_scoreline(match_row)
    items = sorted(dist.probabilities.items())
    total = sum(p for _, p in items)
    if total <= 0.0:
        return (0, 0)
    threshold = rng.random() * total
    cumulative = 0.0
    chosen = items[-1][0]
    for key, prob in items:
        cumulative += prob
        if threshold <= cumulative:
            chosen = key
            break
    home_str, away_str = chosen.split("-")
    return (int(home_str), int(away_str))


def simulate_group_match(
    model,
    home_team_id: str,
    away_team_id: str,
    rng: np.random.Generator,
    *,
    neutral: bool = True,
    **extra,
) -> tuple[int, int]:
    """Simulate a group game, returning a sampled ``(home_goals, away_goals)``."""

    return sample_scoreline(model, _match_row(home_team_id, away_team_id, neutral=neutral, **extra), rng)


def home_advance_probability(model, match_row: pd.Series) -> float:
    """P(home team advances) in a knockout: win in regulation, or win the tie-break."""

    p = model.predict_match(match_row)
    decisive = p.prob_home + p.prob_away
    if decisive <= 0.0:
        tie_break_home = 0.5
    else:
        tie_break_home = p.prob_home / decisive
    return p.prob_home + p.prob_draw * tie_break_home


def simulate_knockout(
    model,
    home_team_id: str,
    away_team_id: str,
    rng: np.random.Generator,
    *,
    neutral: bool = True,
    **extra,
) -> str:
    """Simulate a knockout tie, returning the single advancing team id."""

    row = _match_row(home_team_id, away_team_id, neutral=neutral, **extra)
    p_home = home_advance_probability(model, row)
    return home_team_id if rng.random() < p_home else away_team_id
