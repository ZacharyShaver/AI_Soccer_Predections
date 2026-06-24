from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel

VARIANT_ID = "opp_adj_form"
DESCRIPTION = "Elo + opponent-adjusted last-5 goal difference."
FEATURE_IDEA = "last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta."


class OppAdjFormEloModel(EloModel):
    model_version = "opp_adj_form_v1"

    def fit(self, train_matches_df: pd.DataFrame) -> "OppAdjFormEloModel":
        super().fit(train_matches_df)

        df = train_matches_df.copy()
        date_col = "date" if "date" in df.columns else "match_date"
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        sort_cols = [date_col]
        if "occurrence_index" in df.columns:
            sort_cols.append("occurrence_index")
        sort_cols.append("match_id")
        df = df.sort_values(sort_cols, kind="mergesort")

        recent: dict[str, list[tuple[float, str]]] = {}
        for row in df.itertuples(index=False):
            home_team_id = str(getattr(row, "home_team_id"))
            away_team_id = str(getattr(row, "away_team_id"))
            home_score = float(getattr(row, "home_score"))
            away_score = float(getattr(row, "away_score"))

            recent.setdefault(home_team_id, []).append((home_score - away_score, away_team_id))
            recent[home_team_id] = recent[home_team_id][-5:]

            recent.setdefault(away_team_id, []).append((away_score - home_score, home_team_id))
            recent[away_team_id] = recent[away_team_id][-5:]

        self._opp_adj_gd = {}
        for team_id, pairs in recent.items():
            weighted_sum = 0.0
            weight_sum = 0.0
            for gd, opponent_id in pairs:
                weight = 1.0 + (self.get_rating(opponent_id) - 1500.0) / 100.0
                weight = max(0.5, min(2.0, weight))
                weighted_sum += weight * gd
                weight_sum += weight
            self._opp_adj_gd[team_id] = weighted_sum / weight_sum if weight_sum > 0.0 else 0.0

        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_opp_adj_gd"):
            return base

        gd_home = self._opp_adj_gd.get(str(home_team_id), 0.0)
        gd_away = self._opp_adj_gd.get(str(away_team_id), 0.0)
        delta = 15.0 * (gd_home - gd_away)
        delta = max(-45.0, min(45.0, delta))
        return base + delta


def build_model(*, generated_at_utc: str) -> OppAdjFormEloModel:
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return OppAdjFormEloModel(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
