"""Parametric-memory contamination screen.

A local model may know a match result from training data. Before evaluating a
model on a match we ask it point-blank for the final score. Only an exact
correct score counts as contamination: excluding correct-outcome guesses would
strip favorite-wins from the sample and bias the eval toward upsets.
"""

from __future__ import annotations

import pandas as pd

from wc_predictor.lab.walkback.llm import LMClient

_SYSTEM = (
    "You are a sports results database. If you know the actual final result of the "
    "requested match from your training data, report it. If you do not know it, say so. "
    'Reply ONLY with JSON: {"known": true/false, "home_goals": int or null, '
    '"away_goals": int or null}. Never guess.'
)


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def recall_check(row: pd.Series, client: LMClient) -> dict:
    date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    user = (
        f"What was the final score of {row['home_team']} vs {row['away_team']} "
        f"(men's international football) played on {date}?"
    )
    recalled = client.chat_json(_SYSTEM, user)
    contaminated = (
        bool(recalled.get("known"))
        and _as_int(recalled.get("home_goals")) == int(row["home_score"])
        and _as_int(recalled.get("away_goals")) == int(row["away_score"])
    )
    return {"match_id": str(row["match_id"]), "contaminated": contaminated, "recalled": recalled}
