from __future__ import annotations

import pandas as pd
import pytest

from wc_predictor.data.ingest_international_results import (
    parse_bronze,
    split_and_normalize,
)


FIXTURE_CSV = """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2025-03-22,United States,Canada,2,1,Friendly,Austin,United States,FALSE
2025-06-01,Wales,Northern Ireland,0,0,Friendly,Cardiff,Wales,FALSE
2026-06-11,Mexico,South Africa,,,FIFA World Cup,Mexico City,Mexico,FALSE
"""


def test_parse_bronze_preserves_source_schema_and_blank_scores():
    bronze = parse_bronze(FIXTURE_CSV.encode("utf-8"), write=False)

    assert list(bronze.columns) == [
        "date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "tournament",
        "city",
        "country",
        "neutral",
    ]
    assert len(bronze) == 3
    assert pd.isna(bronze.loc[2, "home_score"])
    assert pd.isna(bronze.loc[2, "away_score"])


def test_split_routes_completed_rows_to_matches_and_blank_scores_to_fixtures():
    bronze = parse_bronze(FIXTURE_CSV.encode("utf-8"), write=False)

    matches, fixtures = split_and_normalize(bronze, write=False)

    assert len(matches) == 2
    assert len(fixtures) == 1
    assert "match_id" in matches.columns
    assert "2026-06-11" not in set(matches["date"].astype(str))
    assert fixtures.iloc[0]["date"].strftime("%Y-%m-%d") == "2026-06-11"
    assert fixtures.iloc[0]["source"] == "martj42"
    assert fixtures.iloc[0]["status"] == "scheduled"
    assert pd.isna(fixtures.iloc[0]["home_score"])
    assert pd.isna(fixtures.iloc[0]["away_score"])
    assert matches.attrs["match_rows"] == 2
    assert fixtures.attrs["fixture_rows"] == 1


def test_martj42_unknown_names_are_identity_canonicalized():
    bronze = parse_bronze(FIXTURE_CSV.encode("utf-8"), write=False)

    matches, fixtures = split_and_normalize(bronze, write=False)

    team_pairs = {
        row.home_team: row.home_team_id for row in pd.concat([matches, fixtures]).itertuples()
    }
    assert team_pairs["United States"] == "USA"
    assert team_pairs["Wales"] == "wales"
    assert team_pairs["Mexico"] == "MEX"
    assert matches.attrs["auto_registered_team_count"] == 2
    assert matches.attrs["auto_registered_team_names"] == [
        "Northern Ireland",
        "Wales",
    ]


def test_same_day_double_headers_survive_with_distinct_match_ids():
    bronze = parse_bronze(
        """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
1974-02-17,Tahiti,New Caledonia,2,1,Friendly,Papeete,Tahiti,FALSE
1974-02-17,Tahiti,New Caledonia,1,2,Friendly,Papeete,Tahiti,FALSE
""".encode("utf-8"),
        write=False,
    )

    matches, fixtures = split_and_normalize(bronze, write=False)

    assert len(matches) == 2
    assert fixtures.empty
    assert matches["match_id"].nunique() == 2
    assert set(matches["occurrence_index"]) == {0, 1}
    assert matches.attrs["double_header_group_count"] == 1


def test_exact_identical_duplicate_rows_are_dropped():
    bronze = parse_bronze(
        """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2025-03-22,United States,Canada,2,1,Friendly,Austin,United States,FALSE
2025-03-22,United States,Canada,2,1,Friendly,Austin,United States,FALSE
""".encode("utf-8"),
        write=False,
    )

    matches, fixtures = split_and_normalize(bronze, write=False)

    assert len(matches) == 1
    assert fixtures.empty
    assert matches.attrs["exact_duplicate_rows_dropped"] == 1


def test_match_id_is_deterministic_for_same_input():
    bronze = parse_bronze(FIXTURE_CSV.encode("utf-8"), write=False)

    first_matches, _ = split_and_normalize(bronze, write=False)
    second_matches, _ = split_and_normalize(bronze, write=False)

    assert first_matches["match_id"].tolist() == second_matches["match_id"].tolist()


def test_data_quality_rejects_negative_scores():
    bronze = parse_bronze(
        """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2025-03-22,United States,Canada,-1,1,Friendly,Austin,United States,FALSE
""".encode("utf-8"),
        write=False,
    )

    with pytest.raises(ValueError, match="scores must be non-negative"):
        split_and_normalize(bronze, write=False)


def test_data_quality_rejects_non_boolean_neutral():
    bronze = parse_bronze(
        """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2025-03-22,United States,Canada,2,1,Friendly,Austin,United States,maybe
""".encode("utf-8"),
        write=False,
    )

    with pytest.raises(ValueError, match="neutral must be boolean"):
        split_and_normalize(bronze, write=False)
