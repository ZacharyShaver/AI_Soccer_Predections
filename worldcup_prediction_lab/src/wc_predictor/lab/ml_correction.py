"""Small dependency-light ML helpers for lab correction-layer variants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class SoftmaxCorrection:
    """Multinomial logistic correction trained with batch gradient descent.

    The lab deliberately keeps this tiny and inspectable instead of adding a
    heavyweight ML dependency for the first correction-layer experiment.
    """

    learning_rate: float = 0.05
    max_iter: int = 300
    l2: float = 0.01

    def __post_init__(self) -> None:
        if self.learning_rate <= 0.0:
            raise ValueError("learning_rate must be positive")
        if self.max_iter <= 0:
            raise ValueError("max_iter must be positive")
        if self.l2 < 0.0:
            raise ValueError("l2 must be non-negative")
        self.weights_: np.ndarray | None = None
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None

    def fit(self, rows: Iterable[Iterable[float]], labels: Iterable[int]) -> "SoftmaxCorrection":
        x = np.asarray(list(rows), dtype=float)
        y = np.asarray(list(labels), dtype=int)
        if x.ndim != 2 or x.shape[0] == 0:
            raise ValueError("rows must be a non-empty 2D feature matrix")
        if y.shape != (x.shape[0],):
            raise ValueError("labels must have one value per row")
        if np.any((y < 0) | (y > 2)):
            raise ValueError("labels must be 0=home, 1=draw, or 2=away")

        self.mean_ = x.mean(axis=0)
        self.scale_ = x.std(axis=0)
        self.scale_[self.scale_ < 1e-9] = 1.0
        x_aug = _add_bias((x - self.mean_) / self.scale_)

        targets = np.zeros((x.shape[0], 3), dtype=float)
        targets[np.arange(x.shape[0]), y] = 1.0
        weights = np.zeros((x_aug.shape[1], 3), dtype=float)

        for _ in range(self.max_iter):
            probs = _softmax(x_aug @ weights)
            gradient = (x_aug.T @ (probs - targets)) / x_aug.shape[0]
            gradient[1:] += self.l2 * weights[1:]
            weights -= self.learning_rate * gradient

        self.weights_ = weights
        return self

    def predict_proba(self, rows: Iterable[Iterable[float]]) -> list[list[float]]:
        if self.weights_ is None or self.mean_ is None or self.scale_ is None:
            raise RuntimeError("SoftmaxCorrection must be fitted before prediction")
        x = np.asarray(list(rows), dtype=float)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.ndim != 2 or x.shape[1] != self.mean_.shape[0]:
            raise ValueError("rows must have the same feature width used at fit time")
        x_aug = _add_bias((x - self.mean_) / self.scale_)
        return _softmax(x_aug @ self.weights_).tolist()


def _add_bias(x: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(x.shape[0], dtype=float), x])


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp_scores = np.exp(shifted)
    return exp_scores / exp_scores.sum(axis=1, keepdims=True)
