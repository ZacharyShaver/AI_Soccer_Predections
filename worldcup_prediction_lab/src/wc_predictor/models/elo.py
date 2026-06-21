"""Sequential Elo model for international match outcome probabilities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import exp, log
from typing import Any, Literal

import pandas as pd


HostAdvantageSide = Literal["home", "away"] | None
HostAdvantageFn = Callable[[pd.Series, str, str], HostAdvantageSide]


DEFAULT_TOURNAMENT_WEIGHTS: dict[str, float] = {
    "Friendly": 0.75,
    "FIFA World Cup": 1.5,
    "FIFA World Cup qualification": 1.25,
    "UEFA Euro": 1.35,
    "Copa America": 1.35,
    "CONCACAF Championship": 1.2,
    "CONCACAF Nations League": 1.0,
    "UEFA Nations League": 1.0,
    "African Cup of Nations": 1.25,
    "AFC Asian Cup": 1.25,
}


@dataclass(frozen=True)
class EloPrediction:
    prob_home: float
    prob_draw: float
    prob_away: float
    pre_match_home_rating: float
    pre_match_away_rating: float
    home_advantage_elo: float


class EloModel:
    """Online Elo model compatible with the backtest model protocol.

    Draws are handled by reserving a draw mass that is largest when adjusted
    ratings are close and decays as teams separate. The remaining mass is split
    so the three-way distribution preserves the standard Elo expected score.
    """

    model_id = "elo_poisson_v1"
    model_version = "m4_outcome_v1"

    def __init__(
        self,
        *,
        base_rating: float = 1500.0,
        k_factor: float = 20.0,
        home_advantage: float = 75.0,
        tournament_weights: Mapping[str, float] | None = None,
        default_tournament_weight: float = 1.0,
        draw_base_probability: float = 0.27,
        draw_rating_scale: float = 400.0,
        max_goals: int = 10,
        host_advantage_fn: HostAdvantageFn | None = None,
    ) -> None:
        if k_factor <= 0.0:
            raise ValueError("k_factor must be positive")
        if draw_base_probability < 0.0 or draw_base_probability >= 1.0:
            raise ValueError("draw_base_probability must be in [0.0, 1.0)")
        if draw_rating_scale <= 0.0:
            raise ValueError("draw_rating_scale must be positive")
        if max_goals < 0:
            raise ValueError("max_goals must be non-negative")

        self.base_rating = float(base_rating)
        self.k_factor = float(k_factor)
        self.home_advantage = float(home_advantage)
        self.tournament_weights = dict(DEFAULT_TOURNAMENT_WEIGHTS)
        if tournament_weights is not None:
            self.tournament_weights.update(
                {str(key): float(value) for key, value in tournament_weights.items()}
            )
        self.default_tournament_weight = float(default_tournament_weight)
        self.draw_base_probability = float(draw_base_probability)
        self.draw_rating_scale = float(draw_rating_scale)
        self.max_goals = int(max_goals)
        self.host_advantage_fn = host_advantage_fn
        self.ratings: dict[str, float] = {}
        self.last_updated: dict[str, str] = {}

    def fit(self, train_matches_df: pd.DataFrame) -> EloModel:
        """Fit ratings by replaying matches in chronological order."""

        self.ratings = {}
        self.last_updated = {}
        if train_matches_df.empty:
            return self

        required_columns = {
            "date",
            "home_team_id",
            "away_team_id",
            "home_score",
            "away_score",
        }
        missing_columns = required_columns - set(train_matches_df.columns)
        if missing_columns:
            raise ValueError(
                f"train_matches_df missing required columns: {sorted(missing_columns)}"
            )

        matches = train_matches_df.copy()
        matches["date"] = pd.to_datetime(matches["date"])
        sort_columns = ["date"]
        if "occurrence_index" in matches.columns:
            sort_columns.append("occurrence_index")
        if "match_id" in matches.columns:
            sort_columns.append("match_id")
        matches = matches.sort_values(sort_columns).reset_index(drop=True)

        for _, match_row in matches.iterrows():
            self._update_from_match(match_row)
        return self

    def predict_match(self, match_row: pd.Series) -> EloPrediction:
        home_team_id = _team_id(match_row, "home_team_id", "home_team")
        away_team_id = _team_id(match_row, "away_team_id", "away_team")
        home_rating = self.get_rating(home_team_id)
        away_rating = self.get_rating(away_team_id)
        home_advantage_elo = self._home_advantage_elo(
            match_row, home_team_id, away_team_id
        )
        prob_home, prob_draw, prob_away = self._outcome_probabilities(
            home_rating, away_rating, home_advantage_elo
        )
        return EloPrediction(
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
            pre_match_home_rating=home_rating,
            pre_match_away_rating=away_rating,
            home_advantage_elo=home_advantage_elo,
        )

    def get_rating(self, team_id: str) -> float:
        """Return the current rating for a team, defaulting unknown teams."""

        return self.ratings.get(str(team_id), self.base_rating)

    def _update_from_match(self, match_row: pd.Series) -> None:
        home_team_id = _team_id(match_row, "home_team_id", "home_team")
        away_team_id = _team_id(match_row, "away_team_id", "away_team")
        home_rating = self.get_rating(home_team_id)
        away_rating = self.get_rating(away_team_id)
        home_score = int(match_row["home_score"])
        away_score = int(match_row["away_score"])

        actual_home_score = _actual_score(home_score, away_score)
        home_advantage_elo = self._home_advantage_elo(
            match_row, home_team_id, away_team_id
        )
        expected_home_score = self._expected_score(
            home_rating, away_rating, home_advantage_elo
        )
        rating_change = (
            self.k_factor
            * self._tournament_weight(match_row)
            * self._goal_difference_multiplier(
                abs(home_score - away_score), home_rating - away_rating
            )
            * (actual_home_score - expected_home_score)
        )

        self.ratings[home_team_id] = home_rating + rating_change
        self.ratings[away_team_id] = away_rating - rating_change
        date_text = _date_text(match_row.get("date"))
        self.last_updated[home_team_id] = date_text
        self.last_updated[away_team_id] = date_text

    def _outcome_probabilities(
        self, home_rating: float, away_rating: float, home_advantage_elo: float
    ) -> tuple[float, float, float]:
        expected_home_score = self._expected_score(
            home_rating, away_rating, home_advantage_elo
        )
        adjusted_diff = home_rating + home_advantage_elo - away_rating
        draw_probability = self.draw_base_probability * exp(
            -abs(adjusted_diff) / self.draw_rating_scale
        )
        draw_probability = min(
            draw_probability,
            2.0 * expected_home_score,
            2.0 * (1.0 - expected_home_score),
        )
        draw_probability = max(0.0, draw_probability)
        prob_home = expected_home_score - (0.5 * draw_probability)
        prob_away = 1.0 - draw_probability - prob_home

        prob_home = max(0.0, min(1.0, prob_home))
        prob_draw = max(0.0, min(1.0, draw_probability))
        prob_away = max(0.0, min(1.0, prob_away))
        total = prob_home + prob_draw + prob_away
        if total <= 0.0:
            raise ValueError("Elo outcome probabilities have no mass")
        prob_home /= total
        prob_draw /= total
        prob_away = max(0.0, 1.0 - prob_home - prob_draw)
        return prob_home, prob_draw, prob_away

    @staticmethod
    def _expected_score(
        home_rating: float, away_rating: float, home_advantage_elo: float
    ) -> float:
        rating_diff = home_rating + home_advantage_elo - away_rating
        return 1.0 / (1.0 + 10.0 ** (-rating_diff / 400.0))

    def _home_advantage_elo(
        self, match_row: pd.Series, home_team_id: str, away_team_id: str
    ) -> float:
        host_side = (
            self.host_advantage_fn(match_row, home_team_id, away_team_id)
            if self.host_advantage_fn is not None
            else None
        )
        if host_side == "home":
            return self.home_advantage
        if host_side == "away":
            return -self.home_advantage

        neutral = _bool_value(match_row.get("neutral", False))
        if neutral:
            return 0.0
        return self.home_advantage

    def _tournament_weight(self, match_row: pd.Series) -> float:
        tournament = str(match_row.get("tournament", ""))
        return self.tournament_weights.get(tournament, self.default_tournament_weight)

    @staticmethod
    def _goal_difference_multiplier(goal_difference: int, rating_diff: float) -> float:
        if goal_difference <= 1:
            return 1.0
        return log(goal_difference + 1.0) * (2.2 / (0.001 * abs(rating_diff) + 2.2))


def _actual_score(home_score: int, away_score: int) -> float:
    if home_score > away_score:
        return 1.0
    if home_score == away_score:
        return 0.5
    return 0.0


def _team_id(match_row: pd.Series, id_column: str, fallback_column: str) -> str:
    value = match_row.get(id_column)
    if pd.isna(value):
        value = match_row.get(fallback_column)
    if pd.isna(value):
        raise ValueError(f"match_row missing {id_column}/{fallback_column}")
    return str(value)


def _bool_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(value)


def _date_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def elo_model(**kwargs: Any) -> EloModel:
    """Create a backtest-compatible Elo model."""

    return EloModel(**kwargs)
