"""Ingest transfermarkt-datasets player valuations into a squad-value silver table.

Source: https://github.com/dcaribou/transfermarkt-datasets (CC0-1.0), which
publishes weekly-refreshed Transfermarkt scrapes as a hosted DuckDB file.
This is the lab's first strength signal that is NOT derived from historical
scorelines: per-player market values are dated (2004+), so a leak-free
"squad value as of this match date" join is possible.

The silver table is a MONTHLY per-team series, not raw valuations:
``(team_id, date, squad_value_eur, valued_players)`` where the value at each
month-end sums the ``top_k`` most valuable players holding a valuation dated
within ``staleness_days`` before that month-end. The staleness window keeps
retired players (whose final Transfermarkt valuation would otherwise persist
forever) from inflating a country's talent pool.

Honest caveats, also written to the DQ report:
* citizenship is a talent-POOL proxy, not the actual 26-man roster;
* Transfermarkt values are crowd-sourced estimates, thin before ~2007;
* dual citizens count for their listed ``country_of_citizenship`` only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.data.team_aliases import TeamAliasResolver

REMOTE_DUCKDB_URL = (
    "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/transfermarkt-datasets.duckdb"
)
SQUAD_VALUES_FILE = "transfermarkt_squad_values.parquet"
ALIAS_SOURCE = "transfermarkt"
DEFAULT_TOP_K = 15
DEFAULT_STALENESS_DAYS = 730  # two years: a stale valuation stops counting

SQUAD_VALUE_COLUMNS = [
    "team_id",
    "team_name",
    "date",
    "squad_value_eur",
    "valued_players",
]


def _utc_iso() -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _write_parquet(dataframe: pd.DataFrame, path: Path) -> None:
    import duckdb

    path.parent.mkdir(parents=True, exist_ok=True)
    escaped_path = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        connection.register("df_to_write", dataframe)
        connection.execute(f"COPY df_to_write TO '{escaped_path}' (FORMAT PARQUET)")


def fetch_raw(url: str = REMOTE_DUCKDB_URL) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pull the two needed tables (slim columns) from the hosted DuckDB file."""

    import duckdb

    with duckdb.connect(database=":memory:") as connection:
        connection.execute("INSTALL httpfs; LOAD httpfs;")
        escaped_url = url.replace("'", "''")
        connection.execute(f"ATTACH '{escaped_url}' AS tm (READ_ONLY);")
        valuations = connection.execute(
            "SELECT player_id, CAST(date AS DATE) AS date, market_value_in_eur "
            "FROM tm.player_valuations "
            "WHERE market_value_in_eur IS NOT NULL AND market_value_in_eur > 0"
        ).df()
        players = connection.execute(
            "SELECT player_id, name, country_of_citizenship FROM tm.players "
            "WHERE country_of_citizenship IS NOT NULL"
        ).df()
    return valuations, players


def build_squad_values(
    valuations: pd.DataFrame,
    players: pd.DataFrame,
    resolver: TeamAliasResolver,
    *,
    top_k: int = DEFAULT_TOP_K,
    staleness_days: int = DEFAULT_STALENESS_DAYS,
) -> tuple[pd.DataFrame, list[str]]:
    """Monthly per-team squad-value series from dated player valuations.

    Pure and offline-testable. Returns ``(squad_values_df, unmatched_countries)``
    where unmatched countries are reported (not fatal) so the DQ report can
    surface alias-table gaps exactly like the Football-Data ingestion did.
    """

    required_valuations = {"player_id", "date", "market_value_in_eur"}
    missing = required_valuations - set(valuations.columns)
    if missing:
        raise ValueError(f"valuations missing required columns: {sorted(missing)}")
    required_players = {"player_id", "country_of_citizenship"}
    missing = required_players - set(players.columns)
    if missing:
        raise ValueError(f"players missing required columns: {sorted(missing)}")

    frame = valuations.merge(
        players[["player_id", "country_of_citizenship"]], on="player_id", how="inner"
    )
    frame = frame[frame["market_value_in_eur"] > 0].copy()
    frame["date"] = pd.to_datetime(frame["date"])

    countries = sorted(frame["country_of_citizenship"].dropna().unique())
    resolved: dict[str, tuple[str, str]] = {}
    unmatched: list[str] = []
    for country in countries:
        try:
            alias = resolver.resolve(country, source=ALIAS_SOURCE)
            resolved[country] = (alias.canonical_team_id, alias.canonical_name)
        except KeyError:
            unmatched.append(country)

    frame = frame[frame["country_of_citizenship"].isin(resolved)].copy()
    if frame.empty:
        return pd.DataFrame(columns=SQUAD_VALUE_COLUMNS), unmatched

    staleness = pd.Timedelta(days=staleness_days)
    rows: list[dict] = []
    for country, group in frame.groupby("country_of_citizenship", sort=True):
        team_id, team_name = resolved[country]
        # One value per (player, month): the latest valuation inside the month.
        events = group.sort_values(["player_id", "date"])
        events = events.assign(month=events["date"].dt.to_period("M").dt.end_time.dt.normalize())
        per_month = events.groupby(["player_id", "month"], sort=True).last().reset_index()

        # Player x month matrix, forward-filled at most `staleness` months.
        matrix = per_month.pivot(
            index="month", columns="player_id", values="market_value_in_eur"
        )
        full_index = pd.date_range(
            matrix.index.min(), matrix.index.max(), freq="ME"
        ).union(matrix.index)
        limit = max(1, int(staleness / pd.Timedelta(days=30.44)))
        matrix = matrix.reindex(full_index).ffill(limit=limit)

        for month, values in matrix.iterrows():
            live = values.dropna()
            if live.empty:
                continue
            top = live.nlargest(top_k)
            rows.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "date": month,
                    "squad_value_eur": float(top.sum()),
                    "valued_players": int(live.size),
                }
            )

    squad_values = pd.DataFrame(rows, columns=SQUAD_VALUE_COLUMNS)
    squad_values = squad_values.sort_values(["team_id", "date"]).reset_index(drop=True)
    return squad_values, unmatched


def load_squad_values(path: str | Path | None = None) -> pd.DataFrame:
    import duckdb

    silver_path = Path(path) if path is not None else settings.SILVER_DIR / SQUAD_VALUES_FILE
    if not silver_path.exists():
        return pd.DataFrame(columns=SQUAD_VALUE_COLUMNS)
    escaped_path = str(silver_path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        frame = connection.execute(f"SELECT * FROM read_parquet('{escaped_path}')").df()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def _dq_report(
    squad_values: pd.DataFrame,
    unmatched: list[str],
    *,
    top_k: int,
    staleness_days: int,
    source_url: str,
) -> str:
    by_team = squad_values.groupby("team_name")["date"].agg(["min", "max", "count"])
    coverage_2010 = squad_values[squad_values["date"] >= "2010-01-01"]["team_id"].nunique()
    sample = by_team.sort_values("count", ascending=False).head(10)
    sample_rows = "\n".join(
        f"| {name} | {row['min']:%Y-%m} | {row['max']:%Y-%m} | {int(row['count'])} |"
        for name, row in sample.iterrows()
    )
    unmatched_text = (
        "\n".join(f"- {name}" for name in unmatched) if unmatched else "- (none)"
    )
    return f"""# DQ: transfermarkt squad values

Generated: `{_utc_iso()}`
Source: `{source_url}` (transfermarkt-datasets, CC0-1.0; weekly refresh)

Monthly per-team squad value = sum of the top {top_k} player market values among
citizens holding a valuation dated within {staleness_days} days before month-end.

## Coverage

- Rows: {len(squad_values)}
- Teams with any coverage: {squad_values["team_id"].nunique()}
- Teams with coverage since 2010: {coverage_2010}
- Date range: {squad_values["date"].min():%Y-%m} .. {squad_values["date"].max():%Y-%m}

| Team | First | Last | Months |
| --- | --- | --- | ---: |
{sample_rows}

## Unmatched citizenship names (no alias row; excluded)

{unmatched_text}

## Caveats

- Citizenship is a talent-POOL proxy, not the selected 26-man roster.
- Transfermarkt values are crowd estimates; history is thin before ~2007.
- Dual citizens count only for their listed country_of_citizenship.
- The {staleness_days}-day staleness window drops retired/inactive players
  whose final valuation would otherwise persist forever.
"""


def run(
    *,
    write: bool = True,
    url: str = REMOTE_DUCKDB_URL,
    top_k: int = DEFAULT_TOP_K,
    staleness_days: int = DEFAULT_STALENESS_DAYS,
) -> dict:
    resolver = TeamAliasResolver.from_csv()
    valuations, players = fetch_raw(url)
    squad_values, unmatched = build_squad_values(
        valuations, players, resolver, top_k=top_k, staleness_days=staleness_days
    )

    silver_path = settings.SILVER_DIR / SQUAD_VALUES_FILE
    report_path = settings.PROJECT_DIR / "reports" / "data_quality" / "transfermarkt_squad_values.md"
    if write:
        _write_parquet(squad_values, silver_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            _dq_report(
                squad_values,
                unmatched,
                top_k=top_k,
                staleness_days=staleness_days,
                source_url=url,
            ),
            encoding="utf-8",
        )

    return {
        "rows": len(squad_values),
        "teams": int(squad_values["team_id"].nunique()) if not squad_values.empty else 0,
        "unmatched_countries": unmatched,
        "silver_path": str(silver_path),
        "report_path": str(report_path),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run(), indent=2, default=str))
