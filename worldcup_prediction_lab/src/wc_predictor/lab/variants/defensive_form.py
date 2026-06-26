from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel


VARIANT_ID = "defensive_form"
DESCRIPTION = "Elo + last-5 defensive solidity (goals conceded)."
FEATURE_IDEA = (
    "Average goals conceded over each team last 5 matches; the stingier defense "
    "(fewer conceded) gets a positive Elo delta via home-minus-away."
)
FORM_WINDOW = 5


class DefensiveFormEloModel(EloModel):
    model_version = "defensive_form_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        matches_df = train_matches_df.copy()
        date_col = "date" if "date" in matches_df.columns else "match_date"
        matches_df[date_col] = pd.to_datetime(matches_df[date_col], errors="coerce")

        sort_cols = [date_col]
        if "occurrence_index" in matches_df.columns:
            sort_cols.append("occurrence_index")
        if "match_id" in matches_df.columns:
            sort_cols.append("match_id")
        matches_df = matches_df.sort_values(sort_cols, kind="mergesort")

        conceded_by_team: dict[str, list[float]] = {}
        for _, row in matches_df.iterrows():
            if pd.isna(row.get("home_score")) or pd.isna(row.get("away_score")):
                continue

            home_team_id = str(row["home_team_id"])
            away_team_id = str(row["away_team_id"])
            home_conceded = float(row["away_score"])
            away_conceded = float(row["home_score"])

            conceded_by_team.setdefault(home_team_id, []).append(home_conceded)
            conceded_by_team.setdefault(away_team_id, []).append(away_conceded)

        self._conceded = {
            team_id: float(pd.Series(values[-FORM_WINDOW:]).mean())
            for team_id, values in conceded_by_team.items()
            if values
        }
        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_conceded"):
            return base

        conceded_home = self._conceded.get(str(home_team_id), 1.0)
        conceded_away = self._conceded.get(str(away_team_id), 1.0)
        delta = 20.0 * (conceded_away - conceded_home)
        delta = max(-45.0, min(45.0, delta))
        return base + delta


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return DefensiveFormEloModel(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
