from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd

from _common import ROOT, now_utc_iso, save_sample


SOURCE_ID = "footballdata"
BASE_URL = "https://www.football-data.co.uk/"
DATA_URL = urljoin(BASE_URL, "data.php")
DOWNLOADS_URL = urljoin(BASE_URL, "downloadm.php")
ENGLAND_URL = urljoin(BASE_URL, "englandm.php")
ALL_NEW_DATA_URL = urljoin(BASE_URL, "all_new_data.php")
NOTES_URL = urljoin(BASE_URL, "notes.txt")
WORLD_CUP_URL = urljoin(BASE_URL, "WorldCup2026.xlsx")
LEAGUE_SAMPLE_URL = urljoin(BASE_URL, "mmz4281/2526/E0.csv")
FINDINGS_DIR = ROOT / "discovery" / "findings"
COUNTRY_PAGE_NAMES = {
    "englandm.php",
    "scotlandm.php",
    "germanym.php",
    "italym.php",
    "spainm.php",
    "francem.php",
    "netherlandsm.php",
    "belgiumm.php",
    "portugalm.php",
    "turkeym.php",
    "greecem.php",
    "argentina.php",
    "austria.php",
    "brazil.php",
    "china.php",
    "denmark.php",
    "finland.php",
    "ireland.php",
    "japan.php",
    "mexico.php",
    "norway.php",
    "poland.php",
    "romania.php",
    "russia.php",
    "sweden.php",
    "switzerland.php",
    "usa.php",
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        parsed = {key.lower(): value or "" for key, value in attrs}
        href = parsed.get("href")
        if href:
            self.links.append({"href": href, "title": parsed.get("title", "")})


def fetch(url: str, accept: str = "*/*") -> Any:
    import httpx

    headers = {
        "Accept": accept,
        "User-Agent": "AI-Soccer-Predictions discovery probe (+local research; contact: repo owner)",
    }
    return httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)


def response_facts(response: Any) -> dict[str, Any]:
    return {
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "final_url": str(response.url),
        "bytes": len(response.content),
    }


def preview_text(response: Any, limit: int = 160) -> str:
    return response.text[:limit].replace("\r", " ").replace("\n", " ").strip()


def parse_links(page_url: str, content: str) -> list[str]:
    parser = LinkParser()
    parser.feed(content)
    return sorted({urljoin(page_url, link["href"]) for link in parser.links})


def page_summary(url: str) -> dict[str, Any]:
    response = fetch(url, "text/html,text/plain,*/*")
    summary = {"url": url, **response_facts(response)}
    if response.status_code != 200:
        summary["outcome"] = "http_error"
        summary["preview"] = preview_text(response)
        return summary

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type and "text/plain" not in content_type:
        summary["outcome"] = "non_text_200"
        summary["preview"] = response.content[:80].hex()
        return summary

    links = parse_links(url, response.text)
    summary.update(
        {
            "outcome": "text_page",
            "link_count": len(links),
            "worldcup_links": [link for link in links if "worldcup" in link.lower()],
            "xlsx_links": [link for link in links if link.lower().endswith(".xlsx")],
            "csv_links": [link for link in links if link.lower().endswith(".csv")],
            "league_country_page_links": [
                link for link in links if Path(link).name.lower() in COUNTRY_PAGE_NAMES
            ],
        }
    )
    return summary


def looks_like_csv(response: Any, expected_prefix: str) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    first_line = response.text.splitlines()[0].lstrip("\ufeff") if response.text.splitlines() else ""
    return ("csv" in content_type or "text/plain" in content_type) and first_line.startswith(
        expected_prefix
    )


def looks_like_xlsx(response: Any) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return (
        "spreadsheetml" in content_type
        or "application/vnd.ms-excel" in content_type
        or response.content.startswith(b"PK\x03\x04")
    )


def write_schema_sample(path_name: str, df: pd.DataFrame) -> str:
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = FINDINGS_DIR / path_name
    df.head(20).to_csv(path, index=False)
    return path.relative_to(ROOT).as_posix()


def date_summary(df: pd.DataFrame, column: str) -> dict[str, str | int | None]:
    parsed = pd.to_datetime(df[column], errors="coerce", dayfirst=True)
    if not parsed.notna().any():
        return {"min": None, "max": None, "non_null": 0}
    return {
        "min": parsed.min().date().isoformat(),
        "max": parsed.max().date().isoformat(),
        "non_null": int(parsed.notna().sum()),
    }


def odds_columns(columns: list[str]) -> dict[str, list[str]]:
    return {
        "home_draw_away_opening_or_standard": [
            col
            for col in columns
            if col.endswith(("H", "D", "A"))
            and not col.endswith(("CH", "CD", "CA"))
            and ">" not in col
            and "<" not in col
            and "AH" not in col
        ],
        "home_draw_away_closing": [
            col
            for col in columns
            if col.endswith(("CH", "CD", "CA"))
            or col in {"B365CH", "B365CD", "B365CA", "MaxCH", "MaxCD", "MaxCA", "AvgCH", "AvgCD", "AvgCA"}
        ],
        "over_under": [col for col in columns if ">2.5" in col or "<2.5" in col],
        "asian_handicap": [col for col in columns if "AH" in col or col in {"AHh", "AHCh"}],
    }


def probe_league_csv() -> dict[str, Any]:
    response = fetch(LEAGUE_SAMPLE_URL, "text/csv,text/plain,*/*")
    result = {"url": LEAGUE_SAMPLE_URL, **response_facts(response)}
    if response.status_code != 200:
        result["outcome"] = "http_error"
        result["preview"] = preview_text(response)
        return result
    if not looks_like_csv(response, "Div,Date,"):
        result["outcome"] = "non_csv_200"
        result["preview"] = preview_text(response)
        return result

    df = pd.read_csv(BytesIO(response.content), encoding="utf-8-sig")
    sample = save_sample(SOURCE_ID, "E0-2526.csv", response.content)
    result.update(
        {
            "outcome": "csv",
            "sample_saved_at": sample["path"],
            "sha256": sample["sha256"],
            "rows": int(len(df)),
            "columns": list(df.columns),
            "column_count": int(len(df.columns)),
            "date_range": date_summary(df, "Date"),
            "odds_columns": odds_columns(list(df.columns)),
            "schema_sample_path": write_schema_sample(
                "d4-footballdata-e0-2526-schema-sample.csv", df
            ),
        }
    )
    return result


def probe_world_cup_workbook() -> dict[str, Any]:
    response = fetch(WORLD_CUP_URL, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*")
    result = {"url": WORLD_CUP_URL, **response_facts(response)}
    if response.status_code != 200:
        result["outcome"] = "http_error"
        result["preview"] = preview_text(response)
        return result
    if not looks_like_xlsx(response):
        result["outcome"] = "non_xlsx_200"
        result["preview_hex"] = response.content[:80].hex()
        return result

    sample = save_sample(SOURCE_ID, "WorldCup2026.xlsx", response.content)
    workbook = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")
    sheets: dict[str, Any] = {}
    first_sheet_sample_path: str | None = None
    for sheet_name in workbook.sheet_names:
        df = pd.read_excel(workbook, sheet_name=sheet_name)
        sheet_summary = {
            "rows": int(len(df)),
            "column_count": int(len(df.columns)),
            "columns": list(df.columns),
            "odds_columns": odds_columns([str(column) for column in df.columns]),
        }
        if "Date" in df.columns:
            sheet_summary["date_range"] = date_summary(df, "Date")
        sheets[sheet_name] = sheet_summary
        if first_sheet_sample_path is None:
            first_sheet_sample_path = write_schema_sample(
                "d4-footballdata-worldcup2026-schema-sample.csv", df
            )

    result.update(
        {
            "outcome": "xlsx",
            "sample_saved_at": sample["path"],
            "sha256": sample["sha256"],
            "openpyxl_read_ok": True,
            "sheet_names": workbook.sheet_names,
            "sheets": sheets,
            "schema_sample_path": first_sheet_sample_path,
        }
    )
    return result


def notes_summary() -> dict[str, Any]:
    response = fetch(NOTES_URL, "text/plain,*/*")
    result = {"url": NOTES_URL, **response_facts(response)}
    if response.status_code != 200:
        result["outcome"] = "http_error"
        result["preview"] = preview_text(response)
        return result
    content_type = response.headers.get("content-type", "").lower()
    if "text/plain" not in content_type:
        result["outcome"] = "non_text_200"
        result["preview"] = preview_text(response)
        return result

    text = response.text
    result.update(
        {
            "outcome": "text",
            "mentions_bet365": "Bet365" in text or "B365" in text,
            "mentions_closing": "closing" in text.lower(),
            "key_lines": [
                line.strip()
                for line in text.splitlines()
                if line.strip().startswith(("B365", "Max", "Avg", "C", "BbMx", "BbAv"))
            ][:40],
        }
    )
    return result


def main() -> None:
    pages = {
        "data": page_summary(DATA_URL),
        "downloads": page_summary(DOWNLOADS_URL),
        "england": page_summary(ENGLAND_URL),
        "all_new_data": page_summary(ALL_NEW_DATA_URL),
    }
    worldcup_links = sorted(
        {
            link
            for page in pages.values()
            for link in page.get("worldcup_links", [])
        }
    )
    country_pages = sorted(
        {
            link.lower()
            for page in pages.values()
            for link in page.get("league_country_page_links", [])
        }
    )
    league_csv_links = pages["england"].get("csv_links", [])
    summary = {
        "source_id": SOURCE_ID,
        "generated_at": now_utc_iso(),
        "pages": pages,
        "coverage": {
            "documented_worldcup_links": worldcup_links,
            "worldcup_link_count": len(worldcup_links),
            "documented_country_league_pages": country_pages,
            "documented_country_league_page_count": len(country_pages),
            "england_csv_link_count": len(league_csv_links),
            "england_2526_csv_links": [
                link for link in league_csv_links if "/2526/" in link
            ],
        },
        "notes": notes_summary(),
        "world_cup_workbook": probe_world_cup_workbook(),
        "league_csv_sample": probe_league_csv(),
    }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
