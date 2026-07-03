"""Single-shot forecast harness for the walk-back ablations.

Three conditions, market NEVER shown (that is the whole experiment — with the
market in the prompt the task degenerates to copying a number):
  stats — Elo ratings/probs + venue/tournament, no news
  news  — linted news docs only, no model numbers
  both  — stats + news
"""

from __future__ import annotations

import pandas as pd

from wc_predictor.lab.walkback.llm import LMClient

CONDITIONS = ("stats", "news", "both")

_SYSTEM = (
    "You are a professional football (soccer) match forecaster. Estimate honest "
    "probabilities for the home win / draw / away win of the upcoming match using ONLY "
    "the information provided. Do not use any knowledge of what actually happened. "
    'Reply ONLY with JSON: {"p_home": float, "p_draw": float, "p_away": float, '
    '"reasoning": "one sentence"}. Probabilities must sum to 1.'
)


def _stats_block(row: pd.Series) -> str:
    return (
        f"Elo ratings: {row['home_team']} {row['elo_home_rating']:.0f}, "
        f"{row['away_team']} {row['elo_away_rating']:.0f} "
        f"(home advantage {row['elo_home_advantage']:.0f} Elo).\n"
        f"Elo model probabilities: home {row['elo_prob_home']:.3f}, "
        f"draw {row['elo_prob_draw']:.3f}, away {row['elo_prob_away']:.3f}."
    )


def _news_block(well: dict) -> str:
    lines = []
    for doc in well["docs"][:10]:
        lines.append(f"- [{doc['seendate']}] ({doc['source']}) {doc['title']}")
        if doc.get("body"):
            lines.append(f"  {doc['body'][:1500]}")
    return "Pre-match news (published before match day):\n" + "\n".join(lines)


def build_prompt(row: pd.Series, well: dict | None, condition: str) -> tuple[str, str]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    if condition in ("news", "both") and not well:
        raise ValueError(f"condition {condition!r} requires a news well")
    date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    parts = [
        f"Match: {row['home_team']} (home) vs {row['away_team']} (away)",
        f"Date: {date} | Venue: {row.get('city', '')} | Competition: {row.get('tournament', '')}",
    ]
    if condition in ("stats", "both"):
        parts.append(_stats_block(row))
    if condition in ("news", "both"):
        parts.append(_news_block(well))
    parts.append("Forecast this match now.")
    return _SYSTEM, "\n\n".join(parts)


def _normalize(p: tuple[float, float, float]) -> tuple[float, float, float]:
    clamped = [max(0.001, float(x)) for x in p]
    total = sum(clamped)
    return tuple(x / total for x in clamped)


def forecast_one(row: pd.Series, well: dict | None, condition: str, client: LMClient) -> dict:
    system, user = build_prompt(row, well, condition)
    raw = client.chat_json(system, user)
    p_home, p_draw, p_away = _normalize(
        (raw.get("p_home", 1 / 3), raw.get("p_draw", 1 / 3), raw.get("p_away", 1 / 3))
    )
    pick = ("home", "draw", "away")[max(range(3), key=[p_home, p_draw, p_away].__getitem__)]
    return {"match_id": str(row["match_id"]), "condition": condition, "model": client.model,
            "p_home": p_home, "p_draw": p_draw, "p_away": p_away, "pick": pick}
