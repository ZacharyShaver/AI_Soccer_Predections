"""Accuracy-first pick-tuned recalibrated Elo.

This is intentionally labeled mad science: it optimizes the argmax pick layer
rather than pretending to discover a clean football feature. The underlying
ratings are still ``elo_recalibrated``. A small set of static knobs then nudges
probabilities just enough to make a different top pick when the tuned rule says
that improves historical pick accuracy.
"""

from __future__ import annotations

from wc_predictor.lab.variants.group_incentive import GroupIncentiveElo, TeamContext
from wc_predictor.models.elo import EloModel, EloPrediction


VARIANT_ID = "accuracy_pick_tuned"
DESCRIPTION = "Accuracy-first pick layer on top of recalibrated Elo."
FEATURE_IDEA = (
    "Static pick-tuning knobs: small H/D/A offsets, high-draw close-match override, "
    "and already-safe favorite override toward the other side."
)

HOME_OFFSET = 0.03
DRAW_OFFSET = -0.04
AWAY_OFFSET = -0.04
DRAW_PICK_MIN = 0.30
DRAW_PICK_MARGIN = 0.11
SAFE_FAVORITE_MAX = 0.45


class AccuracyPickTunedElo(GroupIncentiveElo):
    """Recalibrated Elo with a static accuracy-first pick override layer."""

    model_version = "accuracy_pick_tuned_v1"

    def predict_match(self, match_row):
        prediction = EloModel.predict_match(self, match_row)
        probs = _normalize([
            prediction.prob_home + HOME_OFFSET,
            prediction.prob_draw + DRAW_OFFSET,
            prediction.prob_away + AWAY_OFFSET,
        ])

        forced = self._forced_pick(match_row, probs)
        if forced is not None:
            probs = _force_pick(probs, forced=forced)

        return EloPrediction(
            prob_home=probs[0],
            prob_draw=probs[1],
            prob_away=probs[2],
            pre_match_home_rating=prediction.pre_match_home_rating,
            pre_match_away_rating=prediction.pre_match_away_rating,
            home_advantage_elo=prediction.home_advantage_elo,
        )

    def _forced_pick(self, match_row, probs: list[float]) -> int | None:
        forced: int | None = None

        favorite_side = 0 if probs[0] >= probs[2] else 2
        underdog_side = 2 if favorite_side == 0 else 0
        favorite_ctx = self._team_context(match_row, favorite_side)
        if favorite_ctx.already_safe and probs[favorite_side] <= SAFE_FAVORITE_MAX:
            forced = underdog_side

        favorite_prob = max(probs[0], probs[2])
        if probs[1] >= DRAW_PICK_MIN and favorite_prob - probs[1] <= DRAW_PICK_MARGIN:
            forced = 1

        return forced

    def _team_context(self, match_row, side: int) -> TeamContext:
        meta = self._fixture_meta(match_row)
        if not meta or str(meta.get("stage", "")).lower() != "group":
            return TeamContext()
        table = self._group_tables.get(str(meta.get("group", "")))
        if not table:
            return TeamContext()
        team_key = "home_team_id" if side == 0 else "away_team_id"
        return table.get(str(match_row.get(team_key)), TeamContext())


def _force_pick(probs: list[float], *, forced: int) -> list[float]:
    """Minimally nudge ``forced`` just above the current top probability."""

    normalized = _normalize(probs)
    if forced < 0 or forced > 2:
        raise ValueError("forced pick index must be 0, 1, or 2")
    if normalized.index(max(normalized)) == forced:
        return normalized

    needed = max(normalized) + 0.001 - normalized[forced]
    donors = [idx for idx in range(3) if idx != forced]
    donor_mass = sum(normalized[idx] for idx in donors)
    if needed <= 0.0 or donor_mass <= needed:
        return normalized

    adjusted = list(normalized)
    scale = (donor_mass - needed) / donor_mass
    for idx in donors:
        adjusted[idx] *= scale
    adjusted[forced] += needed
    return _normalize(adjusted)


def _normalize(probs: list[float]) -> list[float]:
    cleaned = [max(0.001, float(value)) for value in probs]
    total = sum(cleaned)
    home = cleaned[0] / total
    draw = cleaned[1] / total
    away = max(0.0, 1.0 - home - draw)
    return [home, draw, away]


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn, load_silver_data
    from wc_predictor.lab.variants.elo_recalibrated import recalibrated_elo_kwargs

    _matches, fixtures, _teams = load_silver_data()
    return AccuracyPickTunedElo(
        **recalibrated_elo_kwargs(),
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
        fixture_schedule_df=fixtures,
    )
