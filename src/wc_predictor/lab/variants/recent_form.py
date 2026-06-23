from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel


VARIANT_ID = "recent_form"
DESCRIPTION = "Elo + short-window momentum from last-5 match results."
FEATURE_IDEA = "average result (win=1, draw=0.5, loss=0) over each team's last 5 matches."
FORM_WINDOW = 5


class RecentFormElo(EloModel):
    """Elo model with a short-window form adjustment in Elo points."""

    model_version = "recent_form_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        matches = train_matches_df.copy()
        matches["_recent_form_date"] = pd.to_datetime(matches["date"], errors="coerce")

        sort_columns = ["_recent_form_date"]
        if "occurrence_index" in matches.columns:
            sort_columns.append("occurrence_index")
        if "match_id" in matches.columns:
            sort_columns.append("match_id")

        team_results: dict[str, list[float]] = {}
        for _, row in matches.sort_values(sort_columns, kind="mergesort").iterrows():
            home_score = row["home_score"]
            away_score = row["away_score"]
            if pd.isna(home_score) or pd.isna(away_score):
                continue

            home_team_id = str(row["home_team_id"])
            away_team_id = str(row["away_team_id"])

            if home_score > away_score:
                home_result = 1.0
                away_result = 0.0
            elif home_score < away_score:
                home_result = 0.0
                away_result = 1.0
            else:
                home_result = 0.5
                away_result = 0.5

            team_results.setdefault(home_team_id, []).append(home_result)
            team_results.setdefault(away_team_id, []).append(away_result)

        self._form: dict[str, float] = {
            team_id: sum(results[-FORM_WINDOW:]) / len(results[-FORM_WINDOW:])
            for team_id, results in team_results.items()
            if results
        }
        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_form"):
            return base

        form_home = self._form.get(str(home_team_id), 0.5)
        form_away = self._form.get(str(away_team_id), 0.5)
        delta = 60.0 * (form_home - form_away)
        delta = max(-60.0, min(60.0, delta))
        return base + delta


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return RecentFormElo(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
