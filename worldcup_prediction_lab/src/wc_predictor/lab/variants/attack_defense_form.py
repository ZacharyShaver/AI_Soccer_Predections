from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel


VARIANT_ID = "attack_defense_form"
DESCRIPTION = "Elo + opponent-coupled attack vs defense form (last 5)."
FEATURE_IDEA = (
    "expected goal supremacy from each side last-5 attack (goals scored) coupled "
    "with the opponent last-5 defense (goals conceded)."
)


class AttackDefenseFormEloModel(EloModel):
    model_version = "attack_defense_form_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)

        df = train_matches_df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        sort_cols = ["date"]
        if "occurrence_index" in df.columns:
            sort_cols.append("occurrence_index")
        if "match_id" in df.columns:
            sort_cols.append("match_id")
        df = df.sort_values(sort_cols, kind="mergesort")

        scored_by_team: dict[str, list[float]] = {}
        conceded_by_team: dict[str, list[float]] = {}
        goals: list[float] = []

        for row in df.itertuples(index=False):
            home_team_id = str(getattr(row, "home_team_id"))
            away_team_id = str(getattr(row, "away_team_id"))
            home_score = float(getattr(row, "home_score"))
            away_score = float(getattr(row, "away_score"))

            for team_id, scored, conceded in (
                (home_team_id, home_score, away_score),
                (away_team_id, away_score, home_score),
            ):
                scored_history = scored_by_team.setdefault(team_id, [])
                conceded_history = conceded_by_team.setdefault(team_id, [])
                scored_history.append(scored)
                conceded_history.append(conceded)
                del scored_history[:-5]
                del conceded_history[:-5]
                goals.append(scored)

        self._league_avg_goals = float(pd.Series(goals).mean()) if goals else 1.3
        if pd.isna(self._league_avg_goals):
            self._league_avg_goals = 1.3

        self._attack = {
            team_id: float(pd.Series(history).mean())
            for team_id, history in scored_by_team.items()
            if history
        }
        self._defense = {
            team_id: float(pd.Series(history).mean())
            for team_id, history in conceded_by_team.items()
            if history
        }

        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not hasattr(self, "_attack"):
            return base

        avg = getattr(self, "_league_avg_goals", 1.3)
        home_attack = self._attack.get(str(home_team_id), avg)
        away_attack = self._attack.get(str(away_team_id), avg)
        home_def = self._defense.get(str(home_team_id), avg)
        away_def = self._defense.get(str(away_team_id), avg)

        home_expected = 0.5 * (home_attack + away_def)
        away_expected = 0.5 * (away_attack + home_def)
        supremacy = home_expected - away_expected
        delta = max(-45.0, min(45.0, 30.0 * supremacy))

        return base + delta


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return AttackDefenseFormEloModel(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
