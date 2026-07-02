"""Recalibrated Elo + Transfermarkt squad-value differential.

The lab's first strength signal NOT derived from historical scorelines.
Monthly per-team squad values (top-15 citizen player market values,
2-year staleness window; see ``data.ingest_transfermarkt``) enter as a
bounded Elo delta on top of the recalibrated foundation:

    delta = clip(COEF * ln(V_home / V_away), -CAP, +CAP)

using each side's latest monthly value STRICTLY BEFORE the match date
(published pre-match, so leak-free by construction). Matches where either
side lacks a value (or has < MIN_VALUED_PLAYERS valued citizens) get no
delta and reduce to plain elo_recalibrated.

Evidence (runs/squad_value_scratch/evaluate.py, 2026-07-02): on the 15.9k
history walk-forward with (coef, cap) chosen OUT-OF-FOLD via 6-block
time-ordered walk-forward (n=13,249): RPS 0.17266 vs elo_recalibrated
0.17300 on the same matches — paired 95% CI [-0.00048, -0.00017] EXCLUDES 0.
On the covered subsample (59.3% of matches) the frozen config's edge is
-0.00054 (CI excludes 0). The coefficient grid is well-behaved: small
optimum (10 per unit log-ratio), monotonically worse past 20 — a real
small signal, not a knob artifact. Deployed config = the full-history
argmin, coef=10, cap=80 (cap rarely binds at this coefficient).
"""

from __future__ import annotations

from bisect import bisect_left
from math import log

import pandas as pd

from wc_predictor.lab.variants.elo_recalibrated import recalibrated_elo_kwargs
from wc_predictor.models.elo import EloModel

VARIANT_ID = "squad_value"
DESCRIPTION = (
    "Recalibrated Elo + Transfermarkt squad-value differential (first non-scoreline signal)."
)
FEATURE_IDEA = (
    "Bounded Elo delta from the log ratio of the two sides' Transfermarkt squad values "
    "(top-15 citizen market values, monthly, strictly pre-match)."
)

COEF = 10.0
CAP = 80.0
MIN_VALUED_PLAYERS = 5


class SquadValueEloModel(EloModel):
    """Recalibrated Elo whose home-advantage delta includes the squad-value edge."""

    def __init__(self, *, squad_values: pd.DataFrame | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        if squad_values is None:
            from wc_predictor.data.ingest_transfermarkt import load_squad_values

            squad_values = load_squad_values()
        self._value_lookup: dict[str, tuple[list[pd.Timestamp], list[float]]] = {}
        if not squad_values.empty:
            usable = squad_values[squad_values["valued_players"] >= MIN_VALUED_PLAYERS]
            for team_id, group in usable.groupby("team_id"):
                group = group.sort_values("date")
                self._value_lookup[str(team_id)] = (
                    list(pd.to_datetime(group["date"])),
                    list(group["squad_value_eur"]),
                )

    def _value_before(self, team_id: str, date: pd.Timestamp) -> float | None:
        series = self._value_lookup.get(str(team_id))
        if series is None:
            return None
        dates, values = series
        index = bisect_left(dates, date)  # dates[index - 1] < date: strictly before
        if index == 0:
            return None
        return values[index - 1]

    def _squad_value_delta(self, match_row: pd.Series, home_id: str, away_id: str) -> float:
        raw_date = match_row.get("date") or match_row.get("match_date")
        if raw_date is None:
            return 0.0
        date = pd.Timestamp(raw_date)
        home_value = self._value_before(home_id, date)
        away_value = self._value_before(away_id, date)
        if not home_value or not away_value:
            return 0.0
        return max(-CAP, min(CAP, COEF * log(home_value / away_value)))

    def _home_advantage_elo(
        self, match_row: pd.Series, home_team_id: str, away_team_id: str
    ) -> float:
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        # The value edge is a strength differential, not a venue effect, so it
        # applies on neutral ground too.
        return base + self._squad_value_delta(match_row, home_team_id, away_team_id)


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return SquadValueEloModel(
        **recalibrated_elo_kwargs(),
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
