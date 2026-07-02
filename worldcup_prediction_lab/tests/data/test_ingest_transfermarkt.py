from __future__ import annotations

import pandas as pd
import pytest

from wc_predictor.data.ingest_transfermarkt import build_squad_values
from wc_predictor.data.team_aliases import TeamAlias, TeamAliasResolver, normalize_team_name


def _resolver(mapping: dict[str, tuple[str, str]]) -> TeamAliasResolver:
    aliases = {
        ("manual", normalize_team_name(name)): TeamAlias(
            canonical_team_id=team_id, canonical_name=canonical
        )
        for name, (team_id, canonical) in mapping.items()
    }
    return TeamAliasResolver(aliases)


RESOLVER = _resolver({"Ruritania": ("RUR", "Ruritania"), "Grand Fenwick": ("FEN", "Grand Fenwick")})


def _valuation(player_id, date, value):
    return {"player_id": player_id, "date": date, "market_value_in_eur": value}


def _player(player_id, country):
    return {"player_id": player_id, "name": f"p{player_id}", "country_of_citizenship": country}


def test_top_k_sum_and_monthly_as_of_semantics():
    valuations = pd.DataFrame(
        [
            _valuation(1, "2020-01-10", 10_000_000),
            _valuation(2, "2020-01-15", 5_000_000),
            _valuation(3, "2020-01-20", 1_000_000),
            _valuation(1, "2020-03-05", 20_000_000),  # revaluation
        ]
    )
    players = pd.DataFrame([_player(1, "Ruritania"), _player(2, "Ruritania"), _player(3, "Ruritania")])

    squad, unmatched = build_squad_values(valuations, players, RESOLVER, top_k=2)

    assert unmatched == []
    january = squad[(squad["team_id"] == "RUR") & (squad["date"] == "2020-01-31")]
    assert january["squad_value_eur"].iloc[0] == pytest.approx(15_000_000)  # top-2 of 3
    assert january["valued_players"].iloc[0] == 3

    march = squad[(squad["team_id"] == "RUR") & (squad["date"] == "2020-03-31")]
    assert march["squad_value_eur"].iloc[0] == pytest.approx(25_000_000)  # 20m + 5m


def test_stale_valuations_expire():
    valuations = pd.DataFrame(
        [
            _valuation(1, "2018-01-10", 8_000_000),
            _valuation(2, "2020-06-15", 2_000_000),
        ]
    )
    players = pd.DataFrame([_player(1, "Ruritania"), _player(2, "Ruritania")])

    squad, _ = build_squad_values(valuations, players, RESOLVER, top_k=15, staleness_days=365)

    june_2020 = squad[(squad["team_id"] == "RUR") & (squad["date"] == "2020-06-30")]
    assert june_2020["squad_value_eur"].iloc[0] == pytest.approx(2_000_000)
    assert june_2020["valued_players"].iloc[0] == 1  # player 1's 2018 value expired


def test_unmatched_countries_are_reported_not_fatal():
    valuations = pd.DataFrame(
        [_valuation(1, "2020-01-10", 1_000_000), _valuation(2, "2020-01-10", 2_000_000)]
    )
    players = pd.DataFrame([_player(1, "Ruritania"), _player(2, "Atlantis")])

    squad, unmatched = build_squad_values(valuations, players, RESOLVER)

    assert unmatched == ["Atlantis"]
    assert set(squad["team_id"]) == {"RUR"}


def test_zero_and_null_values_are_dropped():
    valuations = pd.DataFrame(
        [
            _valuation(1, "2020-01-10", 0),
            _valuation(2, "2020-01-10", 3_000_000),
        ]
    )
    players = pd.DataFrame([_player(1, "Ruritania"), _player(2, "Ruritania")])

    squad, _ = build_squad_values(valuations, players, RESOLVER)
    january = squad[squad["date"] == "2020-01-31"]
    assert january["valued_players"].iloc[0] == 1
    assert january["squad_value_eur"].iloc[0] == pytest.approx(3_000_000)


def test_missing_required_columns_raise():
    players = pd.DataFrame([_player(1, "Ruritania")])
    with pytest.raises(ValueError, match="valuations missing"):
        build_squad_values(pd.DataFrame({"player_id": [1]}), players, RESOLVER)
