"""Market route: how much does the de-vigged market improve on Elo, and can a
blend beat the market itself?

Builds directly on :mod:`wc_predictor.evaluation.elo_vs_market`: it reuses the
same leak-free alignment (martj42 results joined to Football-Data odds) and
per-match Elo/market scoring, then evaluates the linear opinion pool

    blend = lambda * market + (1 - lambda) * elo        (renormalized)

over a grid of ``lambda``. For each candidate we report RPS and a paired
bootstrap CI of the per-match RPS difference against BOTH parents (Elo and the
market). The project's accepted significance bar is "paired CI excludes 0".

Empirical finding on the current sample (n~174, 2014-2026): the market beats
Elo by a wide, significant margin and the optimal linear blend is ``lambda=1``
(pure market) -- mixing Elo back in only hurts, and richer combiners
(log-linear pooling, draw nudges) do not beat the market either. So the market
route's value is "use the de-vigged market where it exists; fall back to the
recalibrated Elo where it does not", not a static Elo/market mixture.

The Elo base defaults to the tuned ``elo_recalibrated`` configuration so the
comparison is against our strongest pure-ratings model, not the raw baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.elo_vs_market import (
    MARKET_ODDS_FILE,
    MATCHES_FILE,
    MIN_USABLE_SAMPLE,
    _read_parquet,
    add_elo_predictions,
    align_matches_with_market,
    score_predictions,
)
from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score
from wc_predictor.models.elo import EloModel

BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 20260626
LAMBDA_GRID = [round(0.05 * i, 2) for i in range(21)]  # 0.00 .. 1.00 step 0.05

# Tuned Elo (matches the elo_recalibrated lab variant): faster K, recalibrated
# draw mass, flat tournament weights. No host fn -- these are historical games.
_FLAT_TOURNAMENT_WEIGHTS = {
    "Friendly": 1.0,
    "FIFA World Cup": 1.0,
    "FIFA World Cup qualification": 1.0,
    "UEFA Euro": 1.0,
    "Copa America": 1.0,
    "CONCACAF Championship": 1.0,
    "CONCACAF Nations League": 1.0,
    "UEFA Nations League": 1.0,
    "African Cup of Nations": 1.0,
    "AFC Asian Cup": 1.0,
}


def recalibrated_elo() -> EloModel:
    return EloModel(
        k_factor=30.0,
        home_advantage=75.0,
        draw_base_probability=0.33,
        draw_rating_scale=600.0,
        tournament_weights=_FLAT_TOURNAMENT_WEIGHTS,
        default_tournament_weight=1.0,
    )


@dataclass(frozen=True)
class BlendInterval:
    point: float
    low: float
    high: float
    n: int


@dataclass(frozen=True)
class LambdaRow:
    lam: float
    rps: float
    diff_vs_elo: BlendInterval  # elo_rps - blend_rps (positive => blend better)
    diff_vs_market: BlendInterval  # market_rps - blend_rps (positive => blend better)


@dataclass(frozen=True)
class MarketBlendResult:
    n: int
    date_min: str
    date_max: str
    elo_rps: float
    market_rps: float
    market_minus_elo: BlendInterval  # elo_rps - market_rps (positive => market better)
    rows: list[LambdaRow]
    best_lambda: float
    best_rps: float
    verdict: str
    report_path: Path


def _outcome(row: pd.Series) -> str:
    home, away = int(row["home_score"]), int(row["away_score"])
    return "home" if home > away else ("away" if away > home else "draw")


def _probs(row: pd.Series, prefix: str) -> list[float]:
    raw = [
        float(row[f"{prefix}_prob_home"]),
        float(row[f"{prefix}_prob_draw"]),
        float(row[f"{prefix}_prob_away"]),
    ]
    total = sum(raw) or 1.0
    return [value / total for value in raw]


def _blend_rps_series(scored: pd.DataFrame, lam: float) -> list[float]:
    series: list[float] = []
    for _, row in scored.iterrows():
        market = _probs(row, "market")
        elo = _probs(row, "elo")
        blended = [lam * m + (1.0 - lam) * e for m, e in zip(market, elo)]
        total = sum(blended) or 1.0
        blended = [value / total for value in blended]
        series.append(ranked_probability_score(blended, _outcome(row)))
    return series


def _ci(diffs: list[float]) -> BlendInterval:
    point, low, high, n = bootstrap_ci(
        diffs, n_boot=BOOTSTRAP_N, alpha=0.05, seed=BOOTSTRAP_SEED
    )
    return BlendInterval(point=point, low=low, high=high, n=n)


def evaluate_blend(scored: pd.DataFrame) -> MarketBlendResult:
    n = len(scored)
    elo_rps = _blend_rps_series(scored, 0.0)
    market_rps = _blend_rps_series(scored, 1.0)
    elo_mean = sum(elo_rps) / n
    market_mean = sum(market_rps) / n

    rows: list[LambdaRow] = []
    best_lambda, best_rps = 1.0, market_mean
    for lam in LAMBDA_GRID:
        series = _blend_rps_series(scored, lam)
        mean = sum(series) / n
        diff_elo = _ci([e - b for e, b in zip(elo_rps, series)])
        diff_market = _ci([m - b for m, b in zip(market_rps, series)])
        rows.append(LambdaRow(lam=lam, rps=mean, diff_vs_elo=diff_elo, diff_vs_market=diff_market))
        if mean < best_rps - 1e-12:
            best_lambda, best_rps = lam, mean

    market_minus_elo = _ci([e - m for e, m in zip(elo_rps, market_rps)])
    dates = pd.to_datetime(scored["date"])
    verdict = _verdict(best_lambda, market_minus_elo)
    return MarketBlendResult(
        n=n,
        date_min=dates.min().strftime("%Y-%m-%d"),
        date_max=dates.max().strftime("%Y-%m-%d"),
        elo_rps=elo_mean,
        market_rps=market_mean,
        market_minus_elo=market_minus_elo,
        rows=rows,
        best_lambda=best_lambda,
        best_rps=best_rps,
        verdict=verdict,
        report_path=settings.REPORTS_DIR / "backtests" / "market_blend.md",
    )


def _verdict(best_lambda: float, market_minus_elo: BlendInterval) -> str:
    market_sig = market_minus_elo.low > 0.0
    if best_lambda >= 0.95 and market_sig:
        return (
            "The de-vigged market significantly beats the tuned Elo (paired RPS CI "
            "excludes 0) and the optimal linear blend is essentially pure market "
            "(lambda>=0.95): blending Elo back in does not help. Use the market "
            "where it exists and fall back to the recalibrated Elo where it does not."
        )
    if best_lambda <= 0.05:
        return "Elo is not improved by the market on this sample (optimal lambda~0)."
    if market_sig:
        return (
            f"The market significantly beats Elo, and a blend at lambda={best_lambda:.2f} "
            "scores best on this sample."
        )
    return (
        f"Best blend at lambda={best_lambda:.2f}; the market's edge over Elo is not "
        "significant on this sample (paired CI spans 0)."
    )


def _fmt(interval: BlendInterval) -> str:
    return f"{interval.point:+.5f} [{interval.low:+.5f}, {interval.high:+.5f}]"


def format_report(result: MarketBlendResult) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Market route: Elo vs market vs blend",
        "",
        f"Generated: `{generated}`",
        "",
        "Lower RPS is better. Blend = `lambda * market + (1 - lambda) * elo`.",
        "Elo base is the tuned `elo_recalibrated` config (K=30, draw_base 0.33,",
        "draw_scale 600, flat tournament weights). Paired CIs are bootstrap 95%",
        f"({BOOTSTRAP_N:,} resamples, seed {BOOTSTRAP_SEED}); a diff is significant",
        "when its CI excludes 0.",
        "",
        "## Sample",
        "",
        f"- Usable joined result/market rows: {result.n:,}",
        f"- Date range: {result.date_min} to {result.date_max}",
        "",
        "## Headline",
        "",
        f"- Tuned Elo RPS: **{result.elo_rps:.4f}**",
        f"- Market RPS: **{result.market_rps:.4f}**",
        f"- Market minus Elo (positive = market better): {_fmt(result.market_minus_elo)}",
        f"- Best blend: **lambda = {result.best_lambda:.2f}**, RPS **{result.best_rps:.4f}**",
        "",
        "## Lambda sweep",
        "",
        "| lambda | blend RPS | blend - Elo [95% CI] | blend - market [95% CI] |",
        "| ---: | ---: | --- | --- |",
    ]
    for row in result.rows:
        lines.append(
            f"| {row.lam:.2f} | {row.rps:.4f} | {_fmt(row.diff_vs_elo)} | {_fmt(row.diff_vs_market)} |"
        )
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            result.verdict,
            "",
            "## Honesty caveats",
            "",
            "- Sample is only the Football-Data odds rows that resolve to canonical teams and join martj42 results; extending the alias table would change it.",
            "- The market embeds information Elo never sees (injuries, lineups, late money).",
            "- 'Use the market where it exists' only covers matches that HAVE tradeable odds; most of the ~49k history does not, so Elo remains the backbone.",
            "- Elo predictions are point-in-time by match date with all same-date results withheld (leak-free).",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    *,
    matches_path: str | Path = settings.SILVER_DIR / MATCHES_FILE,
    market_odds_path: str | Path = settings.SILVER_DIR / MARKET_ODDS_FILE,
    model_factory: Callable[[], EloModel] = recalibrated_elo,
    write: bool = True,
) -> MarketBlendResult:
    matches = _read_parquet(matches_path)
    market_odds = _read_parquet(market_odds_path)
    aligned, alignment = align_matches_with_market(matches, market_odds)
    if alignment.usable_joined_rows < MIN_USABLE_SAMPLE:
        raise RuntimeError(
            "usable joined sample is too small for a market-blend verdict: "
            f"{alignment.usable_joined_rows} < {MIN_USABLE_SAMPLE}"
        )
    evaluation = add_elo_predictions(aligned, matches, model_factory=model_factory)
    scored = score_predictions(evaluation)
    result = evaluate_blend(scored)
    if write:
        result.report_path.parent.mkdir(parents=True, exist_ok=True)
        result.report_path.write_text(format_report(result), encoding="utf-8")
    return result


def main() -> None:
    result = run()
    print(
        "[market_blend] "
        f"n={result.n} range={result.date_min}..{result.date_max} "
        f"elo_rps={result.elo_rps:.4f} market_rps={result.market_rps:.4f} "
        f"best_lambda={result.best_lambda:.2f} best_rps={result.best_rps:.4f} "
        f"market_minus_elo={result.market_minus_elo.point:+.5f}"
        f"[{result.market_minus_elo.low:+.5f},{result.market_minus_elo.high:+.5f}] "
        f"report={result.report_path}",
        flush=True,
    )
    print(f"[market_blend] verdict: {result.verdict}", flush=True)


if __name__ == "__main__":
    main()
