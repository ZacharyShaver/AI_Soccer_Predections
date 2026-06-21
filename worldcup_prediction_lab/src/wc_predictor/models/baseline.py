"""Climatology baseline model for match outcome and scoreline prediction."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Any

import pandas as pd

from wc_predictor.models.base import ScorelineDistribution


@dataclass(frozen=True)
class BaselinePrediction:
    prob_home: float
    prob_draw: float
    prob_away: float
    scoreline_distribution: ScorelineDistribution


@dataclass(frozen=True)
class ClimatologyParameters:
    home_expected_goals: float
    away_expected_goals: float
    empirical_draw_rate: float
    training_match_count: int


class BaselineClimatology:
    """Global-rate baseline with no team-strength features."""

    model_id = "baseline_climatology"
    model_version = "v1"

    def __init__(
        self,
        *,
        max_goals: int = 10,
        generated_at_utc: str = "1970-01-01T00:00:00Z",
    ) -> None:
        if max_goals < 0:
            raise ValueError("max_goals must be non-negative")
        self.max_goals = max_goals
        self.generated_at_utc = generated_at_utc
        self.params: ClimatologyParameters | None = None

    def fit(self, train_matches_df: pd.DataFrame) -> BaselineClimatology:
        """Fit global scoring and draw rates from the supplied training rows only."""

        required_columns = {"home_score", "away_score"}
        missing_columns = required_columns - set(train_matches_df.columns)
        if missing_columns:
            raise ValueError(
                f"train_matches_df missing required columns: {sorted(missing_columns)}"
            )
        if train_matches_df.empty:
            raise ValueError("baseline_climatology requires at least one training match")

        home_scores = pd.to_numeric(train_matches_df["home_score"], errors="raise")
        away_scores = pd.to_numeric(train_matches_df["away_score"], errors="raise")
        draws = home_scores == away_scores
        self.params = ClimatologyParameters(
            home_expected_goals=float(home_scores.mean()),
            away_expected_goals=float(away_scores.mean()),
            empirical_draw_rate=float(draws.mean()),
            training_match_count=int(len(train_matches_df)),
        )
        return self

    def predict_match(self, match_row: pd.Series) -> BaselinePrediction:
        if self.params is None:
            raise ValueError("baseline_climatology must be fitted before prediction")

        probabilities, tail_probability = self._scoreline_probabilities(
            self.params.home_expected_goals,
            self.params.away_expected_goals,
        )
        prob_home, prob_draw, prob_away = self._outcome_probabilities(probabilities)
        scoreline_distribution = ScorelineDistribution(
            match_id=str(match_row.get("match_id", "")),
            model_id=self.model_id,
            generated_at_utc=self.generated_at_utc,
            max_goals=self.max_goals,
            home_expected_goals=self.params.home_expected_goals,
            away_expected_goals=self.params.away_expected_goals,
            probabilities=probabilities,
            tail_probability=tail_probability,
        )
        return BaselinePrediction(
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
            scoreline_distribution=scoreline_distribution,
        )

    def _scoreline_probabilities(
        self, home_expected_goals: float, away_expected_goals: float
    ) -> tuple[dict[str, float], float]:
        home_pmf = _poisson_pmf(home_expected_goals, self.max_goals)
        away_pmf = _poisson_pmf(away_expected_goals, self.max_goals)
        probabilities: dict[str, float] = {}
        finite_mass = 0.0
        for home_goals, home_probability in enumerate(home_pmf):
            for away_goals, away_probability in enumerate(away_pmf):
                probability = home_probability * away_probability
                probabilities[f"{home_goals}-{away_goals}"] = probability
                finite_mass += probability
        tail_probability = max(0.0, 1.0 - finite_mass)
        return probabilities, tail_probability

    @staticmethod
    def _outcome_probabilities(probabilities: dict[str, float]) -> tuple[float, float, float]:
        home_mass = 0.0
        draw_mass = 0.0
        away_mass = 0.0
        for scoreline, probability in probabilities.items():
            home_goals_text, away_goals_text = scoreline.split("-", maxsplit=1)
            home_goals = int(home_goals_text)
            away_goals = int(away_goals_text)
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


def _poisson_pmf(rate: float, max_goals: int) -> list[float]:
    if rate < 0.0:
        raise ValueError("Poisson rate must be non-negative")

    probabilities = [exp(-rate)]
    for goals in range(1, max_goals + 1):
        probabilities.append(probabilities[-1] * rate / goals)
    return probabilities


def baseline_climatology(**kwargs: Any) -> BaselineClimatology:
    """Create a backtest-compatible climatology baseline model."""

    return BaselineClimatology(**kwargs)
