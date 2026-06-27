"""Pure probability-combination recipes for model fusion experiments."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

ProbTriple = tuple[float, float, float]


def linear_opinion_pool(
    probabilities: Sequence[Sequence[float]],
    *,
    weights: Sequence[float] | None = None,
) -> ProbTriple:
    """Weighted arithmetic mean of H/D/A probability triples."""

    triples = _validated_probabilities(probabilities, allow_zero=True)
    normalized_weights = _normalized_weights(weights, len(triples))
    pooled = [
        sum(weight * triple[outcome] for weight, triple in zip(normalized_weights, triples))
        for outcome in range(3)
    ]
    return _normalize_triple(pooled)


def logarithmic_opinion_pool(
    probabilities: Sequence[Sequence[float]],
    *,
    weights: Sequence[float] | None = None,
    floor: float = 1e-12,
) -> ProbTriple:
    """Weighted normalized geometric mean of H/D/A probability triples."""

    triples = _validated_probabilities(probabilities, allow_zero=floor > 0.0)
    if floor < 0.0:
        raise ValueError("floor must be non-negative")
    normalized_weights = _normalized_weights(weights, len(triples))

    pooled: list[float] = []
    for outcome in range(3):
        log_mass = 0.0
        for weight, triple in zip(normalized_weights, triples):
            probability = max(triple[outcome], floor)
            if probability <= 0.0:
                raise ValueError("logarithmic opinion pool requires strictly positive probabilities")
            log_mass += weight * math.log(probability)
        pooled.append(math.exp(log_mass))
    return _normalize_triple(pooled)


def inverse_rps_weights(scores: Mapping[str, float]) -> dict[str, float]:
    """Weight variants by inverse RPS; lower RPS receives more mass."""

    if not scores:
        raise ValueError("at least one score is required")
    raw = {name: 1.0 / _positive_score(score, name) for name, score in scores.items()}
    return _normalize_mapping(raw)


def softmax_rps_weights(scores: Mapping[str, float], *, temperature: float = 0.01) -> dict[str, float]:
    """Softmax over negative RPS; lower RPS receives more mass."""

    if not scores:
        raise ValueError("at least one score is required")
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")

    best = min(scores.values())
    raw = {
        name: math.exp(-(_positive_score(score, name) - best) / temperature)
        for name, score in scores.items()
    }
    return _normalize_mapping(raw)


def select_top_k(scores: Mapping[str, float], *, k: int) -> list[str]:
    """Return the k lowest-RPS variant ids, stable by name for ties."""

    if k <= 0:
        raise ValueError("k must be positive")
    ranked = _ranked_names(scores)
    if k > len(ranked):
        raise ValueError("k cannot exceed the number of variants")
    return ranked[:k]


def select_rank_and_trim(scores: Mapping[str, float], *, trim_worst: int) -> list[str]:
    """Return all variants except the highest-RPS tail."""

    if trim_worst < 0:
        raise ValueError("trim_worst must be non-negative")
    ranked = _ranked_names(scores)
    keep_count = len(ranked) - trim_worst
    if keep_count <= 0:
        raise ValueError("trim_worst would remove every variant")
    return ranked[:keep_count]


def weight_vector_for_variants(
    scores: Mapping[str, float],
    variant_ids: Sequence[str],
    *,
    scheme: str,
    temperature: float = 0.01,
) -> list[float]:
    """Build opinion-pool weights in the same order as ``variant_ids``."""

    if not variant_ids:
        raise ValueError("at least one variant id is required")
    missing = [variant_id for variant_id in variant_ids if variant_id not in scores]
    if missing:
        raise ValueError(f"missing scores for variants: {', '.join(missing)}")

    selected_scores = {variant_id: scores[variant_id] for variant_id in variant_ids}
    if scheme == "uniform":
        weights = {variant_id: 1.0 / len(variant_ids) for variant_id in variant_ids}
    elif scheme == "inverse_rps":
        weights = inverse_rps_weights(selected_scores)
    elif scheme == "softmax_rps":
        weights = softmax_rps_weights(selected_scores, temperature=temperature)
    else:
        raise ValueError(f"unknown weight scheme: {scheme}")
    return [weights[variant_id] for variant_id in variant_ids]


def _validated_probabilities(
    probabilities: Sequence[Sequence[float]],
    *,
    allow_zero: bool,
) -> list[ProbTriple]:
    if not probabilities:
        raise ValueError("at least one probability triple is required")

    triples: list[ProbTriple] = []
    for index, values in enumerate(probabilities):
        if len(values) != 3:
            raise ValueError(f"probability set {index} must contain three probabilities")
        triple = tuple(float(value) for value in values)
        if any(not math.isfinite(value) for value in triple):
            raise ValueError(f"probability set {index} contains a non-finite value")
        if any(value < 0.0 for value in triple):
            raise ValueError(f"probability set {index} contains a negative probability")
        if not allow_zero and any(value <= 0.0 for value in triple):
            raise ValueError("logarithmic opinion pool requires strictly positive probabilities")
        if sum(triple) <= 0.0:
            raise ValueError(f"probability set {index} must have positive total mass")
        triples.append(_normalize_triple(triple))
    return triples


def _normalized_weights(weights: Sequence[float] | None, count: int) -> list[float]:
    if weights is None:
        return [1.0 / count] * count
    if len(weights) != count:
        raise ValueError("weights and probabilities must have the same length")
    normalized = [float(weight) for weight in weights]
    if any(not math.isfinite(weight) for weight in normalized):
        raise ValueError("weights must be finite")
    if any(weight < 0.0 for weight in normalized):
        raise ValueError("weights must be non-negative")
    total = sum(normalized)
    if total <= 0.0:
        raise ValueError("weights must have positive total mass")
    return [weight / total for weight in normalized]


def _normalize_triple(values: Iterable[float]) -> ProbTriple:
    triple = tuple(float(value) for value in values)
    total = sum(triple)
    if total <= 0.0:
        raise ValueError("probabilities must have positive total mass")
    return (triple[0] / total, triple[1] / total, triple[2] / total)


def _positive_score(score: float, name: str) -> float:
    value = float(score)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"score for {name!r} must be a positive finite number")
    return value


def _normalize_mapping(values: Mapping[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0.0:
        raise ValueError("weights must have positive total mass")
    return {name: value / total for name, value in values.items()}


def _ranked_names(scores: Mapping[str, float]) -> list[str]:
    if not scores:
        raise ValueError("at least one score is required")
    for name, score in scores.items():
        _positive_score(score, name)
    return [name for name, _score in sorted(scores.items(), key=lambda item: (item[1], item[0]))]
