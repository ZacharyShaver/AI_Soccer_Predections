from __future__ import annotations

import pandas as pd

from wc_predictor.forecast_live import build_world_cup_host_advantage_fn
from wc_predictor.models.elo import EloModel


VARIANT_ID = "rest_days"
DESCRIPTION = "Elo + rest/fatigue: more days since last match = small Elo bump."
FEATURE_IDEA = "rest days since each team's previous match (cap 14d); short rest penalized."


class RestDaysElo(EloModel):
    model_version = "rest_days_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        dates = pd.to_datetime(train_matches_df["date"])
        last_match_date: dict[str, pd.Timestamp] = {}

        for team_col in ("home_team_id", "away_team_id"):
            team_dates = (
                pd.DataFrame(
                    {
                        "team_id": train_matches_df[team_col],
                        "date": dates,
                    }
                )
                .dropna(subset=["team_id", "date"])
                .groupby("team_id")["date"]
                .max()
            )

            for team_id, match_date in team_dates.items():
                team_key = str(team_id)
                if team_key not in last_match_date or match_date > last_match_date[team_key]:
                    last_match_date[team_key] = match_date

        self._last_match_date = last_match_date
        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)

        match_date = pd.to_datetime(match_row.get("date"))
        if pd.isna(match_date):
            return base

        last_match_date = getattr(self, "_last_match_date", None)
        if last_match_date is None:
            return base

        rest_home = self._rest_days(match_date, home_team_id, last_match_date)
        rest_away = self._rest_days(match_date, away_team_id, last_match_date)
        delta = max(-30.0, min(30.0, 3.0 * (rest_home - rest_away)))
        return base + delta

    @staticmethod
    def _rest_days(
        match_date: pd.Timestamp,
        team_id: str,
        last_match_date: dict[str, pd.Timestamp],
    ) -> int:
        previous_date = last_match_date.get(str(team_id))
        if previous_date is None:
            return 7

        rest_days = (match_date - previous_date).days
        return max(0, min(14, rest_days))


def build_model(*, generated_at_utc: str) -> RestDaysElo:
    return RestDaysElo(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
