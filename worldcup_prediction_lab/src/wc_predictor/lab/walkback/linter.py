"""Leakage linter for news wells.

Belt and braces on top of the GDELT date window: a doc is rejected if it is
dated on/after match day, or if its text pairs both team names with a
scoreline or past-tense result language. False positives are acceptable —
dropping a clean preview costs a little coverage; keeping a leaky doc
invalidates the match.
"""

from __future__ import annotations

import re

SCORE_RE = re.compile(r"\b\d{1,2}\s?[-–:]\s?\d{1,2}\b")
RESULT_WORDS_RE = re.compile(
    r"\b(beat|defeated|won|lost to|thrashed|edged|drew with|held)\b", re.IGNORECASE
)


def _text(doc: dict) -> str:
    return f"{doc.get('title') or ''}\n{doc.get('body') or ''}"


def lint_doc(doc: dict, *, home: str, away: str, match_date: str) -> list[str]:
    violations: list[str] = []
    if str(doc.get("seendate", "9999")) >= str(match_date):
        violations.append(f"date: {doc.get('seendate')} not before {match_date}")
    text = _text(doc)
    both_teams = re.search(re.escape(home), text, re.I) and re.search(re.escape(away), text, re.I)
    if both_teams and SCORE_RE.search(text):
        violations.append("score: scoreline pattern with both team names present")
    if both_teams and RESULT_WORDS_RE.search(text):
        violations.append("result-language: past-tense result verb with both team names")
    return violations


def clean_well(well: dict) -> dict:
    kept, dropped = [], []
    for doc in well.get("docs", []):
        v = lint_doc(doc, home=well["home_team"], away=well["away_team"],
                     match_date=well["match_date"])
        if v:
            dropped.append({"url": doc.get("url", ""), "violations": v})
        else:
            kept.append(doc)
    out = dict(well)
    out["docs"] = kept
    out["lint"] = {"kept": len(kept), "dropped": dropped}
    return out


def well_ok(well: dict, *, min_docs: int = 3) -> bool:
    return len(well.get("docs", [])) >= min_docs
