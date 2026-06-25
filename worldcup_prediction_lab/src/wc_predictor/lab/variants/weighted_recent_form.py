from __future__ import annotations

from collections import defaultdict

import pandas as pd

from wc_predictor.models.elo import EloModel


VARIANT_ID = "weighted_recent_form"
DESCRIPTION = "Elo with a recency-weighted last-five match form adjustment."
FEATURE_IDEA = "Use weighted recent team results to nudge effective home advantage."


class WeightedRecentFormElo(EloModel):
    model_version = "weighted_recent_form_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        matches = train_matches_df.copy()
        matches["_date"] = pd.to_datetime(matches["date"], errors="coerce")

        sort_cols = ["_date"]
        if "occurrence_index" in matches.columns:
            sort_cols.append("occurrence_index")
        if "match_id" in matches.columns:
            sort_cols.append("match_id")
        matches = matches.sort_values(sort_cols, kind="mergesort")

        results_by_team = defaultdict(list)
        for _, match in matches.iterrows():
            home_score = match.get("home_score")
            away_score = match.get("away_score")
            if pd.isna(home_score) or pd.isna(away_score):
                continue

            home_team_id = str(match["home_team_id"])
            away_team_id = str(match["away_team_id"])

            if home_score > away_score:
                home_result = 1.0
                away_result = 0.0
            elif home_score < away_score:
                home_result = 0.0
                away_result = 1.0
            else:
                home_result = 0.5
                away_result = 0.5

            results_by_team[home_team_id].append(home_result)
            results_by_team[away_team_id].append(away_result)

        self._form = {}
        for team_id, results in results_by_team.items():
            window = results[-5:]
            weights = list(range(1, len(window) + 1))
            self._form[team_id] = sum(
                result * weight for result, weight in zip(window, weights)
            ) / sum(weights)

        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_form"):
            return base

        form_home = self._form.get(str(home_team_id), 0.5)
        form_away = self._form.get(str(away_team_id), 0.5)
        delta = max(-60.0, min(60.0, 60.0 * (form_home - form_away)))
        return base + delta


def build_model(*, generated_at_utc):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return WeightedRecentFormElo(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
