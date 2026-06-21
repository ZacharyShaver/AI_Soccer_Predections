# Source: Team ratings - Elo / FIFA rankings (ratings)

- **Reachable:** partial. Source pages and metadata endpoints were reachable, but no rating table was downloaded because reuse rights were not clear enough.
- **Access method:** public website pages plus GitHub metadata survey only; no committed or raw rating data sample.
- **Auth required:** none for surveyed pages/metadata. Kaggle CLI/API was not available locally, and no Kaggle data was pulled.
- **requires_secret:** false for this survey.
- **License / terms URL:** https://www.eloratings.net/, https://www.eloratings.net/robots.txt, https://www.eloratings.net/terms, https://inside.fifa.com/terms-of-service, https://inside.fifa.com/robots.txt, https://www.kaggle.com/terms, and the GitHub mirror URLs listed below.
- **Allowed use (1 line):** Safe default is to compute our own Elo from D1 martj42 results; external ratings are optional benchmarks only when a specific source has clear reuse permission and documented access.
- **Endpoint(s) / URL(s) probed:**
  - World Football Elo Ratings: `https://www.eloratings.net/robots.txt`, `https://www.eloratings.net/terms`, `https://www.eloratings.net/`, `https://www.eloratings.net/about`
  - FIFA ranking: `https://inside.fifa.com/robots.txt`, `https://inside.fifa.com/terms-of-service`, `https://inside.fifa.com/fifa-world-ranking/men`
  - Kaggle mirror search/terms: `https://www.kaggle.com/datasets?search=fifa%20ranking`, `https://www.kaggle.com/terms`
  - GitHub metadata/search API for representative FIFA-ranking and Elo mirrors.
- **Schema (key columns/fields):** none accepted as legal data. If we compute our own Elo, expected internal fields are `match_id`/date/order, `home_team`, `away_team`, pre-match home/away Elo, expected score, result, K/tournament weight, home/neutral adjustment, goal-difference adjustment if used, and post-match ratings.
- **Row / record count in sample:** 0 rating records downloaded. GitHub metadata search returned counts only: {'fifa ranking csv': 6, 'world football elo ratings': 29, 'eloratings': 19}.
- **Date range / freshness (latest record date):** FIFA public ranking page reports last official update `2026-06-11T10:00:59.636Z` and next official update `2026-07-20T00:00:00.000Z`. GitHub mirror freshness is listed below. World Football Elo homepage did not expose a documented update cadence in the fetched metadata pages.
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

| URL | Status | Content type | Shape validation | Note |
| --- | ---: | --- | --- | --- |
| https://www.eloratings.net/robots.txt | 404 | text/html | no | not a valid metadata/page response |
| https://www.eloratings.net/terms | 404 | text/html | no | not a valid metadata/page response |
| https://www.eloratings.net/ | 200 | text/html | yes | metadata/page response shape validated |
| https://www.eloratings.net/about | 200 |  | yes | metadata/page response shape validated |
| https://inside.fifa.com/robots.txt | 200 | text/plain; charset=UTF-8 | yes | metadata/page response shape validated |
| https://inside.fifa.com/terms-of-service | 200 | text/html; charset=utf-8 | yes | metadata/page response shape validated |
| https://inside.fifa.com/fifa-world-ranking/men | 200 | text/html; charset=utf-8 | yes | metadata/page response shape validated |
| https://www.kaggle.com/terms | 200 | text/html; charset=utf-8 | yes | metadata/page response shape validated |
| https://www.kaggle.com/datasets?search=fifa%20ranking | 200 | text/html; charset=utf-8 | yes | metadata/page response shape validated |

## Source-specific findings

### World Football Elo Ratings

- Documented API or bulk download: not found in the checked public pages.
- Terms permit reuse/redistribution: not established. `https://www.eloratings.net/robots.txt` and `https://www.eloratings.net/terms` returned 404 in this run; the homepage/about page did not expose a license or reuse grant.
- Freshness / update cadence: the site appears live, but no documented cadence was found in pages fetched by this probe.
- Decision: do not download or redistribute eloratings.net rating data in P1. If Claude wants this benchmark later, ask for explicit permission or find a clearly licensed derivative with credible provenance.

### FIFA / Coca-Cola Men's World Ranking

- Documented API or bulk download: no public documented ranking API or bulk export was found. The public ranking page is HTML and robots.txt disallows `/api/` on `inside.fifa.com`.
- Terms permit reuse/redistribution: no. FIFA terms define platform content to include information, data, feeds, and API, reserve rights, and limit content access/use to private non-commercial platform use unless separately permitted.
- Freshness / update cadence: page reported last official update `2026-06-11T10:00:59.636Z` and next official update `2026-07-20T00:00:00.000Z`.
- Decision: do not scrape FIFA ranking data or use undocumented FIFA APIs. A manually reviewed, permissioned FIFA export could be an optional benchmark later, but is not selected now.

### Open mirrors

| Mirror | License metadata | Freshness | Terms position | Verdict |
| --- | --- | --- | --- | --- |
| `JGravier/soccer-elo` | NOASSERTION | 2024-03-24T12:28:48Z | Repository advertises CC-BY, but README says data was scraped/compiled from eloratings.net, whose reuse terms were not found. | Do not use without upstream permission review. |
| `samuraitruong/fifa-ranking-data` | Apache-2.0 | 2019-12-13T05:25:50Z | Apache-2.0 covers repository code, but repository metadata describes collection of FIFA ranking data; FIFA terms do not grant redistribution of ranking data. | Do not use as a data source. |
| `adamtpang/worldcupelo.com` | none/unknown | 2026-06-09T04:01:34Z | README documents no-key JSON endpoints, but repo has no license metadata and says ratings are based on eloratings.net. | Do not use as a data source. |

Kaggle was reviewed only at the search/terms level because no local Kaggle CLI/API credentials were available and dataset pages are per-dataset/license specific. Treat Kaggle mirrors as usable only when the exact dataset page shows an open license and the upstream provenance is compatible with redistribution. No Kaggle data was downloaded.

## Probe output highlights

- Required command path: `uv run --with httpx python discovery/probes/probe_ratings.py`
- External rating records downloaded: 0
- Raw sample created: no
- Terms-first rule applied: robots/terms/metadata pages were checked before any data-like endpoint, and no data-like endpoint was called for eloratings.net or FIFA.
