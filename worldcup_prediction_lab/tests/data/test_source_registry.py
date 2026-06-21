import pytest

from wc_predictor.data.source_registry import get_source, load_sources


def test_sources_have_required_fields():
    sources = load_sources()

    assert len(sources) == 9
    for source in sources.values():
        assert source.source_id
        assert source.raw_retention_days >= 0
        assert source.required_fields


def test_milestone_one_ingestion_sources_are_phase_one():
    sources = load_sources()

    assert "international_results_martj42" in sources
    assert "openfootball_worldcup_2026" in sources
    assert sources["international_results_martj42"].phase == 1
    assert sources["openfootball_worldcup_2026"].phase == 1
    assert "active" in sources["international_results_martj42"].status
    assert "active" in sources["openfootball_worldcup_2026"].status


def test_get_source_returns_source_and_raises_for_unknown_id():
    source = get_source("international_results_martj42")

    assert source.source_id == "international_results_martj42"
    assert source.display_name == "martj42 International Results"

    with pytest.raises(KeyError, match="Unknown source_id"):
        get_source("missing_source")
