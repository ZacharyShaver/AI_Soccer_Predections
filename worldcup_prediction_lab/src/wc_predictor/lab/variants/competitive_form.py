"""Competition-importance-weighted recent goal-difference Elo variant."""

from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel


VARIANT_ID = "competitive_form"
DESCRIPTION = "Elo with last-5 goal-difference form that down-weights friendlies."
FEATURE_IDEA = "Competition-importance-weighted last-5 goal-difference form."


def _match_weight(tournament) -> float:
    tournament_text = "" if pd.isna(tournament) else str(tournament).lower()
    if "friendly" in tournament_text:
        return 0.4
    return 1.0


class CompetitiveFormElo(EloModel):
    model_version = "competitive_form_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        matches = train_matches_df.copy()
        date_col = "date" if "date" in matches.columns else "match_date"
        parsed_date_col = "__competitive_form_parsed_date"
        matches[parsed_date_col] = pd.to_datetime(matches[date_col], errors="coerce")

        sort_cols = [parsed_date_col]
        for col in ("occurrence_index", "match_id"):
            if col in matches.columns:
                sort_cols.append(col)
        matches = matches.sort_values(sort_cols, kind="mergesort")

        team_form: dict[str, list[tuple[float, float]]] = {}
        for _, match in matches.iterrows():
            home_score = match.get("home_score")
            away_score = match.get("away_score")
            if pd.isna(home_score) or pd.isna(away_score):
                continue

            home_team_id = str(match.get("home_team_id"))
            away_team_id = str(match.get("away_team_id"))
            home_gd = float(home_score) - float(away_score)
            away_gd = -home_gd
            weight = _match_weight(match.get("tournament"))

            team_form.setdefault(home_team_id, []).append((home_gd, weight))
            team_form.setdefault(away_team_id, []).append((away_gd, weight))

        self._form = {}
        for team_id, pairs in team_form.items():
            recent_pairs = pairs[-5:]
            total_weight = sum(weight for _, weight in recent_pairs)
            if total_weight == 0:
                self._form[team_id] = 0.0
            else:
                self._form[team_id] = (
                    sum(goal_difference * weight for goal_difference, weight in recent_pairs)
                    / total_weight
                )

        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_form"):
            return base

        gd_home = self._form.get(str(home_team_id), 0.0)
        gd_away = self._form.get(str(away_team_id), 0.0)
        delta = max(-45.0, min(45.0, 15.0 * (gd_home - gd_away)))
        return base + delta


def build_model(*, generated_at_utc):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return CompetitiveFormElo(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
