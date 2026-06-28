"""Trained correction layer on top of recalibrated Elo.

This variant keeps ``elo_recalibrated`` as the spine. During ``fit`` it walks
through historical matches, records the pre-match recalibrated Elo probabilities
and simple rating/context features, then trains a small multinomial softmax
model to predict the actual home/draw/away result. At prediction time the
learned correction is blended back with the base Elo probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Iterable

import pandas as pd

from wc_predictor.lab.ml_correction import SoftmaxCorrection
from wc_predictor.lab.variants.elo_recalibrated import recalibrated_elo_kwargs
from wc_predictor.models.elo import EloModel, EloPrediction, HostAdvantageFn


VARIANT_ID = "ml_elo_correction"
DESCRIPTION = "Trained softmax correction layer blended with recalibrated Elo."
FEATURE_IDEA = (
    "Train on pre-match recalibrated Elo probabilities, rating spread, draw mass, "
    "neutral/host context, and tournament class; blend learned probabilities with Elo."
)

MIN_TRAINING_ROWS = 60
ML_BLEND_WEIGHT = 0.50


@dataclass(frozen=True)
class TrainingConfig:
    learning_rate: float = 0.05
    max_iter: int = 350
    l2: float = 0.02
    blend_weight: float = ML_BLEND_WEIGHT


class MLEloCorrectionModel:
    """Fit/predict protocol compatible with lab backtests and ledgers."""

    model_version = "ml_elo_correction_v1"

    def __init__(
        self,
        *,
        generated_at_utc: str,
        host_advantage_fn: HostAdvantageFn | None = None,
        config: TrainingConfig | None = None,
    ) -> None:
        self.generated_at_utc = generated_at_utc
        self.host_advantage_fn = host_advantage_fn
        self.config = config or TrainingConfig()
        self.base_model = self._fresh_base_model()
        self.correction: SoftmaxCorrection | None = None

    def fit(self, train_matches_df: pd.DataFrame) -> "MLEloCorrectionModel":
        self.base_model = self._fresh_base_model()
        self.correction = None
        if train_matches_df.empty:
            return self

        matches = _completed_matches(train_matches_df)
        if matches.empty:
            return self

        online_base = self._fresh_base_model()
        rows: list[list[float]] = []
        labels: list[int] = []
        for _, match_row in matches.iterrows():
            base_prediction = online_base.predict_match(match_row)
            rows.append(_feature_vector(match_row, base_prediction))
            labels.append(_outcome_label(match_row))
            online_base._update_from_match(match_row)

        self.base_model.fit(matches)
        if len(rows) >= MIN_TRAINING_ROWS and len(set(labels)) >= 2:
            self.correction = SoftmaxCorrection(
                learning_rate=self.config.learning_rate,
                max_iter=self.config.max_iter,
                l2=self.config.l2,
            ).fit(rows, labels)
        return self

    def predict_match(self, match_row: pd.Series) -> EloPrediction:
        base_prediction = self.base_model.predict_match(match_row)
        probs = [
            base_prediction.prob_home,
            base_prediction.prob_draw,
            base_prediction.prob_away,
        ]
        if self.correction is not None:
            learned = self.correction.predict_proba([_feature_vector(match_row, base_prediction)])[0]
            probs = _blend(probs, learned, weight=self.config.blend_weight)

        return EloPrediction(
            prob_home=probs[0],
            prob_draw=probs[1],
            prob_away=probs[2],
            pre_match_home_rating=base_prediction.pre_match_home_rating,
            pre_match_away_rating=base_prediction.pre_match_away_rating,
            home_advantage_elo=base_prediction.home_advantage_elo,
        )

    def predict_scoreline(self, match_row: pd.Series):
        return self.base_model.predict_scoreline(match_row)

    def _fresh_base_model(self) -> EloModel:
        return EloModel(
            **recalibrated_elo_kwargs(),
            generated_at_utc=self.generated_at_utc,
            host_advantage_fn=self.host_advantage_fn,
        )


def _completed_matches(matches_df: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "home_team_id", "away_team_id", "home_score", "away_score"}
    missing = required - set(matches_df.columns)
    if missing:
        raise ValueError(f"train_matches_df missing required columns: {sorted(missing)}")

    matches = matches_df.copy()
    matches["date"] = pd.to_datetime(matches["date"])
    matches = matches.dropna(subset=["date", "home_score", "away_score"])
    sort_columns = [column for column in ("date", "occurrence_index", "match_id") if column in matches.columns]
    return matches.sort_values(sort_columns).reset_index(drop=True)


def _feature_vector(match_row: pd.Series, prediction: EloPrediction) -> list[float]:
    probs = _normalize([prediction.prob_home, prediction.prob_draw, prediction.prob_away])
    home, draw, away = probs
    adjusted_rating_diff = (
        prediction.pre_match_home_rating
        + prediction.home_advantage_elo
        - prediction.pre_match_away_rating
    )
    tournament = str(match_row.get("tournament", ""))
    return [
        home,
        draw,
        away,
        log(home / draw),
        log(away / draw),
        adjusted_rating_diff / 400.0,
        abs(adjusted_rating_diff) / 400.0,
        prediction.home_advantage_elo / 100.0,
        max(home, away),
        home - away,
        draw - max(home, away),
        1.0 if bool(match_row.get("neutral", False)) else 0.0,
        1.0 if tournament == "FIFA World Cup" else 0.0,
        1.0 if "qualification" in tournament.lower() else 0.0,
        1.0 if tournament == "Friendly" else 0.0,
    ]


def _outcome_label(match_row: pd.Series) -> int:
    home_score = int(match_row["home_score"])
    away_score = int(match_row["away_score"])
    if home_score > away_score:
        return 0
    if away_score > home_score:
        return 2
    return 1


def _blend(base: Iterable[float], learned: Iterable[float], *, weight: float) -> list[float]:
    weight = max(0.0, min(1.0, float(weight)))
    return _normalize([
        (1.0 - weight) * base_prob + weight * learned_prob
        for base_prob, learned_prob in zip(base, learned, strict=True)
    ])


def _normalize(probs: Iterable[float]) -> list[float]:
    cleaned = [max(1e-6, float(value)) for value in probs]
    total = sum(cleaned)
    home = cleaned[0] / total
    draw = cleaned[1] / total
    away = max(0.0, 1.0 - home - draw)
    return [home, draw, away]


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return MLEloCorrectionModel(
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
