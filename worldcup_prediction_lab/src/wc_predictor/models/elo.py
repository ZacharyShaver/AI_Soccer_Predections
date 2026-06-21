"""Sequential Elo model for international match outcome probabilities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import exp, log
from typing import Any, Literal

import pandas as pd

from wc_predictor.models.base import ScorelineDistribution


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
        generated_at_utc: str = "1970-01-01T00:00:00Z",
        base_total_goals: float = 2.65,
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
        if base_total_goals <= 0.0:
            raise ValueError("base_total_goals must be positive")

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
        self.generated_at_utc = generated_at_utc
        self.base_total_goals = float(base_total_goals)
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

    def predict_scoreline(self, match_row: pd.Series) -> ScorelineDistribution:
        """Return a calibrated scoreline grid consistent with M4 outcomes.

        Expected goals are a deterministic mapping from adjusted Elo strength:
        the total-goal baseline is fixed, and the home/away split follows the
        Elo expected score. The independent Poisson grid is then scaled inside
        home-win, draw, and away-win buckets so the finite matrix preserves the
        M4 three-way probabilities; `tail_probability` keeps the mass for
        scores beyond `max_goals` separate.
        """

        home_team_id = _team_id(match_row, "home_team_id", "home_team")
        away_team_id = _team_id(match_row, "away_team_id", "away_team")
        home_rating = self.get_rating(home_team_id)
        away_rating = self.get_rating(away_team_id)
        home_advantage_elo = self._home_advantage_elo(
            match_row, home_team_id, away_team_id
        )
        outcome_probabilities = self._outcome_probabilities(
            home_rating, away_rating, home_advantage_elo
        )
        home_expected_goals, away_expected_goals = self._expected_goals(
            home_rating, away_rating, home_advantage_elo
        )
        probabilities, tail_probability = self._scoreline_probabilities(
            home_expected_goals,
            away_expected_goals,
            outcome_probabilities,
        )
        return ScorelineDistribution(
            match_id=str(match_row.get("match_id", "")),
            model_id=self.model_id,
            generated_at_utc=self.generated_at_utc,
            max_goals=self.max_goals,
            home_expected_goals=home_expected_goals,
            away_expected_goals=away_expected_goals,
            probabilities=probabilities,
            tail_probability=tail_probability,
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

    def _expected_goals(
        self, home_rating: float, away_rating: float, home_advantage_elo: float
    ) -> tuple[float, float]:
        expected_home_score = self._expected_score(
            home_rating, away_rating, home_advantage_elo
        )
        adjusted_diff = home_rating + home_advantage_elo - away_rating
        total_goals = self.base_total_goals + min(abs(adjusted_diff), 600.0) / 600.0 * 0.25
        home_goal_share = 0.2 + (0.6 * expected_home_score)
        away_goal_share = 1.0 - home_goal_share
        return total_goals * home_goal_share, total_goals * away_goal_share

    def _scoreline_probabilities(
        self,
        home_expected_goals: float,
        away_expected_goals: float,
        outcome_probabilities: tuple[float, float, float],
    ) -> tuple[dict[str, float], float]:
        home_pmf = _poisson_pmf(home_expected_goals, self.max_goals)
        away_pmf = _poisson_pmf(away_expected_goals, self.max_goals)
        probabilities: dict[str, float] = {}
        group_masses = {"home": 0.0, "draw": 0.0, "away": 0.0}

        for home_goals, home_probability in enumerate(home_pmf):
            for away_goals, away_probability in enumerate(away_pmf):
                probability = home_probability * away_probability
                scoreline = f"{home_goals}-{away_goals}"
                probabilities[scoreline] = probability
                group_masses[_outcome_group(home_goals, away_goals)] += probability

        finite_mass = sum(probabilities.values())
        if finite_mass <= 0.0:
            raise ValueError("scoreline probabilities have no finite mass")

        target_group_masses = {
            "home": outcome_probabilities[0] * finite_mass,
            "draw": outcome_probabilities[1] * finite_mass,
            "away": outcome_probabilities[2] * finite_mass,
        }
        scaled_probabilities: dict[str, float] = {}
        for scoreline, probability in probabilities.items():
            home_goals, away_goals = _parse_scoreline(scoreline)
            group = _outcome_group(home_goals, away_goals)
            group_mass = group_masses[group]
            if group_mass <= 0.0:
                scaled_probabilities[scoreline] = 0.0
            else:
                scaled_probabilities[scoreline] = (
                    probability * target_group_masses[group] / group_mass
                )

        scaled_finite_mass = sum(scaled_probabilities.values())
        if scaled_finite_mass <= 0.0:
            raise ValueError("scoreline probabilities have no calibrated mass")
        tail_probability = max(0.0, 1.0 - scaled_finite_mass)
        return scaled_probabilities, tail_probability

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


def _poisson_pmf(rate: float, max_goals: int) -> list[float]:
    if rate < 0.0:
        raise ValueError("Poisson rate must be non-negative")

    probabilities = [exp(-rate)]
    for goals in range(1, max_goals + 1):
        probabilities.append(probabilities[-1] * rate / goals)
    return probabilities


def _parse_scoreline(scoreline: str) -> tuple[int, int]:
    home_goals_text, away_goals_text = scoreline.split("-", maxsplit=1)
    return int(home_goals_text), int(away_goals_text)


def _outcome_group(home_goals: int, away_goals: int) -> Literal["home", "draw", "away"]:
    if home_goals > away_goals:
        return "home"
    if home_goals == away_goals:
        return "draw"
    return "away"


def outcome_probabilities_from_scoreline(
    distribution: ScorelineDistribution,
) -> tuple[float, float, float]:
    """Derive finite-matrix home/draw/away probabilities from a distribution."""

    home_mass = 0.0
    draw_mass = 0.0
    away_mass = 0.0
    for scoreline, probability in distribution.probabilities.items():
        home_goals, away_goals = _parse_scoreline(scoreline)
        if home_goals > away_goals:
            home_mass += probability
        elif home_goals == away_goals:
            draw_mass += probability
        else:
            away_mass += probability

    finite_mass = home_mass + draw_mass + away_mass
    if finite_mass <= 0.0:
        raise ValueError("scoreline probabilities have no finite mass")
    prob_home = home_mass / finite_mass
    prob_draw = draw_mass / finite_mass
    prob_away = max(0.0, 1.0 - prob_home - prob_draw)
    return prob_home, prob_draw, prob_away


def top_scorelines(
    distribution: ScorelineDistribution, count: int = 5
) -> list[tuple[str, float]]:
    if count < 0:
        raise ValueError("count must be non-negative")
    return sorted(
        distribution.probabilities.items(),
        key=lambda item: (-item[1], item[0]),
    )[:count]


def top_scoreline(distribution: ScorelineDistribution) -> tuple[str, float]:
    return top_scorelines(distribution, 1)[0]


def draw_probability(distribution: ScorelineDistribution) -> float:
    return outcome_probabilities_from_scoreline(distribution)[1]


def home_win_probability(distribution: ScorelineDistribution) -> float:
    return outcome_probabilities_from_scoreline(distribution)[0]


def away_win_probability(distribution: ScorelineDistribution) -> float:
    return outcome_probabilities_from_scoreline(distribution)[2]


def over_probability(distribution: ScorelineDistribution, threshold: float) -> float:
    return sum(
        probability
        for scoreline, probability in distribution.probabilities.items()
        if sum(_parse_scoreline(scoreline)) > threshold
    )


def under_probability(distribution: ScorelineDistribution, threshold: float) -> float:
    return sum(
        probability
        for scoreline, probability in distribution.probabilities.items()
        if sum(_parse_scoreline(scoreline)) < threshold
    )


def btts_probability(distribution: ScorelineDistribution) -> float:
    return sum(
        probability
        for scoreline, probability in distribution.probabilities.items()
        if all(goals > 0 for goals in _parse_scoreline(scoreline))
    )


def elo_model(**kwargs: Any) -> EloModel:
    """Create a backtest-compatible Elo model."""

    return EloModel(**kwargs)
