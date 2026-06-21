from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

import pandas as pd

from _common import ROOT, head_rows, http_get, now_utc_iso, save_sample


SOURCE_ID = "martj42"
BASE_URL = "https://raw.githubusercontent.com/martj42/international_results/master"
FILES = ("results.csv", "shootouts.csv", "goalscorers.csv", "former_names.csv")
SCHEMA_SAMPLE_PATH = (
    ROOT / "discovery" / "findings" / "d1-martj42-results-schema-sample.csv"
)


def fetch_csv(name: str) -> tuple[pd.DataFrame, dict[str, str]]:
    url = f"{BASE_URL}/{name}"
    response = http_get(url)
    sample_meta = save_sample(SOURCE_ID, name, response.content)
    df = pd.read_csv(BytesIO(response.content))
    return df, {"url": url, **sample_meta}


def main() -> None:
    frames: dict[str, pd.DataFrame] = {}
    samples: dict[str, dict[str, str]] = {}

    for name in FILES:
        df, sample_meta = fetch_csv(name)
        frames[name] = df
        samples[name] = sample_meta

    results = frames["results.csv"].copy()
    results["date"] = pd.to_datetime(results["date"], errors="raise")

    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    last_three_years_start = today - pd.DateOffset(years=3)
    matches_2025_2026 = results[results["date"].dt.year.isin([2025, 2026])]
    complete_score_rows = results[
        results["home_score"].notna() & results["away_score"].notna()
    ]
    blank_score_rows = results[
        results["home_score"].isna() | results["away_score"].isna()
    ]
    teams = pd.concat([results["home_team"], results["away_team"]], ignore_index=True)

    SCHEMA_SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    head_rows(results, 20).to_csv(SCHEMA_SAMPLE_PATH, index=False)

    raw_file_summaries = {
        name: {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "sample_saved_at": samples[name]["path"],
            "sha256": samples[name]["sha256"],
            "url": samples[name]["url"],
        }
        for name, df in frames.items()
    }

    summary = {
        "source_id": SOURCE_ID,
        "generated_at": now_utc_iso(),
        "results_csv": {
            "columns": list(results.columns),
            "total_rows": int(len(results)),
            "min_date": results["date"].min().date().isoformat(),
            "max_date": results["date"].max().date().isoformat(),
            "max_completed_score_date": complete_score_rows["date"]
            .max()
            .date()
            .isoformat(),
            "blank_score_rows": int(len(blank_score_rows)),
            "last_three_years_start": last_three_years_start.date().isoformat(),
            "last_three_years_rows": int(
                (results["date"] >= last_three_years_start).sum()
            ),
            "distinct_teams": int(teams.nunique()),
            "matches_2025_2026_present": bool(not matches_2025_2026.empty),
            "matches_2025_2026_rows": int(len(matches_2025_2026)),
            "years_present_in_2025_2026": [
                int(year) for year in sorted(matches_2025_2026["date"].dt.year.unique())
            ],
            "schema_sample_path": SCHEMA_SAMPLE_PATH.relative_to(ROOT).as_posix(),
        },
        "raw_files": raw_file_summaries,
    }

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
