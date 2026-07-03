from wc_predictor.lab.walkback.linter import clean_well, lint_doc, well_ok


def _doc(**over):
    base = {"url": "https://ex.com/a", "title": "Brazil vs Norway preview",
            "seendate": "2025-03-08", "source": "ex.com", "body": None}
    base.update(over)
    return base


KW = dict(home="Brazil", away="Norway", match_date="2025-03-10")


def test_clean_doc_passes():
    assert lint_doc(_doc(), **KW) == []


def test_doc_on_or_after_match_day_rejected():
    assert "date" in ";".join(lint_doc(_doc(seendate="2025-03-10"), **KW))
    assert "date" in ";".join(lint_doc(_doc(seendate="2025-03-11"), **KW))


def test_scoreline_with_both_teams_rejected():
    body = "Brazil beat Norway 2-1 at the Maracana on Tuesday."
    assert any("score" in v for v in lint_doc(_doc(body=body), **KW))


def test_past_tense_result_language_rejected():
    body = "Norway defeated Brazil in a stunning upset."
    assert any("result-language" in v for v in lint_doc(_doc(body=body), **KW))


def test_scoreline_without_team_context_is_fine():
    body = "Haaland has 2-1 odds to score first according to bookmakers."
    # both team names absent around the score pattern -> allowed
    assert lint_doc(_doc(title="Odds roundup", body=body), **KW) == []


def test_clean_well_and_gate():
    well = {"match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
            "match_date": "2025-03-10", "built_at": "x",
            "docs": [_doc(), _doc(url="u2", seendate="2025-03-11"),
                     _doc(url="u3"), _doc(url="u4")]}
    cleaned = clean_well(well)
    assert cleaned["lint"]["kept"] == 3
    assert cleaned["lint"]["dropped"][0]["url"] == "u2"
    assert well_ok(cleaned) is True
    assert well_ok(cleaned, min_docs=4) is False
