"""Scratch (not committed): probe transfermarkt-datasets for squad-value viability.

Discovery evidence for the "new strength data" lane. Reads the remote DuckDB
file over httpfs (no bulk download) and answers:
1. What columns do player_valuations / players carry?
2. What date range do valuations cover (leak-free join needs dated history)?
3. How many valued players per country of citizenship — do small WC nations
   (DR Congo, Cape Verde, Curacao...) have enough coverage, or only UEFA?
"""

from __future__ import annotations

import json

import duckdb

REMOTE = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/transfermarkt-datasets.duckdb"

PROBE_COUNTRIES = [
    "Argentina", "Brazil", "Japan", "United States", "Mexico",
    "DR Congo", "Cape Verde", "Curacao", "Uzbekistan", "Jordan",
    "Haiti", "New Zealand", "Iran", "Morocco", "Ghana",
]


def main() -> None:
    con = duckdb.connect(":memory:")
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"ATTACH '{REMOTE}' AS tm (READ_ONLY);")

    out: dict = {}
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_catalog='tm'"
    ).fetchall()]
    out["tables"] = tables

    for table in ("player_valuations", "players"):
        cols = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_catalog='tm' AND table_name=? ORDER BY ordinal_position",
            [table],
        ).fetchall()
        out[f"{table}_columns"] = [f"{c}:{t}" for c, t in cols]

    out["valuations_summary"] = con.execute(
        "SELECT COUNT(*) AS rows, MIN(date) AS min_date, MAX(date) AS max_date, "
        "COUNT(DISTINCT player_id) AS players FROM tm.player_valuations"
    ).df().to_dict(orient="records")[0]

    out["players_rows"] = con.execute("SELECT COUNT(*) FROM tm.players").fetchone()[0]

    # Valued players per probe country, and how far back their valuations go.
    placeholders = ",".join("?" for _ in PROBE_COUNTRIES)
    out["coverage_by_country"] = con.execute(
        f"""
        SELECT p.country_of_citizenship AS country,
               COUNT(DISTINCT v.player_id) AS valued_players,
               MIN(v.date) AS earliest_valuation,
               SUM(CASE WHEN v.date >= '2024-01-01' THEN 1 ELSE 0 END) AS rows_since_2024
        FROM tm.player_valuations v
        JOIN tm.players p USING (player_id)
        WHERE p.country_of_citizenship IN ({placeholders})
        GROUP BY 1 ORDER BY 2 DESC
        """,
        PROBE_COUNTRIES,
    ).df().to_dict(orient="records")

    # Valuation rows per year — how thin is the early history?
    out["rows_by_year"] = con.execute(
        "SELECT EXTRACT(year FROM date) AS yr, COUNT(*) AS rows "
        "FROM tm.player_valuations GROUP BY 1 ORDER BY 1"
    ).df().to_dict(orient="records")

    print(json.dumps(out, indent=1, default=str))
    with open("runs/squad_value_scratch/probe.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)


if __name__ == "__main__":
    main()
