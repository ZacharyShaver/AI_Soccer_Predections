"""Match-level simulation helpers for the tournament Monte Carlo.

Group games sample a full scoreline from the Elo model's calibrated
``ScorelineDistribution`` (so goal difference / goals scored feed the FIFA
tiebreakers). Knockout games resolve to a single winner: regulation uses the
M4 three-way outcome probabilities, and a drawn result goes to penalties
modelled as a COIN FLIP. That replaces the original conditional-on-not-draw
tie-break (``prob_home / (prob_home + prob_away)``): measured on 561
historical shootouts with leak-free pre-match Elo ratings (2026-07-02,
``runs/shootout_scratch/``), the stronger side won only 51.0% (Wilson 95% CI
[46.9%, 55.1%] — indistinguishable from 50/50; even >=100-Elo favourites:
53.7%, CI spans 50%), while the old rule assumed 68.0% on those same matches.
Note martj42 scores include extra time, so the outcome model's "draw" for a
knockout already means "went to penalties".

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
    """P(home team advances) in a knockout: win outright, or win the shootout.

    The shootout term is 0.5 — empirically shootouts are coin flips regardless
    of team strength (see module docstring for the 561-shootout evidence).
    """

    p = model.predict_match(match_row)
    return p.prob_home + 0.5 * p.prob_draw


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
