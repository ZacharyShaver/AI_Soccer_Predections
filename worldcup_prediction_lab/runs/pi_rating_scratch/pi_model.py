"""Scratch (not committed): online pi-rating model (Constantinou & Fenton 2013).

Pi-ratings keep TWO ratings per team — home-ground and away-ground — updated
from the discrepancy between observed and expected goal difference, with a
cross-update (gamma) flowing a fraction of each home-ground lesson into the
away-ground rating and vice versa. The paper's selling point is that home
advantage becomes a per-team learned quantity instead of a global constant.

Adaptations for this lab (documented, honest):
* International football is neutral-heavy (whole WC group stage). At a
  neutral venue both sides use the MEAN of their two ratings; a host-aware
  fn can still assign true home ground (same convention as Elo/DC here).
* The paper feeds ratings into a separate probability model. Here expected
  goal difference maps to H/D/A via a Poisson goal split around a fixed
  total (T=2.6): home_xg=(T+gd_hat)/2, away_xg=(T-gd_hat)/2, floored — the
  same grid-summing layer Dixon-Coles uses, minus the tau correction.
"""

from __future__ import annotations

from math import exp, log10

import pandas as pd

from wc_predictor.models.elo import _bool_value, _team_id

C_SCALE = 3.0


def _expectation(rating: float) -> float:
    """Signed goal-difference expectation from a rating (paper's phi)."""

    return (10.0 ** (abs(rating) / C_SCALE) - 1.0) * (1.0 if rating >= 0 else -1.0)


def _psi(error: float) -> float:
    """Diminishing weight of a goal-difference error (paper's psi)."""

    return C_SCALE * log10(1.0 + abs(error)) * (1.0 if error >= 0 else -1.0)


def _poisson_pmf(rate: float, max_goals: int) -> list[float]:
    probabilities = [exp(-rate)]
    for goals in range(1, max_goals + 1):
        probabilities.append(probabilities[-1] * rate / goals)
    return probabilities


class PiRatingPrediction:
    __slots__ = ("prob_home", "prob_draw", "prob_away")

    def __init__(self, prob_home: float, prob_draw: float, prob_away: float) -> None:
        self.prob_home = prob_home
        self.prob_draw = prob_draw
        self.prob_away = prob_away


class PiRatingModel:
    def __init__(
        self,
        *,
        lam: float = 0.06,
        gamma: float = 0.5,
        total_goals: float = 2.6,
        max_goals: int = 10,
        host_advantage_fn=None,
    ) -> None:
        self.lam = float(lam)
        self.gamma = float(gamma)
        self.total_goals = float(total_goals)
        self.max_goals = int(max_goals)
        self.host_advantage_fn = host_advantage_fn
        self.home_ratings: dict[str, float] = {}
        self.away_ratings: dict[str, float] = {}

    def _venue(self, match_row: pd.Series, home_id: str, away_id: str) -> str:
        host = (
            self.host_advantage_fn(match_row, home_id, away_id)
            if self.host_advantage_fn is not None
            else None
        )
        if host in ("home", "away"):
            return host
        return "neutral" if _bool_value(match_row.get("neutral", False)) else "home"

    def _side_expectations(self, match_row: pd.Series, home_id: str, away_id: str):
        rh_home = self.home_ratings.get(home_id, 0.0)
        ra_home = self.away_ratings.get(home_id, 0.0)
        rh_away = self.home_ratings.get(away_id, 0.0)
        ra_away = self.away_ratings.get(away_id, 0.0)
        venue = self._venue(match_row, home_id, away_id)
        if venue == "home":
            return _expectation(rh_home), _expectation(ra_away), venue
        if venue == "away":  # nominal away side is the true host
            return _expectation(ra_home), _expectation(rh_away), venue
        mean_home = 0.5 * (rh_home + ra_home)
        mean_away = 0.5 * (rh_away + ra_away)
        return _expectation(mean_home), _expectation(mean_away), venue

    def predict_match(self, match_row: pd.Series) -> PiRatingPrediction:
        home_id = _team_id(match_row, "home_team_id", "home_team")
        away_id = _team_id(match_row, "away_team_id", "away_team")
        e_home, e_away, _ = self._side_expectations(match_row, home_id, away_id)
        gd_hat = e_home - e_away
        home_xg = max(0.15, (self.total_goals + gd_hat) / 2.0)
        away_xg = max(0.15, (self.total_goals - gd_hat) / 2.0)
        home_pmf = _poisson_pmf(home_xg, self.max_goals)
        away_pmf = _poisson_pmf(away_xg, self.max_goals)
        masses = [0.0, 0.0, 0.0]  # home, draw, away
        for h, ph in enumerate(home_pmf):
            for a, pa in enumerate(away_pmf):
                p = ph * pa
                if h > a:
                    masses[0] += p
                elif h == a:
                    masses[1] += p
                else:
                    masses[2] += p
        total = sum(masses)
        return PiRatingPrediction(masses[0] / total, masses[1] / total, masses[2] / total)

    def _update_from_match(self, match_row: pd.Series) -> None:
        home_id = _team_id(match_row, "home_team_id", "home_team")
        away_id = _team_id(match_row, "away_team_id", "away_team")
        e_home, e_away, venue = self._side_expectations(match_row, home_id, away_id)
        observed = float(match_row["home_score"]) - float(match_row["away_score"])
        error = observed - (e_home - e_away)
        step = _psi(error) * self.lam

        if venue == "home":
            self.home_ratings[home_id] = self.home_ratings.get(home_id, 0.0) + step
            self.away_ratings[home_id] = self.away_ratings.get(home_id, 0.0) + step * self.gamma
            self.away_ratings[away_id] = self.away_ratings.get(away_id, 0.0) - step
            self.home_ratings[away_id] = self.home_ratings.get(away_id, 0.0) - step * self.gamma
        elif venue == "away":
            self.away_ratings[home_id] = self.away_ratings.get(home_id, 0.0) + step
            self.home_ratings[home_id] = self.home_ratings.get(home_id, 0.0) + step * self.gamma
            self.home_ratings[away_id] = self.home_ratings.get(away_id, 0.0) - step
            self.away_ratings[away_id] = self.away_ratings.get(away_id, 0.0) - step * self.gamma
        else:  # neutral: split the lesson evenly across both grounds
            half = step * 0.5 * (1.0 + self.gamma)
            self.home_ratings[home_id] = self.home_ratings.get(home_id, 0.0) + half
            self.away_ratings[home_id] = self.away_ratings.get(home_id, 0.0) + half
            self.home_ratings[away_id] = self.home_ratings.get(away_id, 0.0) - half
            self.away_ratings[away_id] = self.away_ratings.get(away_id, 0.0) - half
