from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest

from wc_predictor.data.devig import no_vig_three_way
from wc_predictor.data.ingest_footballdata import parse_workbook


def _workbook_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, dataframe in sheets.items():
            dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def test_parse_workbook_maps_average_odds_to_normalized_market_odds():
    workbook = _workbook_bytes(
        {
            "WorldCup2022": pd.DataFrame(
                [
                    {
                        "Competition": "World Cup 2022",
                        "Home": "United States",
                        "Away": "Iran",
                        "Date": "2022-11-29",
                        "Time": "19:00",
                        "HG": 1,
                        "AG": 0,
                        "H-Avg": 2.0,
                        "D-Avg": 3.5,
                        "A-Avg": 4.0,
                        "bet365-H": 1.95,
                        "bet365-D": 3.4,
                        "bet365-A": 4.2,
                    }
                ]
            )
        }
    )

    market_odds = parse_workbook(workbook)

    assert list(market_odds["bookmaker"]) == ["avg"]
    assert market_odds.loc[0, "date"] == pd.Timestamp("2022-11-29")
    assert market_odds.loc[0, "home_team_id"] == "USA"
    assert market_odds.loc[0, "away_team_id"] == "IRN"
    expected = no_vig_three_way(2.0, 3.5, 4.0)
    assert (
        market_odds.loc[0, ["prob_home", "prob_draw", "prob_away"]]
        .astype(float)
        .tolist()
    ) == pytest.approx(expected)
    assert sum(market_odds.loc[0, ["prob_home", "prob_draw", "prob_away"]]) == pytest.approx(
        1.0,
        abs=1e-12,
    )


def test_parse_workbook_falls_back_to_bet365_odds_and_fifa_aliases():
    workbook = _workbook_bytes(
        {
            "WorldCup2026Qualifiers": pd.DataFrame(
                [
                    {
                        "Home": "Korea Republic",
                        "Away": "Cabo Verde",
                        "Date": "2025-09-05",
                        "Home Score": 2,
                        "Away Score": 1,
                        "bet365-H": 1.8,
                        "bet365-D": 3.6,
                        "bet365-A": 5.0,
                    }
                ]
            )
        }
    )

    market_odds = parse_workbook(workbook)

    assert list(market_odds["bookmaker"]) == ["bet365"]
    assert market_odds.loc[0, "home_team_id"] == "KOR"
    assert market_odds.loc[0, "away_team_id"] == "CPV"
    assert market_odds.loc[0, "source_sheet"] == "WorldCup2026Qualifiers"


def test_parse_workbook_skips_missing_odds_and_reports_unmatched_names():
    workbook = _workbook_bytes(
        {
            "WorldCup2018": pd.DataFrame(
                [
                    {
                        "Home": "Atlantis FC",
                        "Away": "Iran",
                        "Date": "2018-06-15",
                        "H-Avg": 2.1,
                        "D-Avg": 3.2,
                        "A-Avg": 3.8,
                    },
                    {
                        "Home": "United States",
                        "Away": "Iran",
                        "Date": "2018-06-16",
                        "H-Avg": None,
                        "D-Avg": 3.2,
                        "A-Avg": 3.8,
                    },
                ]
            )
        }
    )

    market_odds = parse_workbook(workbook)

    assert len(market_odds) == 1
    assert pd.isna(market_odds.loc[0, "home_team_id"])
    assert market_odds.loc[0, "away_team_id"] == "IRN"
    assert market_odds.attrs["skipped_missing_odds_rows"] == 1
    assert market_odds.attrs["unmatched_team_names"] == ["Atlantis FC"]
