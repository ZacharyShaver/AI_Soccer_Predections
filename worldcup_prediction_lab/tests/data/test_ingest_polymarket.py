from __future__ import annotations

import pytest

from wc_predictor.data.devig import remove_vig
from wc_predictor.data.ingest_polymarket import parse_world_cup_match_events


def _polymarket_event_fixture() -> dict:
    return {
        "id": "evt-usa-iran",
        "title": "United States vs. Iran",
        "slug": "world-cup-united-states-iran",
        "active": True,
        "closed": False,
        "markets": [
            {
                "id": "m-home",
                "question": "Will United States beat Iran?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.62","0.40"]',
            },
            {
                "id": "m-draw",
                "question": "Will United States vs. Iran end in a draw?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.25","0.77"]',
            },
            {
                "id": "m-away",
                "question": "Will Iran beat United States?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.16","0.86"]',
            },
            {
                "id": "m-null",
                "question": "Will either team win by 5+ goals?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": None,
            },
            {
                "id": "m-placeholder-zero",
                "question": "Will United States vs. Iran finish 9-9?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0","1"]',
            },
            {
                "id": "m-placeholder-empty",
                "question": "Placeholder",
                "outcomes": '["Yes","No"]',
            },
        ],
    }


def test_parse_world_cup_match_event_decodes_json_price_strings_and_devigs_hda():
    market_rows, summary = parse_world_cup_match_events([_polymarket_event_fixture()])

    assert len(market_rows) == 1
    row = market_rows.iloc[0]
    assert row["event_id"] == "evt-usa-iran"
    assert row["home_team_name"] == "United States"
    assert row["away_team_name"] == "Iran"
    assert row["home_team_id"] == "USA"
    assert row["away_team_id"] == "IRN"
    assert row["market_type"] == "three_way"
    assert row["home_market_id"] == "m-home"
    assert row["draw_market_id"] == "m-draw"
    assert row["away_market_id"] == "m-away"

    expected = remove_vig([0.62, 0.25, 0.16])
    assert [row["prob_home"], row["prob_draw"], row["prob_away"]] == pytest.approx(expected)
    assert row["prob_home"] + row["prob_draw"] + row["prob_away"] == pytest.approx(1.0)
    assert summary["events_seen"] == 1
    assert summary["events_matched"] == 1
    assert summary["markets_skipped_invalid_price"] == 3


def test_parse_world_cup_match_event_reports_unmatched_team_names():
    event = _polymarket_event_fixture()
    event["id"] = "evt-atlantis-iran"
    event["title"] = "Atlantis FC vs. Iran"
    event["markets"][0]["question"] = "Will Atlantis FC beat Iran?"
    event["markets"][1]["question"] = "Will Atlantis FC vs. Iran end in a draw?"
    event["markets"][2]["question"] = "Will Iran beat Atlantis FC?"

    market_rows, summary = parse_world_cup_match_events([event])

    assert len(market_rows) == 1
    assert market_rows.loc[0, "home_team_id"] is None
    assert market_rows.loc[0, "away_team_id"] == "IRN"
    assert summary["unmatched_team_names"] == ["Atlantis FC"]


def test_parse_world_cup_match_event_handles_hyphenated_title_alias_variant():
    event = {
        "id": "evt-bih-qatar",
        "title": "Bosnia-Herzegovina vs. Qatar",
        "active": True,
        "closed": False,
        "markets": [
            {
                "id": "m-away",
                "question": "Will Qatar win on 2026-06-24?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.135","0.865"]',
            },
            {
                "id": "m-home",
                "question": "Will Bosnia and Herzegovina win on 2026-06-24?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.675","0.325"]',
            },
            {
                "id": "m-draw",
                "question": "Will Bosnia and Herzegovina vs. Qatar end in a draw?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.195","0.805"]',
            },
        ],
    }

    market_rows, summary = parse_world_cup_match_events([event])

    assert len(market_rows) == 1
    assert market_rows.loc[0, "home_team_id"] == "BIH"
    assert market_rows.loc[0, "away_team_id"] == "QAT"
    assert summary["unmatched_team_names"] == []
