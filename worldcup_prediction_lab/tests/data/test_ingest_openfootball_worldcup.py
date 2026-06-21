from __future__ import annotations

import pandas as pd
import pytest

from wc_predictor.data.ingest_openfootball_worldcup import (
    parse_cup_finals_text,
    parse_cup_text,
    parse_group_declaration,
)


GROUP_DECLARATION = (
    "Group A | Mexico  South Africa  South Korea  Czech Republic"
)

GROUP_CUP_TEXT = f"""= World Cup 2026

{GROUP_DECLARATION}

* Group A
Thu June 11
  13:00 UTC-6     Mexico  2-0 (1-0)  South Africa        @ Mexico City
Wed June 24
  19:00 UTC-6     Czech Republic       v Mexico       @ Mexico City
"""


KNOCKOUT_TEXT = """= World Cup 2026

* Round of 32
Sun Jun 28
  (73) 12:00 UTC-7  2A v 2B           @ Los Angeles (Inglewood)

* Match for third place
Sat Jul 18
  (103) 17:00 UTC-4    L101 v L102    @ Miami (Miami Gardens)
"""


def test_parse_group_declaration_extracts_group_and_teams():
    group_name, teams = parse_group_declaration(GROUP_DECLARATION)

    assert group_name == "A"
    assert teams == ["Mexico", "South Africa", "South Korea", "Czech Republic"]


def test_group_fixtures_resolve_real_teams_and_stage():
    fixtures = parse_cup_text(GROUP_CUP_TEXT, write=False)

    assert list(fixtures["stage"]) == ["group", "group"]
    assert list(fixtures["group"]) == ["A", "A"]
    assert fixtures.loc[0, "match_date"].strftime("%Y-%m-%d") == "2026-06-11"
    assert fixtures.loc[0, "venue"] == "Mexico City"
    assert fixtures.loc[0, "home_team_id"] == "MEX"
    assert fixtures.loc[0, "away_team_id"] == "ZAF"
    assert fixtures.loc[1, "home_team_id"] == "CZE"
    assert fixtures.loc[1, "away_team_id"] == "MEX"
    assert fixtures[["home_slot", "away_slot"]].isna().all().all()
    assert fixtures["match_number"].isna().all()


def test_knockout_fixtures_keep_placeholder_slots_with_null_team_ids():
    fixtures = parse_cup_finals_text(KNOCKOUT_TEXT, write=False)

    assert list(fixtures["stage"]) == ["round_of_32", "third_place"]
    assert fixtures.loc[0, "match_number"] == 73
    assert fixtures.loc[0, "match_date"].strftime("%Y-%m-%d") == "2026-06-28"
    assert fixtures.loc[0, "venue"] == "Los Angeles (Inglewood)"
    assert fixtures.loc[0, "home_slot"] == "2A"
    assert fixtures.loc[0, "away_slot"] == "2B"
    assert fixtures.loc[1, "home_slot"] == "L101"
    assert fixtures.loc[1, "away_slot"] == "L102"
    assert pd.isna(fixtures.loc[0, "home_team_id"])
    assert pd.isna(fixtures.loc[0, "away_team_id"])


def test_unknown_group_team_name_raises():
    text = """= World Cup 2026

Group A | Mexico  Atlantis  South Korea  Czech Republic

* Group A
Thu June 11
  13:00 UTC-6     Mexico  v  Atlantis        @ Mexico City
"""

    with pytest.raises(KeyError, match="Atlantis"):
        parse_cup_text(text, write=False)
