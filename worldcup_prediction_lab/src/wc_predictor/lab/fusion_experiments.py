"""Fusion experiment helpers that produce ledger-ready result objects."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pandas as pd

from wc_predictor.evaluation.elo_vs_market import align_matches_with_market
from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score
from wc_predictor.lab import eval_harness, fusion_ledger, fusion_recipes

OUTCOMES = ("home", "draw", "away")
PredictFn = Callable[[pd.Series], fusion_recipes.ProbTriple]


def build_fused_predict_fn(
    *,
    variant_ids: Sequence[str],
    weights: Sequence[float],
    recipe: str,
) -> PredictFn:
    """Return a predict_fn for eval_harness from ``<variant>_prob_*`` columns."""

    if recipe not in {"linear", "log"}:
        raise ValueError(f"unknown fusion recipe: {recipe}")

    def predict(row: pd.Series) -> fusion_recipes.ProbTriple:
        missing = [
            column
            for variant_id in variant_ids
            for column in _probability_columns(variant_id)
            if column not in row
        ]
        if missing:
            raise ValueError(f"missing probability columns: {', '.join(missing)}")

        probabilities = [
            tuple(float(row[column]) for column in _probability_columns(variant_id))
            for variant_id in variant_ids
        ]
        if recipe == "linear":
            return fusion_recipes.linear_opinion_pool(probabilities, weights=weights)
        return fusion_recipes.logarithmic_opinion_pool(probabilities, weights=weights)

    return predict


def build_market_fusion_frame(
    matches: pd.DataFrame,
    market_odds: pd.DataFrame,
    *,
    variant_ids: Sequence[str],
    generated_at_utc: str,
    build_variant: Callable[..., object] | None = None,
    max_rows: int | None = None,
) -> tuple[pd.DataFrame, object]:
    """Align matches to market odds and attach requested variant probabilities."""

    aligned, alignment = align_matches_with_market(matches, market_odds)
    if max_rows is not None:
        if max_rows <= 0:
            raise ValueError("max_rows must be positive")
        aligned = aligned.head(max_rows).copy()
    frame = attach_variant_probability_columns(
        aligned,
        matches,
        variant_ids=variant_ids,
        generated_at_utc=generated_at_utc,
        build_variant=build_variant,
    )
    return frame, alignment


def add_model_probability_columns(
    aligned: pd.DataFrame,
    matches: pd.DataFrame,
    *,
    model_factory: Callable[[], object],
    prefix: str,
) -> pd.DataFrame:
    """Attach leak-free ``<prefix>_prob_*`` columns for an online model."""

    evaluation = _normalize_dates(aligned)
    train_matches = _completed_matches(_normalize_dates(matches))
    train_matches = train_matches.sort_values(
        _sort_columns(train_matches), kind="mergesort"
    ).reset_index(drop=True)
    evaluation = evaluation.sort_values(
        _sort_columns(evaluation, fallback=("date",)), kind="mergesort"
    ).reset_index(drop=True)

    model = model_factory()
    train_index = 0
    predictions: list[dict[str, float]] = []
    for match_date, date_matches in evaluation.groupby("date", sort=True):
        while (
            train_index < len(train_matches)
            and train_matches.iloc[train_index]["date"] < match_date
        ):
            model._update_from_match(train_matches.iloc[train_index])
            train_index += 1

        for _, row in date_matches.iterrows():
            prediction = model.predict_match(row)
            predictions.append(
                {
                    f"{prefix}_prob_home": prediction.prob_home,
                    f"{prefix}_prob_draw": prediction.prob_draw,
                    f"{prefix}_prob_away": prediction.prob_away,
                    f"{prefix}_home_rating": prediction.pre_match_home_rating,
                    f"{prefix}_away_rating": prediction.pre_match_away_rating,
                    f"{prefix}_home_advantage": prediction.home_advantage_elo,
                }
            )

    return pd.concat([evaluation, pd.DataFrame(predictions)], axis=1)


def add_walkforward_model_probability_columns(
    aligned: pd.DataFrame,
    matches: pd.DataFrame,
    *,
    build_model_fn: Callable[..., object],
    prefix: str,
    generated_at_utc: str,
) -> pd.DataFrame:
    """Attach probabilities by fitting a fresh model before each match date.

    This is slower than ``add_model_probability_columns`` but works for lab
    variants whose features are derived in ``fit()`` rather than incremental
    ``_update_from_match`` calls.
    """

    evaluation = _normalize_dates(aligned)
    train_matches = _completed_matches(_normalize_dates(matches))
    train_matches = train_matches.sort_values(
        _sort_columns(train_matches), kind="mergesort"
    ).reset_index(drop=True)
    evaluation = evaluation.sort_values(
        _sort_columns(evaluation, fallback=("date",)), kind="mergesort"
    ).reset_index(drop=True)

    predictions: list[dict[str, float]] = []
    for match_date, date_matches in evaluation.groupby("date", sort=True):
        training_slice = train_matches.loc[train_matches["date"] < match_date]
        model = build_model_fn(generated_at_utc=generated_at_utc)
        model.fit(training_slice)

        for _, row in date_matches.iterrows():
            prediction = model.predict_match(row)
            predictions.append(
                {
                    f"{prefix}_prob_home": prediction.prob_home,
                    f"{prefix}_prob_draw": prediction.prob_draw,
                    f"{prefix}_prob_away": prediction.prob_away,
                    f"{prefix}_home_rating": prediction.pre_match_home_rating,
                    f"{prefix}_away_rating": prediction.pre_match_away_rating,
                    f"{prefix}_home_advantage": prediction.home_advantage_elo,
                }
            )

    return pd.concat([evaluation, pd.DataFrame(predictions)], axis=1)


def attach_variant_probability_columns(
    aligned: pd.DataFrame,
    matches: pd.DataFrame,
    *,
    variant_ids: Sequence[str],
    generated_at_utc: str,
    build_variant: Callable[..., object] | None = None,
) -> pd.DataFrame:
    """Attach fit-based walk-forward probability columns for each variant id."""

    if build_variant is None:
        from wc_predictor.lab import registry

        build_variant = registry.build

    frame = aligned.copy()
    for variant_id in variant_ids:
        frame = add_walkforward_model_probability_columns(
            frame,
            matches,
            build_model_fn=lambda **kw: build_variant(variant_id, **kw),
            prefix=variant_id,
            generated_at_utc=generated_at_utc,
        )
    return frame


def build_market_fusion_result(
    *,
    frame: pd.DataFrame,
    variant_scores: Mapping[str, float],
    variant_ids: Sequence[str],
    recipe: str,
    weight_scheme: str,
    exp_id: str,
    created_utc: str,
    notes: str = "",
    temperature: float = 0.01,
) -> dict:
    """Score one Fusion 1/2 market-frame recipe and return a ledger payload."""

    weights = fusion_recipes.weight_vector_for_variants(
        variant_scores,
        variant_ids,
        scheme=weight_scheme,
        temperature=temperature,
    )
    predict_fn = build_fused_predict_fn(
        variant_ids=variant_ids,
        weights=weights,
        recipe=recipe,
    )
    scored = eval_harness.score_on_market964(predict_fn, frame=frame)
    vs_best = _paired_vs_best_constituent(
        frame=frame,
        predict_fn=predict_fn,
        variant_scores=variant_scores,
        variant_ids=variant_ids,
    )
    sample = {
        key: scored[key]
        for key in ("n", "rps", "log_loss", "brier")
        if key in scored
    }
    return {
        "exp_id": exp_id,
        "agent": "codex",
        "task": "fuse",
        "created_utc": created_utc,
        "config": {
            "recipe": recipe,
            "sample": "market964",
            "variant_ids": list(variant_ids),
            "weight_scheme": weight_scheme,
            "weights": {
                variant_id: weight
                for variant_id, weight in zip(variant_ids, weights)
            },
            "temperature": temperature if weight_scheme == "softmax_rps" else None,
        },
        "samples": {"market964": sample},
        "vs_market_paired": scored["vs_market_paired"],
        "vs_best_constituent_paired": vs_best,
        "notes": notes,
        "promote": False,
    }


def iter_market_fusion_specs(
    *,
    variant_scores: Mapping[str, float],
    k_values: Sequence[int],
    recipes: Sequence[str],
    weight_schemes: Sequence[str],
) -> list[dict]:
    """Enumerate deterministic Fusion 1/2 market experiment specs."""

    specs: list[dict] = []
    for k in k_values:
        variant_ids = fusion_recipes.select_top_k(variant_scores, k=k)
        for recipe in recipes:
            if recipe not in {"linear", "log"}:
                raise ValueError(f"unknown fusion recipe: {recipe}")
            for weight_scheme in weight_schemes:
                if weight_scheme not in {"uniform", "inverse_rps", "softmax_rps"}:
                    raise ValueError(f"unknown weight scheme: {weight_scheme}")
                specs.append(
                    {
                        "exp_id": (
                            f"fusion-{recipe}-top{k}-"
                            f"{weight_scheme.replace('_', '-')}"
                        ),
                        "recipe": recipe,
                        "weight_scheme": weight_scheme,
                        "variant_ids": variant_ids,
                    }
                )
    return specs


def run_market_fusion_sweep(
    *,
    frame: pd.DataFrame,
    variant_scores: Mapping[str, float],
    specs: Sequence[Mapping[str, object]],
    created_utc: str,
    fusion_dir: Path | None = None,
    record_results: bool = False,
) -> list[dict]:
    """Run a list of Fusion 1/2 specs against a prepared market frame."""

    results: list[dict] = []
    for spec in specs:
        result = build_market_fusion_result(
            frame=frame,
            variant_scores=variant_scores,
            variant_ids=list(spec["variant_ids"]),
            recipe=str(spec["recipe"]),
            weight_scheme=str(spec["weight_scheme"]),
            exp_id=str(spec["exp_id"]),
            created_utc=created_utc,
            notes=str(spec.get("notes", "")),
        )
        results.append(result)
        if record_results:
            fusion_ledger.record(result, fusion_dir=fusion_dir)
    return results


def _probability_columns(variant_id: str) -> tuple[str, str, str]:
    return tuple(f"{variant_id}_prob_{outcome}" for outcome in OUTCOMES)


def _paired_vs_best_constituent(
    *,
    frame: pd.DataFrame,
    predict_fn: PredictFn,
    variant_scores: Mapping[str, float],
    variant_ids: Sequence[str],
) -> dict:
    best_variant_id = min(variant_ids, key=lambda variant_id: variant_scores[variant_id])
    diffs: list[float] = []
    for _, row in frame.iterrows():
        actual = _actual_outcome(row)
        fusion_rps = ranked_probability_score(predict_fn(row), actual)
        best_rps = ranked_probability_score(
            tuple(float(row[column]) for column in _probability_columns(best_variant_id)),
            actual,
        )
        diffs.append(fusion_rps - best_rps)
    point, low, high, _n = bootstrap_ci(
        diffs,
        n_boot=eval_harness.BOOTSTRAP_N,
        alpha=0.05,
        seed=eval_harness.BOOTSTRAP_SEED,
    )
    return {
        "best_variant_id": best_variant_id,
        "mean_diff": point,
        "ci95": [low, high],
        "excludes_0": (low > 0.0) or (high < 0.0),
        "beats_best": high < 0.0,
        "sign": "fusion_minus_best_constituent_rps",
    }


def _actual_outcome(row: pd.Series) -> str:
    if int(row["home_score"]) > int(row["away_score"]):
        return "home"
    if int(row["home_score"]) == int(row["away_score"]):
        return "draw"
    return "away"


def _normalize_dates(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.normalize()
    return normalized


def _completed_matches(matches: pd.DataFrame) -> pd.DataFrame:
    mask = (
        matches["home_team_id"].notna()
        & matches["away_team_id"].notna()
        & matches["home_score"].notna()
        & matches["away_score"].notna()
    )
    return matches.loc[mask].copy()


def _sort_columns(
    dataframe: pd.DataFrame,
    *,
    fallback: Sequence[str] = ("date", "occurrence_index", "match_id"),
) -> list[str]:
    return [column for column in fallback if column in dataframe.columns]
