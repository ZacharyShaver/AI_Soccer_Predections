from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from _common import ROOT, USER_AGENT, now_utc_iso


SOURCE_ID = "ratings"
FINDINGS_PATH = ROOT / "discovery" / "findings" / "d8-ratings.md"

ELORATINGS_HOME = "https://www.eloratings.net/"
ELORATINGS_ABOUT = "https://www.eloratings.net/about"
ELORATINGS_ROBOTS = "https://www.eloratings.net/robots.txt"
ELORATINGS_TERMS = "https://www.eloratings.net/terms"

FIFA_RANKING = "https://inside.fifa.com/fifa-world-ranking/men"
FIFA_TERMS = "https://inside.fifa.com/terms-of-service"
FIFA_ROBOTS = "https://inside.fifa.com/robots.txt"

KAGGLE_SEARCH = "https://www.kaggle.com/datasets?search=fifa%20ranking"
KAGGLE_TERMS = "https://www.kaggle.com/terms"

GITHUB_API = "https://api.github.com"

MIRROR_REPOS = [
    "JGravier/soccer-elo",
    "samuraitruong/fifa-ranking-data",
    "adamtpang/worldcupelo.com",
]


@dataclass(frozen=True)
class UrlCheck:
    url: str
    status_code: int | None
    final_url: str | None
    content_type: str | None
    bytes: int | None
    valid_shape: bool
    note: str


def compact_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch(client: httpx.Client, url: str) -> tuple[UrlCheck, str]:
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return (
            UrlCheck(
                url=url,
                status_code=None,
                final_url=None,
                content_type=None,
                bytes=None,
                valid_shape=False,
                note=f"request failed: {type(exc).__name__}: {exc}",
            ),
            "",
        )

    content_type = response.headers.get("content-type")
    text = response.text if response.content else ""
    lower_content_type = (content_type or "").lower()
    stripped = text.lstrip().lower()
    is_html = "text/html" in lower_content_type or stripped.startswith("<!doctype html")
    is_text = "text/plain" in lower_content_type
    valid_shape = response.status_code == 200 and (is_html or is_text)
    note = "metadata/page response shape validated" if valid_shape else "not a valid metadata/page response"
    return (
        UrlCheck(
            url=url,
            status_code=response.status_code,
            final_url=str(response.url),
            content_type=content_type,
            bytes=len(response.content),
            valid_shape=valid_shape,
            note=note,
        ),
        text,
    )


def github_get_json(client: httpx.Client, path: str, params: dict[str, str] | None = None) -> tuple[Any, UrlCheck]:
    url = f"{GITHUB_API}{path}"
    response = client.get(url, params=params)
    content_type = response.headers.get("content-type", "")
    valid_shape = False
    payload: Any = None
    note = "not JSON"

    if response.status_code == 200 and "application/json" in content_type.lower():
        payload = response.json()
        valid_shape = True
        note = "GitHub metadata JSON shape validated"

    return payload, UrlCheck(
        url=str(response.url),
        status_code=response.status_code,
        final_url=str(response.url),
        content_type=content_type,
        bytes=len(response.content),
        valid_shape=valid_shape,
        note=note,
    )


def extract_fifa_freshness(page_text: str) -> dict[str, str | None]:
    official_match = re.search(r'"lastUpdateDate":"([^"]+)"', page_text)
    next_match = re.search(r'"nextUpdateDate":"([^"]+)"', page_text)
    if official_match or next_match:
        return {
            "last_official_update": official_match.group(1) if official_match else None,
            "next_official_update": next_match.group(1) if next_match else None,
        }

    official_match = re.search(r"Last official update:\s*([A-Za-z0-9, ]{3,40})", page_text)
    next_match = re.search(r"Next official update:\s*([A-Za-z0-9, ]{3,40})", page_text)
    return {
        "last_official_update": compact_ws(official_match.group(1)) if official_match else None,
        "next_official_update": compact_ws(next_match.group(1)) if next_match else None,
    }


def extract_fifa_terms_flags(terms_text: str) -> dict[str, bool]:
    lower = terms_text.lower()
    return {
        "content_includes_data_feeds_and_api": all(
            phrase in lower for phrase in ["data, text", "fifa feeds", "fifa api"]
        ),
        "private_non_commercial_only": "privately for non-commercial purposes" in lower,
        "robots_or_automated_programmes_restricted": "robots, spiders or other automated" in lower,
        "api_disallowed_in_robots": False,
    }


def repo_summary(client: httpx.Client, repo: str) -> dict[str, Any]:
    repo_payload, repo_check = github_get_json(client, f"/repos/{repo}")
    contents_payload, contents_check = github_get_json(client, f"/repos/{repo}/contents")

    content_names: list[str] = []
    if isinstance(contents_payload, list):
        for item in contents_payload:
            if isinstance(item, dict) and "name" in item:
                content_names.append(str(item["name"]))

    readme_text = ""
    for candidate in ("README.md", "readme.md"):
        payload, check = github_get_json(client, f"/repos/{repo}/contents/{candidate}")
        if isinstance(payload, dict) and payload.get("download_url"):
            readme_response = client.get(payload["download_url"])
            if readme_response.status_code == 200 and len(readme_response.content) < 25000:
                readme_text = readme_response.text
            break
        if check.status_code not in (200, 404):
            break

    license_obj = repo_payload.get("license") if isinstance(repo_payload, dict) else None
    return {
        "repo": repo,
        "html_url": repo_payload.get("html_url") if isinstance(repo_payload, dict) else None,
        "license_spdx": license_obj.get("spdx_id") if isinstance(license_obj, dict) else None,
        "license_name": license_obj.get("name") if isinstance(license_obj, dict) else None,
        "pushed_at": repo_payload.get("pushed_at") if isinstance(repo_payload, dict) else None,
        "updated_at": repo_payload.get("updated_at") if isinstance(repo_payload, dict) else None,
        "description": repo_payload.get("description") if isinstance(repo_payload, dict) else None,
        "top_level_files": content_names[:15],
        "repo_check": repo_check.__dict__,
        "contents_check": contents_check.__dict__,
        "readme_mentions_eloratings": "eloratings" in readme_text.lower(),
        "readme_mentions_fifa": "fifa" in readme_text.lower(),
        "readme_mentions_api": "api" in readme_text.lower(),
        "readme_excerpt": compact_ws(readme_text[:1000]) if readme_text else None,
    }


def github_search_summary(client: httpx.Client) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for query in ("fifa ranking csv", "world football elo ratings", "eloratings"):
        payload, check = github_get_json(client, "/search/repositories", {"q": query})
        items = payload.get("items", []) if isinstance(payload, dict) else []
        summaries.append(
            {
                "query": query,
                "total_count": payload.get("total_count") if isinstance(payload, dict) else None,
                "check": check.__dict__,
                "top_results": [
                    {
                        "full_name": item.get("full_name"),
                        "license_spdx": (item.get("license") or {}).get("spdx_id"),
                        "description": item.get("description"),
                    }
                    for item in items[:5]
                    if isinstance(item, dict)
                ],
            }
        )
    return summaries


def check_rows_md(checks: list[UrlCheck]) -> str:
    rows = ["| URL | Status | Content type | Shape validation | Note |", "| --- | ---: | --- | --- | --- |"]
    for check in checks:
        rows.append(
            "| "
            + " | ".join(
                [
                    check.url,
                    str(check.status_code),
                    check.content_type or "",
                    "yes" if check.valid_shape else "no",
                    check.note,
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def mirror_rows_md(repo_summaries: list[dict[str, Any]]) -> str:
    rows = [
        "| Mirror | License metadata | Freshness | Terms position | Verdict |",
        "| --- | --- | --- | --- | --- |",
    ]
    for repo in repo_summaries:
        name = repo["repo"]
        license_text = repo["license_spdx"] or "none/unknown"
        freshness = repo["pushed_at"] or "unknown"
        if name == "JGravier/soccer-elo":
            terms = "Repository advertises CC-BY, but README says data was scraped/compiled from eloratings.net, whose reuse terms were not found."
            verdict = "Do not use without upstream permission review."
        elif name == "samuraitruong/fifa-ranking-data":
            terms = "Apache-2.0 covers repository code, but repository metadata describes collection of FIFA ranking data; FIFA terms do not grant redistribution of ranking data."
            verdict = "Do not use as a data source."
        else:
            terms = "README documents no-key JSON endpoints, but repo has no license metadata and says ratings are based on eloratings.net."
            verdict = "Do not use as a data source."
        rows.append(f"| `{name}` | {license_text} | {freshness} | {terms} | {verdict} |")
    return "\n".join(rows)


def write_findings(summary: dict[str, Any]) -> None:
    fifa = summary["fifa"]
    content = f"""# Source: Team ratings - Elo / FIFA rankings (ratings)

- **Reachable:** partial. Source pages and metadata endpoints were reachable, but no rating table was downloaded because reuse rights were not clear enough.
- **Access method:** public website pages plus GitHub metadata survey only; no committed or raw rating data sample.
- **Auth required:** none for surveyed pages/metadata. Kaggle CLI/API was not available locally, and no Kaggle data was pulled.
- **requires_secret:** false for this survey.
- **License / terms URL:** {ELORATINGS_HOME}, {ELORATINGS_ROBOTS}, {ELORATINGS_TERMS}, {FIFA_TERMS}, {FIFA_ROBOTS}, {KAGGLE_TERMS}, and the GitHub mirror URLs listed below.
- **Allowed use (1 line):** Safe default is to compute our own Elo from D1 martj42 results; external ratings are optional benchmarks only when a specific source has clear reuse permission and documented access.
- **Endpoint(s) / URL(s) probed:**
  - World Football Elo Ratings: `{ELORATINGS_ROBOTS}`, `{ELORATINGS_TERMS}`, `{ELORATINGS_HOME}`, `{ELORATINGS_ABOUT}`
  - FIFA ranking: `{FIFA_ROBOTS}`, `{FIFA_TERMS}`, `{FIFA_RANKING}`
  - Kaggle mirror search/terms: `{KAGGLE_SEARCH}`, `{KAGGLE_TERMS}`
  - GitHub metadata/search API for representative FIFA-ranking and Elo mirrors.
- **Schema (key columns/fields):** none accepted as legal data. If we compute our own Elo, expected internal fields are `match_id`/date/order, `home_team`, `away_team`, pre-match home/away Elo, expected score, result, K/tournament weight, home/neutral adjustment, goal-difference adjustment if used, and post-match ratings.
- **Row / record count in sample:** 0 rating records downloaded. GitHub metadata search returned counts only: {summary['github_search_counts']}.
- **Date range / freshness (latest record date):** FIFA public ranking page reports last official update `{fifa['freshness']['last_official_update']}` and next official update `{fifa['freshness']['next_official_update']}`. GitHub mirror freshness is listed below. World Football Elo homepage did not expose a documented update cadence in the fetched metadata pages.
- **Frozen?** no for official FIFA and World Football Elo pages, but no legally selected data feed was identified. Several mirrors are stale or one-off snapshots.
- **2026 World Cup relevance:** high as benchmark/rating concepts, but external feeds should not be Milestone 1 dependencies. Our own Elo from D1 results is directly relevant, reproducible, and avoids licensing risk.
- **Gotchas:** A HTTP 200 was not treated as valid rating data. FIFA serves ranking and terms pages as HTML, robots.txt disallows `/api/` on `inside.fifa.com`, and FIFA terms reserve content/data/API rights while limiting platform content use to private non-commercial access unless additional permission exists. eloratings.net had no robots.txt or terms page at the checked URLs, and the homepage did not show a license or documented bulk/API feed. GitHub/Kaggle mirrors may have code licenses that do not cure upstream data rights.
- **Recommended phase:** 2 for optional benchmark snapshots only; core Elo implementation belongs in Milestone 1 from D1 results.
- **Retention recommendation:** raw_retention_days=0 for external rating sources until a license-approved feed exists. For our own Elo, raw_retention_days=3650 for D1 source results per D1 policy and bronze_retention_days=3650 for deterministic internal rating snapshots/features.
- **Sample saved at:** none. No external rating data was downloaded.
- **Status:** usable with caveats for concept/benchmark survey; no external feed selected.

## Recommendation

Use **our own calibrated Elo computed from D1 martj42 international results** as the project bar. This has no external rating licensing risk, is fully reproducible, can be rebuilt from versioned match results, and matches the master plan's comparator approach: fancier models must beat plain calibrated Elo on walk-forward RPS/log loss before promotion.

External World Football Elo, FIFA ranking, Kaggle mirrors, or GitHub mirrors should be treated only as optional benchmarks. They should enter the pipeline only after a source-specific license and access review says reuse/redistribution is allowed.

## Terms and access evidence

{check_rows_md([UrlCheck(**check) for check in summary['url_checks']])}

## Source-specific findings

### World Football Elo Ratings

- Documented API or bulk download: not found in the checked public pages.
- Terms permit reuse/redistribution: not established. `{ELORATINGS_ROBOTS}` and `{ELORATINGS_TERMS}` returned 404 in this run; the homepage/about page did not expose a license or reuse grant.
- Freshness / update cadence: the site appears live, but no documented cadence was found in pages fetched by this probe.
- Decision: do not download or redistribute eloratings.net rating data in P1. If Claude wants this benchmark later, ask for explicit permission or find a clearly licensed derivative with credible provenance.

### FIFA / Coca-Cola Men's World Ranking

- Documented API or bulk download: no public documented ranking API or bulk export was found. The public ranking page is HTML and robots.txt disallows `/api/` on `inside.fifa.com`.
- Terms permit reuse/redistribution: no. FIFA terms define platform content to include information, data, feeds, and API, reserve rights, and limit content access/use to private non-commercial platform use unless separately permitted.
- Freshness / update cadence: page reported last official update `{fifa['freshness']['last_official_update']}` and next official update `{fifa['freshness']['next_official_update']}`.
- Decision: do not scrape FIFA ranking data or use undocumented FIFA APIs. A manually reviewed, permissioned FIFA export could be an optional benchmark later, but is not selected now.

### Open mirrors

{mirror_rows_md(summary['github_repos'])}

Kaggle was reviewed only at the search/terms level because no local Kaggle CLI/API credentials were available and dataset pages are per-dataset/license specific. Treat Kaggle mirrors as usable only when the exact dataset page shows an open license and the upstream provenance is compatible with redistribution. No Kaggle data was downloaded.

## Probe output highlights

- Required command path: `uv run --with httpx python discovery/probes/probe_ratings.py`
- External rating records downloaded: 0
- Raw sample created: no
- Terms-first rule applied: robots/terms/metadata pages were checked before any data-like endpoint, and no data-like endpoint was called for eloratings.net or FIFA.
"""
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FINDINGS_PATH.write_text(content, encoding="utf-8")


def main() -> None:
    headers = {
        "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.8",
        "User-Agent": USER_AGENT,
    }
    generated_at = now_utc_iso()

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        url_checks: list[UrlCheck] = []
        page_text: dict[str, str] = {}
        for url in (
            ELORATINGS_ROBOTS,
            ELORATINGS_TERMS,
            ELORATINGS_HOME,
            ELORATINGS_ABOUT,
            FIFA_ROBOTS,
            FIFA_TERMS,
            FIFA_RANKING,
            KAGGLE_TERMS,
            KAGGLE_SEARCH,
        ):
            check, text = fetch(client, url)
            url_checks.append(check)
            page_text[url] = text

        fifa_terms_flags = extract_fifa_terms_flags(page_text.get(FIFA_TERMS, ""))
        fifa_terms_flags["api_disallowed_in_robots"] = "disallow: /api/" in page_text.get(
            FIFA_ROBOTS, ""
        ).lower()

        github_search = github_search_summary(client)
        github_repos = [repo_summary(client, repo) for repo in MIRROR_REPOS]

    summary = {
        "source_id": SOURCE_ID,
        "generated_at": generated_at,
        "external_rating_records_downloaded": 0,
        "raw_sample_created": False,
        "url_checks": [check.__dict__ for check in url_checks],
        "fifa": {
            "freshness": extract_fifa_freshness(page_text.get(FIFA_RANKING, "")),
            "terms_flags": fifa_terms_flags,
        },
        "github_search": github_search,
        "github_search_counts": {
            item["query"]: item["total_count"] for item in github_search
        },
        "github_repos": github_repos,
        "recommendation": "compute own calibrated Elo from D1 martj42 results; external ratings are optional benchmarks only where terms allow",
        "findings_path": FINDINGS_PATH.relative_to(ROOT).as_posix(),
    }
    write_findings(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
