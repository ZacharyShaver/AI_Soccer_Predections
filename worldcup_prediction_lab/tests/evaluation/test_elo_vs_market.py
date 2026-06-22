import math

import pandas as pd
import pytest

from wc_predictor.evaluation.elo_vs_market import (
    align_matches_with_market,
    score_predictions,
    summarize_scores,
)


def test_align_matches_with_market_handles_reversed_odds_orientation():
    matches = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "date": "2026-01-01",
                "home_team_id": "AAA",
                "away_team_id": "BBB",
                "home_team": "Alpha",
                "away_team": "Beta",
                "home_score": 2,
                "away_score": 0,
                "tournament": "Friendly",
                "neutral": False,
                "occurrence_index": 0,
            },
            {
                "match_id": "m2",
                "date": "2026-01-02",
                "home_team_id": "CCC",
                "away_team_id": "DDD",
                "home_team": "Gamma",
                "away_team": "Delta",
                "home_score": 1,
                "away_score": 1,
                "tournament": "Friendly",
                "neutral": True,
                "occurrence_index": 0,
            },
        ]
    )
    odds = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "home_team_id": "AAA",
                "away_team_id": "BBB",
                "home_team_name": "Alpha FD",
                "away_team_name": "Beta FD",
                "bookmaker": "avg",
                "prob_home": 0.6,
                "prob_draw": 0.25,
                "prob_away": 0.15,
                "source_sheet": "test",
            },
            {
                "date": "2026-01-02",
                "home_team_id": "DDD",
                "away_team_id": "CCC",
                "home_team_name": "Delta FD",
                "away_team_name": "Gamma FD",
                "bookmaker": "avg",
                "prob_home": 0.5,
                "prob_draw": 0.3,
                "prob_away": 0.2,
                "source_sheet": "test",
            },
            {
                "date": "2026-01-03",
                "home_team_id": pd.NA,
                "away_team_id": "EEE",
                "home_team_name": "Unmapped",
                "away_team_name": "Mapped",
                "bookmaker": "avg",
                "prob_home": 0.4,
                "prob_draw": 0.3,
                "prob_away": 0.3,
                "source_sheet": "test",
            },
        ]
    )

    aligned, summary = align_matches_with_market(matches, odds)

    assert summary.total_odds_rows == 3
    assert summary.odds_rows_with_both_team_ids == 2
    assert summary.usable_joined_rows == 2
    assert summary.top_unmatched_footballdata_names == [("Unmapped", 1)]

    rows = {row.match_id: row for row in aligned.itertuples()}
    assert rows["m1"].market_prob_home == pytest.approx(0.6)
    assert rows["m1"].market_prob_draw == pytest.approx(0.25)
    assert rows["m1"].market_prob_away == pytest.approx(0.15)
    assert rows["m1"].market_orientation == "as_listed"

    assert rows["m2"].market_prob_home == pytest.approx(0.2)
    assert rows["m2"].market_prob_draw == pytest.approx(0.3)
    assert rows["m2"].market_prob_away == pytest.approx(0.5)
    assert rows["m2"].market_orientation == "reversed"


def test_summarize_scores_reports_paired_market_minus_elo_diffs_and_filters_inf_log_loss():
    scored = score_predictions(
        pd.DataFrame(
            [
                {
                    "match_id": "m1",
                    "home_score": 1,
                    "away_score": 0,
                    "market_prob_home": 0.0,
                    "market_prob_draw": 0.4,
                    "market_prob_away": 0.6,
                    "elo_prob_home": 0.7,
                    "elo_prob_draw": 0.2,
                    "elo_prob_away": 0.1,
                },
                {
                    "match_id": "m2",
                    "home_score": 0,
                    "away_score": 1,
                    "market_prob_home": 0.2,
                    "market_prob_draw": 0.3,
                    "market_prob_away": 0.5,
                    "elo_prob_home": 0.3,
                    "elo_prob_draw": 0.3,
                    "elo_prob_away": 0.4,
                },
            ]
        )
    )

    assert math.isinf(scored.loc[0, "market_log_loss"])

    summary = summarize_scores(scored, n_boot=20, seed=7)

    assert summary["market"]["log_loss"].n == 1
    assert summary["elo"]["log_loss"].n == 2
    assert summary["paired_diff_market_minus_elo"]["log_loss"].n == 1
    assert summary["paired_diff_market_minus_elo"]["rps"].point > 0.0
