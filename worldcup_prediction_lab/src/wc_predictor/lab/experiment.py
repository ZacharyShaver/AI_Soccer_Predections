"""Generate immutable per-variant predictions for upcoming fixtures.

One file per (as_of, variant): runs/experiments/date=<as_of>/<variant_id>.jsonl.
Predictions reuse the live-forecast fixture split + match-row builder so every
variant forecasts exactly the same upcoming matches under the same as-of rules.
Writes are idempotent (byte-identical re-write is a no-op; a conflicting row
for the same prediction_id raises, preserving immutability).
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.lab import registry
from wc_predictor.models.base import MatchPrediction, canonical_json


def _write_immutable(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [canonical_json(row) for row in rows]
    if path.exists():
        existing = [
            line.rstrip("\n")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if existing == serialized:
            return
        # Allow extending only if the existing rows are a prefix; otherwise the
        # variant's prior predictions for this as_of would change -> refuse.
        if existing != serialized[: len(existing)]:
            raise ValueError(
                f"conflicting immutable predictions at {path} "
                "(a prior row changed; predictions are not labels)"
            )
    path.write_text("\n".join(serialized) + "\n", encoding="utf-8")


def generate_variant_predictions(
    variant_id: str,
    *,
    matches_df: pd.DataFrame,
    fixtures_df: pd.DataFrame,
    teams_df: pd.DataFrame,
    as_of: str,
    training_cutoff: str,
    out_root: str | Path = settings.EXPERIMENTS_DIR,
    generated_at_utc: str | None = None,
) -> Path:
    """Fit ``variant_id`` through ``training_cutoff`` and forecast fixtures after ``as_of``."""

    # Imported here to reuse the exact live-forecast logic without a heavy import
    # at module load.
    from wc_predictor.forecast_live import (
        _fixture_match_row,
        _team_names,
        _training_matches,
        split_live_fixtures,
    )

    gen = generated_at_utc or f"{as_of}T00:00:00Z"
    model = registry.build(variant_id, generated_at_utc=gen)
    model.fit(_training_matches(matches_df, training_cutoff=training_cutoff))

    split = split_live_fixtures(fixtures_df, as_of=as_of)
    team_names = _team_names(teams_df)

    rows: list[dict] = []
    for _, fixture in split.forecast_fixtures.iterrows():
        match_row = _fixture_match_row(fixture, team_names)
        outcome = model.predict_match(match_row)
        scoreline = model.predict_scoreline(match_row)
        prediction = MatchPrediction(
            prediction_id=f"{variant_id}:{fixture['fixture_id']}:as_of={as_of}",
            match_id=str(fixture["fixture_id"]),
            model_id=variant_id,
            model_version=str(getattr(model, "model_version", "v1")),
            generated_at_utc=gen,
            training_cutoff=training_cutoff,
            as_of=as_of,
            prob_home=float(outcome.prob_home),
            prob_draw=float(outcome.prob_draw),
            prob_away=float(outcome.prob_away),
            scoreline_distribution=scoreline,
        )
        rows.append(asdict(prediction))

    out_path = Path(out_root) / f"date={as_of}" / f"{variant_id}.jsonl"
    _write_immutable(rows, out_path)
    return out_path


def read_variant_predictions(path: str | Path) -> list[dict]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
