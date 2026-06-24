from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel


VARIANT_ID = "match_congestion"
DESCRIPTION = "Elo + fixture congestion: matches played in the trailing 15 days = fatigue."
FEATURE_IDEA = "count each team matches in the 15 days before kickoff; the more-rested side (fewer recent matches) gets a small Elo bump."
CONGESTION_WINDOW_DAYS = 15


class MatchCongestionEloModel(EloModel):
    model_version = "match_congestion_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        match_dates: dict[str, list[pd.Timestamp]] = {}
        for _, match_row in train_matches_df.iterrows():
            match_date = pd.to_datetime(match_row.get("date"), errors="coerce")
            if pd.isna(match_date):
                continue

            home_team_id = str(match_row.get("home_team_id"))
            away_team_id = str(match_row.get("away_team_id"))
            match_dates.setdefault(home_team_id, []).append(match_date)
            match_dates.setdefault(away_team_id, []).append(match_date)

        self._match_dates = {
            team_id: sorted(dates)
            for team_id, dates in match_dates.items()
        }
        return self

    def _recent_match_count(self, match_date, team_id) -> int:
        dates = self._match_dates.get(str(team_id))
        if dates is None:
            return 0

        window_start = match_date - pd.Timedelta(days=CONGESTION_WINDOW_DAYS)
        return int(sum(1 for d in dates if window_start <= d < match_date))

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_match_dates"):
            return base

        match_date = pd.to_datetime(match_row.get("date"), errors="coerce")
        if pd.isna(match_date):
            return base

        n_home = self._recent_match_count(match_date, home_team_id)
        n_away = self._recent_match_count(match_date, away_team_id)
        delta = -8.0 * (n_home - n_away)
        delta = max(-30.0, min(30.0, delta))
        return base + delta


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return MatchCongestionEloModel(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
