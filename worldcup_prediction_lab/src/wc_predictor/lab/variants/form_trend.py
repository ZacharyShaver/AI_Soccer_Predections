"""Elo variant using recent goal-difference trend."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from wc_predictor.models.elo import EloModel

VARIANT_ID = "form_trend"
DESCRIPTION = "Adjusts Elo home advantage by whether recent goal difference is improving or declining."
FEATURE_IDEA = "Slope of last-5 goal difference, computed as recent half minus earlier half."


class FormTrendElo(EloModel):
    """Elo model with a small adjustment for recent goal-difference direction."""

    model_version = "form_trend_v1"

    def fit(self, train_matches_df: pd.DataFrame) -> "FormTrendElo":
        super().fit(train_matches_df)

        matches = train_matches_df.copy()
        date_col = "_form_trend_date"
        matches[date_col] = pd.to_datetime(matches["date"], errors="coerce")

        sort_cols = [date_col]
        if "occurrence_index" in matches.columns:
            sort_cols.append("occurrence_index")
        if "match_id" in matches.columns:
            sort_cols.append("match_id")
        matches = matches.sort_values(sort_cols, kind="mergesort")

        goal_diffs: dict[str, list[float]] = defaultdict(list)
        for row in matches.itertuples(index=False):
            home_score = getattr(row, "home_score")
            away_score = getattr(row, "away_score")
            if pd.isna(home_score) or pd.isna(away_score):
                continue

            home_team_id = str(getattr(row, "home_team_id"))
            away_team_id = str(getattr(row, "away_team_id"))
            home_goal_diff = float(home_score) - float(away_score)
            goal_diffs[home_team_id].append(home_goal_diff)
            goal_diffs[away_team_id].append(-home_goal_diff)

        trend: dict[str, float] = {}
        for team_id, diffs in goal_diffs.items():
            window = diffs[-5:]
            if len(window) < 2:
                trend[team_id] = 0.0
                continue

            recent_half = window[-2:]
            earlier_half = window[:-2]
            if not earlier_half:
                trend[team_id] = 0.0
                continue
            trend[team_id] = float(pd.Series(recent_half).mean() - pd.Series(earlier_half).mean())

        self._trend = trend
        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_trend"):
            return base

        trend_home = self._trend.get(str(home_team_id), 0.0)
        trend_away = self._trend.get(str(away_team_id), 0.0)
        delta = 12.0 * (trend_home - trend_away)
        delta = max(-40.0, min(40.0, delta))
        return base + delta


def build_model(*, generated_at_utc):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return FormTrendElo(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
