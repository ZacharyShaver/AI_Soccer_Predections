# Plan P1: Data-Source Discovery

> **For Codex:** This is the active plan referenced by `co-op.md`. Do the NEXT single
> unchecked task only, then log + commit per the co-op rules. One source = one session.
> Steps use checkbox (`- [ ]`) syntax. Do not start modeling or build the full package here —
> this phase only proves which sources work and captures real samples + findings.

**Goal:** Empirically verify every candidate data source for the World Cup Prediction Lab —
is it reachable, what does it actually contain, what is its schema/freshness/license, and is
it useful for 2026 — then capture a small real sample and a findings note for each. Output
feeds the source registry (master plan Task 2) with *evidence*, not assumptions.

**Non-goals:** No modeling. No full ingestion pipeline. No hoarding of raw data (samples
only). No scraping any page whose terms forbid it. No spending paid API credits beyond one
tiny probe.

**Parent plan:** `2026-06-21-world-cup-prediction-lab.md` (already reviewed).

---

## Output layout

Everything from this phase lives under `discovery/`:

```text
discovery/
  probes/            # one probe script per source: probe_<id>.py
  samples/           # tiny raw samples captured by probes (GITIGNORED)
  findings/          # one committed markdown note per source: <id>-<source>.md
  DISCOVERY_REPORT.md  # aggregated summary (final task)
  sources_evidence.yaml # candidate registry rows backed by evidence (final task)
```

- **Committed:** `probes/`, `findings/`, `DISCOVERY_REPORT.md`, `sources_evidence.yaml`, and
  a *schema-only* head (≤20 rows) of each sample where license permits.
- **Gitignored:** `discovery/samples/**` (raw payloads). Add this to `.gitignore` in D0.

### Findings note template (use for every source)

```markdown
# Source: <display name> (<id>)

- **Reachable:** yes / no / partial
- **Access method:** public file / public REST / REST + API key / git repo / manual download
- **Auth required:** none / API key (env var name)
- **License / terms URL:**
- **Allowed use (1 line):**
- **Endpoint(s) / URL(s) probed:**
- **Schema (key columns/fields):**
- **Row / record count in sample:**
- **Date range / freshness (latest record date):**
- **Frozen?** (e.g. SPI) yes/no — explain
- **2026 World Cup relevance:** high / medium / low — why
- **Gotchas:** (rate limits, name mismatches, encoding, Windows path issues, thin liquidity)
- **Recommended phase:** 1 / 2 / 3 / drop
- **Retention recommendation:** raw_retention_days, bronze_retention_days
- **Sample saved at:** discovery/samples/<id>/...
- **Status:** ✅ usable / ⚠️ usable with caveats / ⛔ unusable
```

---

## Task D0: Discovery environment + scaffolding

**Files:** `discovery/probes/_common.py`, `.gitignore` (append), `discovery/findings/README.md`

- [x] **Step 1: Decide the run command (no persistent env needed)**

Probes run with `uv` pulling deps on the fly so we don't commit to the full project env yet:

```powershell
uv run --with httpx --with pandas --with openpyxl --with pyyaml python discovery/probes/probe_<id>.py
```

Confirm `uv --version` works. If `uv` is unavailable, fall back to a local `.venv` and log it.

- [x] **Step 2: Add gitignore entries**

Append to `.gitignore`:

```gitignore
discovery/samples/
.env
.venv/
__pycache__/
```

- [x] **Step 3: Create `discovery/probes/_common.py`**

Small shared helpers used by every probe:

- `save_sample(source_id, name, content_bytes)` → writes to `discovery/samples/<id>/<name>`,
  returns path + SHA-256 hash.
- `head_rows(df, n=20)` → returns first n rows for a committed schema sample.
- `now_utc_iso()` → timestamp for manifests.
- `http_get(url, **kw)` → `httpx.get` with a 30s timeout, a descriptive User-Agent, and a
  clear error message on non-200. No retries loop that could hammer a host.

- [x] **Step 4: Commit**

```powershell
git add .gitignore discovery/probes/_common.py discovery/findings/README.md
git commit -m "discovery: scaffold probe harness and outputs"
```

---

## Task D1: martj42 international results (Phase 1, essential)

**Files:** `discovery/probes/probe_martj42.py`, `discovery/findings/d1-martj42.md`

- [x] **Step 1: Probe the raw CSVs**

Fetch and inspect (raw GitHub, `master` branch):
`results.csv`, `shootouts.csv`, `goalscorers.csv`, `former_names.csv` from
`https://raw.githubusercontent.com/martj42/international_results/master/<file>`.

- [x] **Step 2: Capture facts**

For `results.csv`: columns, total row count, min/max `date`, count of rows in last 3 years,
number of distinct teams, and whether 2025–2026 matches are present (freshness check — the
master plan flags this). Save a 20-row schema sample (committed) and the full raw sample
(gitignored).

- [x] **Step 3: Write findings + commit**

Fill the findings template at `discovery/findings/d1-martj42.md`. License is on the repo
(note it). Recommend Phase 1. Commit and log to co-op.md.

---

## Task D2: openfootball World Cup 2026 fixtures (Phase 1, essential)

**Files:** `discovery/probes/probe_openfootball.py`, `discovery/findings/d2-openfootball.md`

- [x] **Step 1: Locate the 2026 fixture files**

Use the GitHub contents API (`https://api.github.com/repos/openfootball/worldcup/contents/`)
or the repo tree to find the 2026 (`2026--north-america` or similar) Football.TXT files. Log
the exact path discovered — do not assume it.

- [x] **Step 2: Capture facts**

Parse one fixture file enough to confirm: number of fixtures, presence of all 48 teams /
12 groups, date range, venues/cities present, and whether knockout bracket structure is
encoded. Save raw sample (gitignored) + a small committed excerpt.

- [x] **Step 3: Cross-check team names against D1**

List any team names in the 2026 fixtures that do NOT appear in martj42 results (these become
alias-table work later). Record them in the findings note.

- [x] **Step 4: Write findings + commit.**

---

## Task D3: FiveThirtyEight SPI (KNOWN FROZEN — verify only)

**Files:** `discovery/probes/probe_spi.py`, `discovery/findings/d3-spi.md`

- [ ] **Step 1: Attempt download**

Try the international SPI files (e.g. `spi_matches_intl.csv`,
`spi_global_rankings_intl.csv`) from the fivethirtyeight/data GitHub repo and/or the legacy
`projects.fivethirtyeight.com/soccer-api/` endpoints. Some may 404 — that is an expected
finding, not an error.

- [ ] **Step 2: Confirm frozen status**

Record the latest match/ranking date present. Confirm it stops ~2023. Explicitly mark
"Frozen? yes" and "Recommended phase: historical-benchmark only (not live)".

- [ ] **Step 3: Write findings + commit.** Do not wire SPI into any live path.

---

## Task D4: Football-Data.co.uk odds (Phase 1/2, verify coverage)

**Files:** `discovery/probes/probe_footballdata.py`, `discovery/findings/d4-footballdata.md`

- [ ] **Step 1: Survey coverage**

Football-Data.co.uk is primarily club leagues. Determine whether it has any
international / World Cup historical odds at all, or only domestic leagues. Fetch one sample
CSV/Excel (e.g. a recent league file) to confirm the odds column schema (B365H/D/A, etc.) and
test that `openpyxl` reads their `.xlsx`.

- [ ] **Step 2: Verdict on relevance**

If it lacks international coverage, mark 2026 relevance LOW and recommend it only as a
historical odds-schema reference / club-league benchmark. Be honest about this.

- [ ] **Step 3: Write findings + commit.**

---

## Task D5: Polymarket public market data (Phase 2)

**Files:** `discovery/probes/probe_polymarket.py`, `discovery/findings/d5-polymarket.md`

- [ ] **Step 1: Search for World Cup markets**

Hit the public Gamma API (`https://gamma-api.polymarket.com/events?...`) and/or search
endpoint for "World Cup" / "FIFA" events. No API key. Record how many relevant events/markets
exist and their `outcomes` / `outcomePrices` shape.

- [ ] **Step 2: Assess coverage + liquidity**

Critical per the master plan: confirm whether markets exist for (a) outright winner,
(b) individual matches, (c) groups, (d) scorelines. Note liquidity / volume where exposed.
Expect outright to exist and match/scoreline markets to be thin or absent — record reality.

- [ ] **Step 3: Map prices → probabilities**

Confirm `outcomePrices` parse as numerics and sum ≈ 1 per market. Save a sample event JSON.

- [ ] **Step 4: Write findings + commit.** Note `requires_secret: false`, retention rec.

---

## Task D6: The Odds API (Phase 2, QUOTA-LIMITED — be careful)

**Files:** `discovery/probes/probe_oddsapi.py`, `discovery/findings/d6-oddsapi.md`

- [ ] **Step 1: Key-aware probe**

Read `THE_ODDS_API_KEY` from env. If absent, SKIP gracefully and write findings from the
public docs only (sports list, soccer keys like `soccer_fifa_world_cup`, credit model). Do
NOT fail.

- [ ] **Step 2: If a key exists, spend exactly ONE cheap call**

Call `/v4/sports/` (free) to list available soccer competitions, and at most one `/v4/odds`
call for a single region+market to confirm schema. Record the `x-requests-remaining` /
`x-requests-used` response headers. Do not loop.

- [ ] **Step 3: Document the credit budget**

Restate: free tier ~500 credits/month; cost = 1 credit per region per market per call.
Estimate credits for the match-day cadence and confirm it needs a budget guard (feeds the
live runner later).

- [ ] **Step 4: Write findings + commit.**

---

## Task D7: StatsBomb open data (Phase 3)

**Files:** `discovery/probes/probe_statsbomb.py`, `discovery/findings/d7-statsbomb.md`

- [ ] **Step 1: List competitions**

Fetch `competitions.json` from the statsbomb/open-data repo. Identify which World Cup editions
and other international competitions are available (competition/season ids).

- [ ] **Step 2: Inspect one match's event file**

Pull one events JSON for a World Cup match; record event types available (shots with xG,
lineups, etc.) and approximate file size (storage planning).

- [ ] **Step 3: Note attribution requirement**

StatsBomb requires attribution when publishing analysis. Record this clearly. Mark Phase 3
(event features are deferred per master plan). Write findings + commit.

---

## Task D8: Team ratings — Elo / FIFA rankings (Phase 2, find legal feed)

**Files:** `discovery/probes/probe_ratings.py`, `discovery/findings/d8-ratings.md`

- [ ] **Step 1: Survey options**

Evaluate sources for team strength ratings: World Football Elo Ratings (eloratings.net),
FIFA/Coca-Cola world ranking, and any open dataset mirrors. For each, record whether there is
a documented API/download and whether the **terms permit reuse** (eloratings.net in
particular — check before pulling anything).

- [ ] **Step 2: Recommend the safe default**

Likely conclusion: compute our OWN Elo from D1 results (no licensing risk, fully reproducible,
matches the comparator approach) and treat external ratings as optional benchmarks only.
State this recommendation explicitly.

- [ ] **Step 3: Write findings + commit.** Pull external data only if terms clearly allow it.

---

## Task D9: News / injury RSS feeds (Phase 3, survey only)

**Files:** `discovery/findings/d9-news.md` (no probe script required unless a free RSS is tested)

- [ ] **Step 1: Survey candidate feeds**

List free, terms-compliant RSS/news options for injury/lineup signals (e.g. major sports
outlet football RSS feeds). For each: feed URL, terms, whether full text or headline-only is
permitted. No scraping of pages that forbid it.

- [ ] **Step 2: Optionally test one RSS feed**

If a clearly-permitted RSS feed exists, fetch it once and record the item schema
(title, link, pubDate). Save a small sample.

- [ ] **Step 3: Write findings + commit.** Mark Phase 3; store metadata/aggregates only.

---

## Task D10: X / Reddit compliance review (Phase 3, NO data pull)

**Files:** `discovery/findings/d10-social-compliance.md` (documentation only)

- [ ] **Step 1: Record the rules**

Summarize, with source URLs: X API access/cost model; Reddit Data API Terms (no using user
content to train ML/AI models without permission). No data is fetched in this task.

- [ ] **Step 2: State the decision**

Confirm the master plan's stance: social/news enters ONLY as compliant timestamped
aggregates, never raw user text as training data; both are deferred to Phase 3. Write findings
+ commit.

---

## Task D11: Aggregate discovery report + evidence registry (final)

**Files:** `discovery/DISCOVERY_REPORT.md`, `discovery/sources_evidence.yaml`

- [ ] **Step 1: Build the summary table**

In `DISCOVERY_REPORT.md`, one row per source: status (✅/⚠️/⛔), phase, reachable, auth, 2026
relevance, key gotcha, retention rec. Lead with a "what's actually usable for Milestone 1"
shortlist.

- [ ] **Step 2: Emit candidate registry rows**

Write `discovery/sources_evidence.yaml` with one entry per usable source using the master
plan's source-registry field shape (source_id, access_method, license_or_terms_url,
requires_secret, retention days, primary_keys, required_fields) — but only fields backed by
what D1–D10 actually observed.

- [ ] **Step 3: Recommendations to Claude**

End the report with: which sources to drop, which to promote, any surprises, and any decisions
needed from Claude before ingestion (P2) is planned. Commit and log to co-op.md.

---

## Definition of done for P1

- Every source D1–D10 has a committed findings note with the template filled in.
- `DISCOVERY_REPORT.md` gives a clear Milestone-1 shortlist.
- `sources_evidence.yaml` exists and is backed by observed evidence.
- No secrets or large raw payloads committed.
- co-op.md log updated; Claude reviews before P2 (ingestion) is written.
