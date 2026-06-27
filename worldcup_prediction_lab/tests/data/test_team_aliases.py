import csv
from pathlib import Path

import pytest

from wc_predictor.config import settings
from wc_predictor.data.team_aliases import TeamAliasResolver


WORLD_CUP_2026_TEAMS = [
    "Mexico",
    "South Africa",
    "South Korea",
    "Czech Republic",
    "Canada",
    "Bosnia & Herzegovina",
    "Qatar",
    "Switzerland",
    "Brazil",
    "Morocco",
    "Haiti",
    "Scotland",
    "USA",
    "Paraguay",
    "Australia",
    "Turkey",
    "Germany",
    "Curaçao",
    "Ivory Coast",
    "Ecuador",
    "Netherlands",
    "Japan",
    "Sweden",
    "Tunisia",
    "Belgium",
    "Egypt",
    "Iran",
    "New Zealand",
    "Spain",
    "Cape Verde",
    "Saudi Arabia",
    "Uruguay",
    "France",
    "Senegal",
    "Iraq",
    "Norway",
    "Argentina",
    "Algeria",
    "Austria",
    "Jordan",
    "Portugal",
    "DR Congo",
    "Uzbekistan",
    "Colombia",
    "England",
    "Croatia",
    "Ghana",
    "Panama",
]


@pytest.fixture()
def resolver():
    return TeamAliasResolver.from_csv()


@pytest.mark.parametrize(
    ("openfootball_name", "alt_name", "alt_source", "canonical_name"),
    [
        ("USA", "United States", "martj42", "United States"),
        (
            "Bosnia & Herzegovina",
            "Bosnia and Herzegovina",
            "martj42",
            "Bosnia and Herzegovina",
        ),
        ("South Korea", "Korea Republic", "fifa", "South Korea"),
        ("Iran", "IR Iran", "fifa", "Iran"),
        ("Cape Verde", "Cabo Verde", "fifa", "Cape Verde"),
        ("DR Congo", "Congo DR", "fifa", "DR Congo"),
        ("Ivory Coast", "Cote d'Ivoire", "fifa", "Ivory Coast"),
        ("Czech Republic", "Czechia", "martj42", "Czechia"),
        ("Turkey", "Turkiye", "fifa", "Turkey"),
    ],
)
def test_difficult_aliases_resolve_to_same_canonical_team(
    resolver, openfootball_name, alt_name, alt_source, canonical_name
):
    openfootball_alias = resolver.resolve(openfootball_name, source="openfootball")
    alternate_alias = resolver.resolve(alt_name, source=alt_source)

    assert openfootball_alias.canonical_team_id == alternate_alias.canonical_team_id
    assert openfootball_alias.canonical_name == canonical_name
    assert alternate_alias.canonical_name == canonical_name


def test_resolver_is_case_whitespace_and_diacritic_insensitive(resolver):
    curacao = resolver.resolve("  curacao  ", source="openfootball")
    curacao_with_diacritic = resolver.resolve("Curaçao", source="openfootball")

    assert curacao.canonical_team_id == curacao_with_diacritic.canonical_team_id
    assert curacao.canonical_name == "Curaçao"


def test_unknown_team_raises_clear_error(resolver):
    with pytest.raises(KeyError, match="Unknown team alias.*Atlantis FC"):
        resolver.resolve("Atlantis FC", source="openfootball")


def test_all_world_cup_2026_openfootball_teams_resolve(resolver):
    resolved_ids = {
        resolver.resolve(team, source="openfootball").canonical_team_id
        for team in WORLD_CUP_2026_TEAMS
    }

    assert len(resolved_ids) == 48


def test_seed_table_has_consistent_unique_canonical_ids(resolver):
    alias_path = settings.CONFIG_DIR / "team_aliases.csv"
    with alias_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    manual_rows = [row for row in rows if row["source_name"] == "manual"]
    # Every canonical id maps to exactly one canonical name (no id reused for two
    # different countries), even though one id may carry several source spellings.
    name_by_id: dict[str, str] = {}
    for row in manual_rows:
        team_id, name = row["canonical_team_id"], row["canonical_name"]
        assert name_by_id.setdefault(team_id, name) == name, f"conflicting name for {team_id}"

    # The 48 World Cup 2026 teams remain present and uniquely identified.
    wc_ids = {
        resolver.resolve(team, source="openfootball").canonical_team_id
        for team in WORLD_CUP_2026_TEAMS
    }
    assert len(wc_ids) == 48
    assert wc_ids <= set(name_by_id)

    # The alias-table expansion grew coverage well past the original 48 seeds.
    assert len(name_by_id) >= 200


def test_reports_unresolved_martj42_sample_names_without_crashing(resolver, capsys):
    sample_path = (
        Path(__file__).resolve().parents[3]
        / "discovery"
        / "findings"
        / "d1-martj42-results-schema-sample.csv"
    )
    with sample_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    names = {
        row[column]
        for row in rows
        for column in ("home_team", "away_team")
        if row[column]
    }
    unresolved = resolver.unresolved_names(names, source="martj42")
    if unresolved:
        print("Unresolved martj42 sample names: " + ", ".join(unresolved))

    capsys.readouterr()
    # The expanded alias table now resolves every name in the discovery sample
    # (Northern Ireland and Wales used to be the only holdouts).
    assert unresolved == []
