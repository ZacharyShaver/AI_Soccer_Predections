from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any

import pandas as pd

from _common import ROOT, now_utc_iso, save_sample


SOURCE_ID = "spi"
FINDINGS_DIR = ROOT / "discovery" / "findings"
README_URL = "https://raw.githubusercontent.com/fivethirtyeight/data/master/soccer-spi/README.md"
GITHUB_CONTENTS_URL = "https://api.github.com/repos/fivethirtyeight/data/contents/soccer-spi"
DOCUMENTED_FILES = (
    "spi_matches_intl.csv",
    "spi_global_rankings_intl.csv",
)
PROBE_URLS = [
    {
        "label": "github_raw_master_spi_matches_intl",
        "kind": "matches",
        "url": "https://raw.githubusercontent.com/fivethirtyeight/data/master/soccer-spi/spi_matches_intl.csv",
    },
    {
        "label": "github_raw_master_spi_global_rankings_intl",
        "kind": "rankings",
        "url": "https://raw.githubusercontent.com/fivethirtyeight/data/master/soccer-spi/spi_global_rankings_intl.csv",
    },
    {
        "label": "github_raw_main_spi_matches_intl",
        "kind": "matches",
        "url": "https://raw.githubusercontent.com/fivethirtyeight/data/main/soccer-spi/spi_matches_intl.csv",
    },
    {
        "label": "github_raw_main_spi_global_rankings_intl",
        "kind": "rankings",
        "url": "https://raw.githubusercontent.com/fivethirtyeight/data/main/soccer-spi/spi_global_rankings_intl.csv",
    },
    {
        "label": "legacy_projects_spi_matches_intl",
        "kind": "matches",
        "url": "https://projects.fivethirtyeight.com/soccer-api/international/spi_matches_intl.csv",
    },
    {
        "label": "legacy_projects_spi_global_rankings_intl",
        "kind": "rankings",
        "url": "https://projects.fivethirtyeight.com/soccer-api/international/spi_global_rankings_intl.csv",
    },
    {
        "label": "legacy_projects_spi_matches_alt",
        "kind": "matches",
        "url": "https://projects.fivethirtyeight.com/soccer-api/international/spi_matches.csv",
    },
    {
        "label": "legacy_projects_spi_global_rankings_alt",
        "kind": "rankings",
        "url": "https://projects.fivethirtyeight.com/soccer-api/international/spi_global_rankings.csv",
    },
]


def fetch(url: str) -> Any:
    import httpx

    headers = {
        "Accept": "text/csv,text/plain,application/json,*/*",
        "User-Agent": "AI-Soccer-Predictions discovery probe (+local research; contact: repo owner)",
    }
    return httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)


def preview_text(response: Any, limit: int = 180) -> str:
    return response.text[:limit].replace("\r", " ").replace("\n", " ").strip()


def looks_like_csv(response: Any) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    first_line = response.text.splitlines()[0].lower() if response.text.splitlines() else ""
    return (
        "csv" in content_type
        or first_line.startswith("season,date,")
        or first_line.startswith("rank,prev_rank,")
    )


def date_summary(df: pd.DataFrame) -> dict[str, str | None]:
    date_columns = [column for column in df.columns if "date" in column.lower()]
    latest_by_column: dict[str, str] = {}
    for column in date_columns:
        parsed = pd.to_datetime(df[column], errors="coerce")
        if parsed.notna().any():
            latest_by_column[column] = parsed.max().date().isoformat()
    latest = max(latest_by_column.values()) if latest_by_column else None
    return {"latest_date": latest, "latest_by_column": latest_by_column}


def write_schema_sample(label: str, df: pd.DataFrame) -> str:
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = FINDINGS_DIR / f"d3-spi-{label}-schema-sample.csv"
    df.head(20).to_csv(path, index=False)
    return path.relative_to(ROOT).as_posix()


def github_directory_summary() -> dict[str, Any]:
    response = fetch(GITHUB_CONTENTS_URL)
    summary: dict[str, Any] = {
        "url": GITHUB_CONTENTS_URL,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "final_url": str(response.url),
    }
    if response.status_code == 200:
        payload = response.json()
        names = [item.get("name") for item in payload if isinstance(item, dict)]
        summary["names"] = names
        summary["documented_csvs_present"] = {
            name: name in names for name in DOCUMENTED_FILES
        }
    else:
        summary["preview"] = preview_text(response)
    return summary


def readme_summary() -> dict[str, Any]:
    response = fetch(README_URL)
    summary: dict[str, Any] = {
        "url": README_URL,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "final_url": str(response.url),
    }
    if response.status_code == 200:
        sample = save_sample(SOURCE_ID, "README.md", response.content)
        lines = response.text.splitlines()
        summary["sample_saved_at"] = sample["path"]
        summary["sha256"] = sample["sha256"]
        summary["documented_files"] = [
            line.strip()[2:]
            for line in lines
            if line.strip().startswith("- https://projects.fivethirtyeight.com/soccer-api/")
        ]
    else:
        summary["preview"] = preview_text(response)
    return summary


def probe_csv_candidate(candidate: dict[str, str]) -> dict[str, Any]:
    response = fetch(candidate["url"])
    result: dict[str, Any] = {
        "label": candidate["label"],
        "kind": candidate["kind"],
        "url": candidate["url"],
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "final_url": str(response.url),
        "bytes": len(response.content),
    }

    if response.status_code != 200:
        result["outcome"] = "http_error"
        result["preview"] = preview_text(response)
        return result

    if not looks_like_csv(response):
        result["outcome"] = "non_csv_200"
        result["preview"] = preview_text(response)
        return result

    try:
        df = pd.read_csv(BytesIO(response.content))
    except Exception as exc:  # pragma: no cover - diagnostic path for discovery probes
        result["outcome"] = "csv_parse_error"
        result["error"] = str(exc)
        result["preview"] = preview_text(response)
        return result

    filename = Path(candidate["url"]).name
    sample = save_sample(SOURCE_ID, filename, response.content)
    result.update(
        {
            "outcome": "csv",
            "rows": int(len(df)),
            "columns": list(df.columns),
            "sample_saved_at": sample["path"],
            "sha256": sample["sha256"],
            "schema_sample_path": write_schema_sample(candidate["label"], df),
            "dates": date_summary(df),
        }
    )
    return result


def main() -> None:
    csv_results = [probe_csv_candidate(candidate) for candidate in PROBE_URLS]
    downloaded = [result for result in csv_results if result["outcome"] == "csv"]
    latest_dates = [
        result["dates"]["latest_date"]
        for result in downloaded
        if result.get("dates", {}).get("latest_date")
    ]
    summary = {
        "source_id": SOURCE_ID,
        "generated_at": now_utc_iso(),
        "readme": readme_summary(),
        "github_directory": github_directory_summary(),
        "probe_results": csv_results,
        "downloaded_csv_count": len(downloaded),
        "latest_downloaded_date": max(latest_dates) if latest_dates else None,
        "parseable_csvs_found": bool(downloaded),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
