"""Post-cutoff eval universe drawn from the market964 aligned frame.

The cutoff exists because local models know historical results parametrically;
only matches after the model's training cutoff are a fair test.
"""

from __future__ import annotations

import pandas as pd

CUTOFF_DEFAULT = "2025-01-01"


def _outcome(row: pd.Series) -> str:
    if row["home_score"] > row["away_score"]:
        return "home"
    if row["home_score"] < row["away_score"]:
        return "away"
    return "draw"


def load_universe(cutoff: str = CUTOFF_DEFAULT, frame: pd.DataFrame | None = None) -> pd.DataFrame:
    if frame is None:
        from wc_predictor.lab.eval_harness import build_market964_frame

        frame = build_market964_frame()
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out[out["date"] >= pd.Timestamp(cutoff)].sort_values("date").reset_index(drop=True)
    out["outcome"] = out.apply(_outcome, axis=1)
    return out
