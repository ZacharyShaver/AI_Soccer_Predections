"""Group-table incentive adjustment for late group-stage matches.

This challenger measures the non-rating context that showed up in recent live
misses: final group matches where a draw is useful, a favorite is already safe,
or the other side has stronger points pressure. It intentionally uses fixture
and result state available before kickoff rather than post-match prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from wc_predictor.models.elo import EloModel, EloPrediction


VARIANT_ID = "group_incentive"
DESCRIPTION = "Host-aware Elo adjusted for group-stage qualification incentives."
FEATURE_IDEA = (
    "Use measurable pre-kickoff group-table state: final group match, draw utility, "
    "favorite safety, and underdog points pressure."
)

MAX_DRAW_BOOST = 0.13
MAX_FAVORITE_SHIFT = 0.09


@dataclass(frozen=True)
class TeamContext:
    points: int = 0
    goal_difference: int = 0
    goals_for: int = 0
    played: int = 0
    rank: int = 4

    @property
    def final_group_match(self) -> bool:
        return self.played >= 2

    @property
    def draw_useful(self) -> bool:
        return self.final_group_match and (self.rank <= 2 or self.points + 1 >= 4)

    @property
    def already_safe(self) -> bool:
        return self.points >= 6 or (
            self.final_group_match and self.points >= 4 and self.rank <= 2
        )

    @property
    def needs_result(self) -> bool:
        return self.final_group_match and self.points <= 3 and self.rank >= 3


class GroupIncentiveElo(EloModel):
    model_version = "group_incentive_v1"

    def __init__(self, *args: Any, fixture_schedule_df: pd.DataFrame | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fixture_schedule_df = fixture_schedule_df
        self._fixture_by_id: dict[str, dict[str, Any]] = {}
        self._group_tables: dict[str, dict[str, TeamContext]] = {}

    def fit(self, train_matches_df: pd.DataFrame):
        super().fit(train_matches_df)
        schedule = self._fixture_schedule()
        self._fixture_by_id = self._build_fixture_lookup(schedule)
        self._group_tables = self._build_group_tables(train_matches_df, schedule)
        return self

    def predict_match(self, match_row):
        prediction = super().predict_match(match_row)
        meta = self._fixture_meta(match_row)
        if not meta or str(meta.get("stage", "")).lower() != "group":
            return prediction

        group = str(meta.get("group", ""))
        table = self._group_tables.get(group)
        if not table:
            return prediction

        home_team_id = str(match_row.get("home_team_id"))
        away_team_id = str(match_row.get("away_team_id"))
        home_ctx = table.get(home_team_id, TeamContext())
        away_ctx = table.get(away_team_id, TeamContext())
        if not (home_ctx.final_group_match or away_ctx.final_group_match):
            return prediction

        probs = [prediction.prob_home, prediction.prob_draw, prediction.prob_away]
        home_away = [probs[0], probs[2]]
        favorite_side = 0 if home_away[0] >= home_away[1] else 2
        underdog_side = 2 if favorite_side == 0 else 0
        favorite_prob = probs[favorite_side]
        favorite_ctx = home_ctx if favorite_side == 0 else away_ctx
        underdog_ctx = away_ctx if favorite_side == 0 else home_ctx

        draw_pressure = 0.0
        if home_ctx.final_group_match and away_ctx.final_group_match:
            draw_pressure += 0.03
        if home_ctx.draw_useful and away_ctx.draw_useful:
            draw_pressure += 0.08
        elif home_ctx.draw_useful or away_ctx.draw_useful:
            draw_pressure += 0.04
        if 0.40 <= favorite_prob <= 0.60:
            draw_pressure += 0.02
        probs = _boost_draw(probs, min(MAX_DRAW_BOOST, draw_pressure))

        favorite_shift = 0.0
        if favorite_ctx.already_safe:
            favorite_shift += 0.06
        if underdog_ctx.needs_result:
            favorite_shift += 0.03
        probs = _shift_from_favorite(
            probs,
            favorite_side=favorite_side,
            underdog_side=underdog_side,
            amount=min(MAX_FAVORITE_SHIFT, favorite_shift),
        )

        return EloPrediction(
            prob_home=probs[0],
            prob_draw=probs[1],
            prob_away=probs[2],
            pre_match_home_rating=prediction.pre_match_home_rating,
            pre_match_away_rating=prediction.pre_match_away_rating,
            home_advantage_elo=prediction.home_advantage_elo,
        )

    def _fixture_schedule(self) -> pd.DataFrame:
        if self.fixture_schedule_df is not None:
            return self.fixture_schedule_df.copy()
        try:
            from wc_predictor.forecast_live import load_silver_data

            _matches, fixtures, _teams = load_silver_data()
            return fixtures
        except Exception:
            return pd.DataFrame()

    def _build_fixture_lookup(self, schedule: pd.DataFrame) -> dict[str, dict[str, Any]]:
        if schedule.empty or "fixture_id" not in schedule.columns:
            return {}
        return {
            str(row["fixture_id"]): dict(row)
            for row in schedule.to_dict("records")
            if str(row.get("stage", "")).lower() == "group"
        }

    def _fixture_meta(self, match_row) -> dict[str, Any] | None:
        fixture_id = str(match_row.get("fixture_id", match_row.get("match_id", "")))
        if fixture_id in self._fixture_by_id:
            return self._fixture_by_id[fixture_id]
        if "group" in match_row and "stage" in match_row:
            return dict(match_row)
        return None

    def _build_group_tables(
        self,
        train_matches_df: pd.DataFrame,
        schedule: pd.DataFrame,
    ) -> dict[str, dict[str, TeamContext]]:
        if train_matches_df.empty or schedule.empty:
            return {}
        group_fixtures = schedule.loc[
            schedule.get("stage", pd.Series(dtype=object)).astype(str).str.lower()
            == "group"
        ].copy()
        if group_fixtures.empty:
            return {}

        table: dict[str, dict[str, dict[str, int]]] = {}
        for row in group_fixtures.to_dict("records"):
            group = str(row.get("group", ""))
            if not group:
                continue
            group_table = table.setdefault(group, {})
            for side in ("home_team_id", "away_team_id"):
                team_id = str(row.get(side))
                if team_id and team_id != "nan":
                    group_table.setdefault(
                        team_id,
                        {"points": 0, "goal_difference": 0, "goals_for": 0, "played": 0},
                    )

        completed = _oriented_completed_group_results(train_matches_df, group_fixtures)
        for row in completed:
            group = str(row["group"])
            home = str(row["home_team_id"])
            away = str(row["away_team_id"])
            hs = int(row["home_score"])
            away_score = int(row["away_score"])
            group_table = table.setdefault(group, {})
            home_stats = group_table.setdefault(
                home, {"points": 0, "goal_difference": 0, "goals_for": 0, "played": 0}
            )
            away_stats = group_table.setdefault(
                away, {"points": 0, "goal_difference": 0, "goals_for": 0, "played": 0}
            )
            home_stats["played"] += 1
            away_stats["played"] += 1
            home_stats["goals_for"] += hs
            away_stats["goals_for"] += away_score
            home_stats["goal_difference"] += hs - away_score
            away_stats["goal_difference"] += away_score - hs
            if hs > away_score:
                home_stats["points"] += 3
            elif away_score > hs:
                away_stats["points"] += 3
            else:
                home_stats["points"] += 1
                away_stats["points"] += 1

        contexts: dict[str, dict[str, TeamContext]] = {}
        for group, group_table in table.items():
            ranked = sorted(
                group_table.items(),
                key=lambda item: (
                    -item[1]["points"],
                    -item[1]["goal_difference"],
                    -item[1]["goals_for"],
                    item[0],
                ),
            )
            contexts[group] = {
                team_id: TeamContext(
                    points=stats["points"],
                    goal_difference=stats["goal_difference"],
                    goals_for=stats["goals_for"],
                    played=stats["played"],
                    rank=rank,
                )
                for rank, (team_id, stats) in enumerate(ranked, start=1)
            }
        return contexts


def _oriented_completed_group_results(
    train_matches_df: pd.DataFrame,
    group_fixtures: pd.DataFrame,
) -> list[dict[str, Any]]:
    matches = train_matches_df.copy()
    if "date" not in matches.columns:
        return []
    matches["date"] = pd.to_datetime(matches["date"], errors="coerce")
    completed = matches.dropna(subset=["date", "home_score", "away_score"])
    keyed: dict[tuple[frozenset[str], str], dict[str, Any]] = {}
    for row in completed.to_dict("records"):
        home = str(row.get("home_team_id"))
        away = str(row.get("away_team_id"))
        day = pd.to_datetime(row["date"]).strftime("%Y-%m-%d")
        keyed[(frozenset((home, away)), day)] = row

    rows: list[dict[str, Any]] = []
    for fixture in group_fixtures.to_dict("records"):
        home = str(fixture.get("home_team_id"))
        away = str(fixture.get("away_team_id"))
        day = pd.to_datetime(fixture.get("match_date"), errors="coerce")
        if pd.isna(day):
            continue
        hit = keyed.get((frozenset((home, away)), day.strftime("%Y-%m-%d")))
        if hit is None:
            continue
        hit_home = str(hit.get("home_team_id"))
        if hit_home == home:
            home_score = int(hit["home_score"])
            away_score = int(hit["away_score"])
        else:
            home_score = int(hit["away_score"])
            away_score = int(hit["home_score"])
        rows.append(
            {
                "group": fixture.get("group"),
                "home_team_id": home,
                "away_team_id": away,
                "home_score": home_score,
                "away_score": away_score,
            }
        )
    return rows


def _boost_draw(probs: list[float], amount: float) -> list[float]:
    if amount <= 0.0:
        return _normalize(probs)
    non_draw = probs[0] + probs[2]
    amount = min(amount, non_draw * 0.8)
    if non_draw <= 0.0:
        return _normalize(probs)
    scale = (non_draw - amount) / non_draw
    return _normalize([probs[0] * scale, probs[1] + amount, probs[2] * scale])


def _shift_from_favorite(
    probs: list[float],
    *,
    favorite_side: int,
    underdog_side: int,
    amount: float,
) -> list[float]:
    if amount <= 0.0:
        return _normalize(probs)
    amount = min(amount, probs[favorite_side] * 0.5)
    shifted = list(probs)
    shifted[favorite_side] -= amount
    shifted[1] += amount * 0.5
    shifted[underdog_side] += amount * 0.5
    return _normalize(shifted)


def _normalize(probs: list[float]) -> list[float]:
    cleaned = [max(0.0, float(value)) for value in probs]
    total = sum(cleaned)
    if total <= 0.0:
        return [1 / 3, 1 / 3, 1 / 3]
    home = cleaned[0] / total
    draw = cleaned[1] / total
    away = max(0.0, 1.0 - home - draw)
    return [home, draw, away]


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn, load_silver_data

    _matches, fixtures, _teams = load_silver_data()
    return GroupIncentiveElo(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
        fixture_schedule_df=fixtures,
    )
