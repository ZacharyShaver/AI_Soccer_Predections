from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel


VARIANT_ID = "scoring_form"
DESCRIPTION = "Elo + attacking form from last-5 goal difference."
FEATURE_IDEA = "average goal difference (scored minus conceded) over each team's last 5 matches."

FORM_WINDOW = 5


class ScoringFormElo(EloModel):
    """Elo variant with a recent goal-difference adjustment."""

    model_version = "scoring_form_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        matches = train_matches_df.copy()
        matches["_scoring_form_date"] = pd.to_datetime(matches["date"])

        sort_columns = ["_scoring_form_date"]
        for tie_breaker in ("occurrence_index", "match_id"):
            if tie_breaker in matches.columns:
                sort_columns.append(tie_breaker)
        matches = matches.sort_values(sort_columns, kind="mergesort")

        goal_diffs: dict[str, list[float]] = {}
        for row in matches.itertuples(index=False):
            home_team_id = str(getattr(row, "home_team_id"))
            away_team_id = str(getattr(row, "away_team_id"))
            home_score = float(getattr(row, "home_score"))
            away_score = float(getattr(row, "away_score"))

            goal_diffs.setdefault(home_team_id, []).append(home_score - away_score)
            goal_diffs.setdefault(away_team_id, []).append(away_score - home_score)

        self._goal_diff: dict[str, float] = {
            team_id: float(pd.Series(team_diffs[-FORM_WINDOW:]).mean())
            for team_id, team_diffs in goal_diffs.items()
        }

        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_goal_diff"):
            return base

        gd_home = self._goal_diff.get(str(home_team_id), 0.0)
        gd_away = self._goal_diff.get(str(away_team_id), 0.0)
        delta = 15.0 * (gd_home - gd_away)
        delta = max(-45.0, min(45.0, delta))
        return base + delta


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return ScoringFormElo(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
