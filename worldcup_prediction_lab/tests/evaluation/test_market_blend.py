"""Unit tests for the market_blend evaluator (synthetic frames, no parquet)."""

from __future__ import annotations

import pandas as pd

from wc_predictor.evaluation.elo_vs_market import score_predictions
from wc_predictor.evaluation.market_blend import (
    LAMBDA_GRID,
    evaluate_blend,
    format_report,
)


def _scored_frame():
    # Market is deliberately sharper/closer-to-truth than Elo on every row so the
    # market should win and the optimal linear blend should land at lambda=1.
    rows = []
    truths = ["home", "away", "draw", "home", "away", "home"]
    for i, outcome in enumerate(truths):
        home_score, away_score = {"home": (2, 0), "away": (0, 2), "draw": (1, 1)}[outcome]
        if outcome == "home":
            market = (0.75, 0.18, 0.07)
        elif outcome == "away":
            market = (0.10, 0.20, 0.70)
        else:
            market = (0.30, 0.42, 0.28)
        rows.append(
            {
                "match_id": f"m{i}",
                "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i),
                "home_score": home_score,
                "away_score": away_score,
                "market_prob_home": market[0],
                "market_prob_draw": market[1],
                "market_prob_away": market[2],
                # Elo is a flatter, less accurate distribution.
                "elo_prob_home": 0.40,
                "elo_prob_draw": 0.30,
                "elo_prob_away": 0.30,
            }
        )
    return score_predictions(pd.DataFrame(rows))


def test_lambda_grid_endpoints_match_parents():
    scored = _scored_frame()
    result = evaluate_blend(scored)
    lambdas = [row.lam for row in result.rows]
    assert lambdas == LAMBDA_GRID
    by_lam = {row.lam: row.rps for row in result.rows}
    # lambda=0 is pure Elo, lambda=1 is pure market.
    assert by_lam[0.0] == result.elo_rps
    assert by_lam[1.0] == result.market_rps


def test_sharper_market_wins_and_blend_picks_lambda_one():
    scored = _scored_frame()
    result = evaluate_blend(scored)
    assert result.market_rps < result.elo_rps  # market better (lower RPS)
    assert result.market_minus_elo.point > 0.0  # elo_rps - market_rps > 0
    assert result.best_lambda == 1.0
    assert result.best_rps == result.market_rps


def test_report_contains_headline_and_sweep_table():
    scored = _scored_frame()
    result = evaluate_blend(scored)
    report = format_report(result)
    assert "# Market route: Elo vs market vs blend" in report
    assert "## Lambda sweep" in report
    assert "## Verdict" in report
    assert f"lambda = {result.best_lambda:.2f}" in report
