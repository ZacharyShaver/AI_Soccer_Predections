from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel


VARIANT_ID = "opp_adj_recent_form"
DESCRIPTION = "Elo + opponent-adjusted last-5 results form."
FEATURE_IDEA = (
    "Last-5 results (win=1, draw=0.5, loss=0), each game weighted by opponent Elo "
    "strength, then home-minus-away as an Elo delta."
)


class OppAdjRecentFormEloModel(EloModel):
    model_version = "opp_adj_recent_form_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        matches = train_matches_df.copy()
        date_col = "date" if "date" in matches.columns else "match_date"
        matches[date_col] = pd.to_datetime(matches[date_col], errors="coerce")

        sort_cols = [date_col]
        if "occurrence_index" in matches.columns:
            sort_cols.append("occurrence_index")
        sort_cols.append("match_id")
        matches = matches.sort_values(sort_cols, kind="mergesort")

        recent_results = {}
        for _, row in matches.iterrows():
            if pd.isna(row["home_score"]) or pd.isna(row["away_score"]):
                continue

            home_team_id = str(row["home_team_id"])
            away_team_id = str(row["away_team_id"])
            home_score = row["home_score"]
            away_score = row["away_score"]

            if home_score > away_score:
                home_result = 1.0
                away_result = 0.0
            elif away_score > home_score:
                home_result = 0.0
                away_result = 1.0
            else:
                home_result = 0.5
                away_result = 0.5

            recent_results.setdefault(home_team_id, []).append((home_result, away_team_id))
            recent_results[home_team_id] = recent_results[home_team_id][-5:]
            recent_results.setdefault(away_team_id, []).append((away_result, home_team_id))
            recent_results[away_team_id] = recent_results[away_team_id][-5:]

        self._opp_adj_form = {}
        for team_id, results in recent_results.items():
            weighted_sum = 0.0
            weight_sum = 0.0
            for result, opponent_id in results:
                weight = 1.0 + (self.get_rating(opponent_id) - 1500.0) / 100.0
                weight = max(0.5, min(2.0, weight))
                weighted_sum += weight * result
                weight_sum += weight
            self._opp_adj_form[str(team_id)] = weighted_sum / weight_sum if weight_sum else 0.5

        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_opp_adj_form"):
            return base

        form_home = self._opp_adj_form.get(str(home_team_id), 0.5)
        form_away = self._opp_adj_form.get(str(away_team_id), 0.5)
        delta = 60.0 * (form_home - form_away)
        delta = max(-60.0, min(60.0, delta))
        return base + delta


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return OppAdjRecentFormEloModel(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
