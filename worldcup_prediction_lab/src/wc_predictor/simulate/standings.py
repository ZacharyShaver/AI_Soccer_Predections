"""Group standings and FIFA World Cup group tiebreakers.

Tiebreaker order (FIFA World Cup group stage), applied to a group's scored
matches:

1. Points (win=3, draw=1, loss=0)
2. Goal difference (overall)
3. Goals scored (overall)
4. Head-to-head points among the still-tied teams
5. Head-to-head goal difference among the still-tied teams
6. Head-to-head goals scored among the still-tied teams
7. (Fair play / drawing of lots — not modellable here)

Any residual tie after step 6 is broken deterministically by ``canonical_team_id``
ascending so the table is stable and reproducible. The head-to-head sub-table is
computed once over matches played strictly among the tied teams; we do not
recursively re-apply the overall criteria inside a tied subset (documented
approximation, faithful to the common case).

The input is scored matches for ONE group and works identically for real or
simulated results.
"""

from __future__ import annotations

import pandas as pd

WIN_POINTS = 3
DRAW_POINTS = 1

_COLUMNS = ["team_id", "played", "points", "gf", "ga", "gd", "rank"]


def _accumulate(matches: pd.DataFrame, teams: set[str]) -> dict[str, dict[str, int]]:
    """Accumulate points/goals stats for ``teams`` over the given matches.

    Only matches where BOTH teams are in ``teams`` are counted (so the same
    helper computes overall stats, when ``teams`` is every team, and the
    head-to-head sub-table, when ``teams`` is a tied subset).
    """

    stats = {t: {"played": 0, "points": 0, "gf": 0, "ga": 0} for t in teams}
    for row in matches.itertuples(index=False):
        home = str(row.home_team_id)
        away = str(row.away_team_id)
        if home not in teams or away not in teams:
            continue
        hs = int(row.home_score)
        as_ = int(row.away_score)
        stats[home]["played"] += 1
        stats[away]["played"] += 1
        stats[home]["gf"] += hs
        stats[home]["ga"] += as_
        stats[away]["gf"] += as_
        stats[away]["ga"] += hs
        if hs > as_:
            stats[home]["points"] += WIN_POINTS
        elif as_ > hs:
            stats[away]["points"] += WIN_POINTS
        else:
            stats[home]["points"] += DRAW_POINTS
            stats[away]["points"] += DRAW_POINTS
    return stats


def compute_group_table(group_matches_df: pd.DataFrame) -> pd.DataFrame:
    """Return an ordered standings table for a single group.

    Columns: ``team_id, played, points, gf, ga, gd, rank`` (rank 1 = top).
    """

    if group_matches_df.empty:
        return pd.DataFrame(columns=_COLUMNS)

    teams = set(group_matches_df["home_team_id"].astype(str)) | set(
        group_matches_df["away_team_id"].astype(str)
    )
    overall = _accumulate(group_matches_df, teams)
    for t, s in overall.items():
        s["gd"] = s["gf"] - s["ga"]

    # Primary ordering: points, GD, GF (all overall), then a stable team_id key.
    ordered = sorted(
        teams,
        key=lambda t: (
            -overall[t]["points"],
            -overall[t]["gd"],
            -overall[t]["gf"],
            t,
        ),
    )

    # Break remaining ties within runs equal on (points, gd, gf) via head-to-head.
    def overall_key(t: str) -> tuple[int, int, int]:
        return (overall[t]["points"], overall[t]["gd"], overall[t]["gf"])

    resolved: list[str] = []
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and overall_key(ordered[j]) == overall_key(ordered[i]):
            j += 1
        run = ordered[i:j]
        if len(run) > 1:
            h2h = _accumulate(group_matches_df, set(run))
            for t in run:
                h2h[t]["gd"] = h2h[t]["gf"] - h2h[t]["ga"]
            run = sorted(
                run,
                key=lambda t: (
                    -h2h[t]["points"],
                    -h2h[t]["gd"],
                    -h2h[t]["gf"],
                    t,  # deterministic final fallback
                ),
            )
        resolved.extend(run)
        i = j

    records = []
    for rank, t in enumerate(resolved, start=1):
        s = overall[t]
        records.append(
            {
                "team_id": t,
                "played": s["played"],
                "points": s["points"],
                "gf": s["gf"],
                "ga": s["ga"],
                "gd": s["gd"],
                "rank": rank,
            }
        )
    return pd.DataFrame.from_records(records, columns=_COLUMNS)
