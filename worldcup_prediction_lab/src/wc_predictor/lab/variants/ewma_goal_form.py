from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel


VARIANT_ID = "ewma_goal_form"
DESCRIPTION = "Elo + EWMA goal-difference form over a 10-match horizon."
FEATURE_IDEA = (
    "Exponentially-weighted (geometric decay) goal difference over each team's "
    "last 10 matches, then home-minus-away as an Elo delta."
)
EWMA_WINDOW = 10
EWMA_DECAY = 0.7


class EWMAGoalFormEloModel(EloModel):
    model_version = "ewma_goal_form_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        matches_df = train_matches_df.copy()
        date_column = "date" if "date" in matches_df.columns else "match_date"
        matches_df[date_column] = pd.to_datetime(matches_df[date_column], errors="coerce")

        sort_columns = [date_column]
        if "occurrence_index" in matches_df.columns:
            sort_columns.append("occurrence_index")
        sort_columns.append("match_id")
        matches_df = matches_df.sort_values(sort_columns, kind="mergesort")

        team_goal_diffs: dict[str, list[float]] = {}
        for _, match_row in matches_df.iterrows():
            if pd.isna(match_row["home_score"]) or pd.isna(match_row["away_score"]):
                continue

            home_team_id = str(match_row["home_team_id"])
            away_team_id = str(match_row["away_team_id"])
            home_goal_diff = float(match_row["home_score"] - match_row["away_score"])
            away_goal_diff = -home_goal_diff

            team_goal_diffs.setdefault(home_team_id, []).append(home_goal_diff)
            team_goal_diffs[home_team_id] = team_goal_diffs[home_team_id][-EWMA_WINDOW:]
            team_goal_diffs.setdefault(away_team_id, []).append(away_goal_diff)
            team_goal_diffs[away_team_id] = team_goal_diffs[away_team_id][-EWMA_WINDOW:]

        self._ewma_gd = {
            team_id: self._compute_ewma_goal_diff(goal_diffs)
            for team_id, goal_diffs in team_goal_diffs.items()
        }
        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_ewma_gd"):
            return base

        gd_home = self._ewma_gd.get(str(home_team_id), 0.0)
        gd_away = self._ewma_gd.get(str(away_team_id), 0.0)
        delta = max(-45.0, min(45.0, 15.0 * (gd_home - gd_away)))
        return base + delta

    @staticmethod
    def _compute_ewma_goal_diff(goal_diffs: list[float]) -> float:
        if not goal_diffs:
            return 0.0

        weighted_sum = 0.0
        weight_sum = 0.0
        for age, goal_diff in enumerate(reversed(goal_diffs)):
            weight = EWMA_DECAY**age
            weighted_sum += weight * goal_diff
            weight_sum += weight
        return weighted_sum / weight_sum if weight_sum else 0.0


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return EWMAGoalFormEloModel(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
