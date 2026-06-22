"""Elo variant that only trains on a trailing time window.

Used by the P5 recency experiment to test the "ship of Theseus" hypothesis:
discard matches older than ``window_years`` before fitting, so ratings reflect
only recent history. Everything else (update rule, predictions, host/neutral
logic) is inherited from ``EloModel``.
"""

from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel


class WindowedEloModel(EloModel):
    def __init__(self, *, window_years: float, **kwargs) -> None:
        super().__init__(**kwargs)
        if window_years <= 0.0:
            raise ValueError("window_years must be positive")
        self.window_years = float(window_years)
        self.model_id = f"elo_window_{self._window_label()}"

    def _window_label(self) -> str:
        if self.window_years == int(self.window_years):
            return f"{int(self.window_years)}y"
        return f"{self.window_years}y"

    def fit(self, train_matches_df: "pd.DataFrame") -> "WindowedEloModel":
        if not train_matches_df.empty and "date" in train_matches_df.columns:
            dates = pd.to_datetime(train_matches_df["date"])
            cutoff = dates.max() - pd.DateOffset(years=int(self.window_years))
            # fractional years -> add the remaining days
            frac = self.window_years - int(self.window_years)
            if frac:
                cutoff = cutoff - pd.Timedelta(days=round(frac * 365.25))
            train_matches_df = train_matches_df[dates >= cutoff]
        super().fit(train_matches_df)
        return self
