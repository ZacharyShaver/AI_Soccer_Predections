"""Online Dixon-Coles-style Poisson attack/defense model.

Elo scores *outcomes* (win/draw/loss) directly. This model instead scores
*goals*: each team carries an attack rating and a defense rating in log-rate
space, and a match's expected goals are exp(mu + attack_home - defense_away +
home_edge) for the home side (mirrored for away). That is the classic
Dixon & Coles (1997) bivariate-Poisson parameterization, including their
low-score correlation correction tau(x, y) for the 0-0/1-0/0-1/1-1 cell.

The one deliberate departure from the textbook version: Dixon-Coles is
normally fit by batch maximum likelihood over the whole history at once. The
backtest harness's online sample (``score_on_history``) needs a model that
predicts-then-updates one match at a time, so ratings here are updated by a
single Poisson-regression gradient step per match instead -- the same online
contract Elo already satisfies (``predict_match`` then ``_update_from_match``),
just with a goal-count likelihood instead of a win-probability likelihood.
``rho`` (the low-score correction) is a fixed hyperparameter rather than
jointly fit, since it changes little in the literature and online-fitting a
single global scalar isn't worth the extra moving part.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import exp, log
from typing import Any

import pandas as pd

from wc_predictor.models.base import ScorelineDistribution
from wc_predictor.models.elo import HostAdvantageFn, _bool_value, _date_text, _team_id


@dataclass(frozen=True)
class DixonColesPrediction:
    prob_home: float
    prob_draw: float
    prob_away: float
    home_expected_goals: float
    away_expected_goals: float


class DixonColesModel:
    """Online Poisson attack/defense rating model (Dixon-Coles inspired)."""

    model_id = "dixon_coles_poisson_v1"
    model_version = "dc_online_v1"

    def __init__(
        self,
        *,
        learning_rate: float = 0.06,
        home_edge_learning_rate: float = 0.02,
        baseline_learning_rate: float = 0.01,
        shrinkage: float = 0.0008,
        home_edge_init: float = 0.18,
        baseline_init: float = 0.30,
        rho: float = -0.10,
        max_goals: int = 10,
        generated_at_utc: str = "1970-01-01T00:00:00Z",
        host_advantage_fn: HostAdvantageFn | None = None,
    ) -> None:
        if learning_rate <= 0.0:
            raise ValueError("learning_rate must be positive")
        if max_goals < 0:
            raise ValueError("max_goals must be non-negative")

        self.learning_rate = float(learning_rate)
        self.home_edge_learning_rate = float(home_edge_learning_rate)
        self.baseline_learning_rate = float(baseline_learning_rate)
        self.shrinkage = float(shrinkage)
        self.home_edge_init = float(home_edge_init)
        self.baseline_init = float(baseline_init)
        self.rho = float(rho)
        self.max_goals = int(max_goals)
        self.generated_at_utc = generated_at_utc
        self.host_advantage_fn = host_advantage_fn

        self.attack: dict[str, float] = {}
        self.defense: dict[str, float] = {}
        self.home_edge = self.home_edge_init
        self.baseline = self.baseline_init
        self.last_updated: dict[str, str] = {}

    def fit(self, train_matches_df: pd.DataFrame) -> "DixonColesModel":
        self.attack = {}
        self.defense = {}
        self.home_edge = self.home_edge_init
        self.baseline = self.baseline_init
        self.last_updated = {}
        if train_matches_df.empty:
            return self

        required_columns = {"date", "home_team_id", "away_team_id", "home_score", "away_score"}
        missing = required_columns - set(train_matches_df.columns)
        if missing:
            raise ValueError(f"train_matches_df missing required columns: {sorted(missing)}")

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

    def get_attack(self, team_id: str) -> float:
        return self.attack.get(str(team_id), 0.0)

    def get_defense(self, team_id: str) -> float:
        return self.defense.get(str(team_id), 0.0)

    def get_rating(self, team_id: str) -> float:
        """Single-number strength proxy (attack minus defense weakness), for parity with Elo."""

        return self.get_attack(team_id) - self.get_defense(team_id)

    def predict_match(self, match_row: pd.Series) -> DixonColesPrediction:
        home_id = _team_id(match_row, "home_team_id", "home_team")
        away_id = _team_id(match_row, "away_team_id", "away_team")
        home_xg, away_xg = self._expected_goals(match_row, home_id, away_id)
        prob_home, prob_draw, prob_away, _ = self._outcome_probabilities(home_xg, away_xg)
        return DixonColesPrediction(
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
            home_expected_goals=home_xg,
            away_expected_goals=away_xg,
        )

    def predict_scoreline(self, match_row: pd.Series) -> ScorelineDistribution:
        home_id = _team_id(match_row, "home_team_id", "home_team")
        away_id = _team_id(match_row, "away_team_id", "away_team")
        home_xg, away_xg = self._expected_goals(match_row, home_id, away_id)
        _, _, _, grid = self._outcome_probabilities(home_xg, away_xg)
        finite_mass = sum(grid.values())
        tail_probability = max(0.0, 1.0 - finite_mass)
        return ScorelineDistribution(
            match_id=str(match_row.get("match_id", "")),
            model_id=self.model_id,
            generated_at_utc=self.generated_at_utc,
            max_goals=self.max_goals,
            home_expected_goals=home_xg,
            away_expected_goals=away_xg,
            probabilities=grid,
            tail_probability=tail_probability,
        )

    def _update_from_match(self, match_row: pd.Series) -> None:
        home_id = _team_id(match_row, "home_team_id", "home_team")
        away_id = _team_id(match_row, "away_team_id", "away_team")
        home_score = float(match_row["home_score"])
        away_score = float(match_row["away_score"])

        home_xg, away_xg = self._expected_goals(match_row, home_id, away_id)
        home_resid = home_score - home_xg
        away_resid = away_score - away_xg

        attack_home = self.get_attack(home_id)
        defense_home = self.get_defense(home_id)
        attack_away = self.get_attack(away_id)
        defense_away = self.get_defense(away_id)

        lr = self.learning_rate
        self.attack[home_id] = attack_home + lr * home_resid - self.shrinkage * attack_home
        self.defense[away_id] = defense_away - lr * home_resid - self.shrinkage * defense_away
        self.attack[away_id] = attack_away + lr * away_resid - self.shrinkage * attack_away
        self.defense[home_id] = defense_home - lr * away_resid - self.shrinkage * defense_home

        # Home-edge only attaches to whichever side is actually hosting; update
        # from that side's residual (host_sign>0 -> home side hosts -> home_resid,
        # host_sign<0 -> away side hosts -> away_resid).
        host_sign = self._host_sign(match_row, home_id, away_id)
        if host_sign > 0.0:
            self.home_edge += self.home_edge_learning_rate * home_resid
        elif host_sign < 0.0:
            self.home_edge += self.home_edge_learning_rate * away_resid

        self.baseline += self.baseline_learning_rate * 0.5 * (home_resid + away_resid)

        date_text = _date_text(match_row.get("date"))
        self.last_updated[home_id] = date_text
        self.last_updated[away_id] = date_text

    def _host_sign(self, match_row: pd.Series, home_id: str, away_id: str) -> float:
        host_side = (
            self.host_advantage_fn(match_row, home_id, away_id)
            if self.host_advantage_fn is not None
            else None
        )
        if host_side == "home":
            return 1.0
        if host_side == "away":
            return -1.0
        if _bool_value(match_row.get("neutral", False)):
            return 0.0
        return 1.0

    def _expected_goals(
        self, match_row: pd.Series, home_id: str, away_id: str
    ) -> tuple[float, float]:
        host_sign = self._host_sign(match_row, home_id, away_id)
        home_log_rate = self.baseline + self.get_attack(home_id) - self.get_defense(away_id)
        away_log_rate = self.baseline + self.get_attack(away_id) - self.get_defense(home_id)
        if host_sign > 0.0:
            home_log_rate += self.home_edge
        elif host_sign < 0.0:
            away_log_rate += self.home_edge
        home_log_rate = max(-4.0, min(4.0, home_log_rate))
        away_log_rate = max(-4.0, min(4.0, away_log_rate))
        return exp(home_log_rate), exp(away_log_rate)

    def _outcome_probabilities(
        self, home_xg: float, away_xg: float
    ) -> tuple[float, float, float, dict[str, float]]:
        home_pmf = _poisson_pmf(home_xg, self.max_goals)
        away_pmf = _poisson_pmf(away_xg, self.max_goals)
        grid: dict[str, float] = {}
        masses = {"home": 0.0, "draw": 0.0, "away": 0.0}
        for h, ph in enumerate(home_pmf):
            for a, pa in enumerate(away_pmf):
                tau = _dixon_coles_tau(h, a, home_xg, away_xg, self.rho)
                p = max(0.0, ph * pa * tau)
                grid[f"{h}-{a}"] = p
                if h > a:
                    masses["home"] += p
                elif h == a:
                    masses["draw"] += p
                else:
                    masses["away"] += p

        finite_mass = masses["home"] + masses["draw"] + masses["away"]
        if finite_mass <= 0.0:
            raise ValueError("Dixon-Coles outcome probabilities have no mass")
        prob_home = masses["home"] / finite_mass
        prob_draw = masses["draw"] / finite_mass
        prob_away = max(0.0, 1.0 - prob_home - prob_draw)
        return prob_home, prob_draw, prob_away, grid


def _dixon_coles_tau(x: int, y: int, lambda_home: float, lambda_away: float, rho: float) -> float:
    if x == 0 and y == 0:
        return 1.0 - (lambda_home * lambda_away * rho)
    if x == 0 and y == 1:
        return 1.0 + (lambda_home * rho)
    if x == 1 and y == 0:
        return 1.0 + (lambda_away * rho)
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def _poisson_pmf(rate: float, max_goals: int) -> list[float]:
    if rate < 0.0:
        raise ValueError("Poisson rate must be non-negative")
    probabilities = [exp(-rate)]
    for goals in range(1, max_goals + 1):
        probabilities.append(probabilities[-1] * rate / goals)
    return probabilities


def dixon_coles_model(**kwargs: Any) -> DixonColesModel:
    return DixonColesModel(**kwargs)
