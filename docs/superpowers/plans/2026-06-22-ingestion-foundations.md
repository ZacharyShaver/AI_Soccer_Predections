# Plan P2: Ingestion Foundations (Milestone 1 data layer)

> Bite-sized, Codex-executable slices of the master plan
> (`2026-06-21-world-cup-prediction-lab.md`), grounded in the **completed P1 discovery**
> findings (`discovery/DISCOVERY_REPORT.md`, `discovery/sources_evidence.yaml`).
> Steps use checkbox (`- [ ]`) syntax. One task per Codex session. Codex does NOT run git —
> Claude verifies via PowerShell and commits (see `co-op.md`).

## Scope and goal

Build the **trustworthy data layer** for the Elo-first vertical slice: from raw source files to a
clean, normalized, leakage-aware **silver `matches` + `fixtures`** dataset, with a source-contract
registry and a team-alias resolver. **No modeling here** — Elo and predictions are P3.

**Milestone-1 sources only** (from discovery):
- `international_results_martj42` (D1) — historical international results → training history.
- `openfootball_worldcup_2026` (D2) — 2026 fixtures + bracket.
- `internal_elo_from_martj42` (D8 decision) — derived in P3, but its source rows come from here.

Phase 2 benchmark sources (Polymarket / Football-Data / The Odds API) and Phase 3 sources
(StatsBomb / GDELT / social) are **explicitly out of scope for P2** and get their own later plan.

## Design decisions locked from the discovery report (so Codex does not re-decide)

These resolve the "Decisions Needed Before P2" list in `discovery/DISCOVERY_REPORT.md`:

1. **Fixtures vs results split (from D1).** `results.csv` mixes completed matches and ~36
   blank-score future 2026 fixtures. Ingestion splits on score presence: rows with **both**
   `home_score` and `away_score` populated → `matches` (completed, model labels); rows with a
   blank score → routed to the **fixtures** path only, never used as result labels.
2. **Team alias table (from D2).** Exact-match resolver, canonical IDs. Seed with the D2
   mismatches (`Bosnia & Herzegovina`→`Bosnia and Herzegovina`, `USA`→`United States`) plus the
   FIFA display-name variants (`Korea Republic`, `IR Iran`, `Cabo Verde`, `Congo DR`,
   `Cote d'Ivoire`, `Czechia`/`Czech Republic`, `Turkiye`/`Turkey`, `Ivory Coast`, `DR Congo`).
   Unknown names fail loudly (no silent fuzzy fallback in Milestone 1).
3. **De-vig (from D5):** Phase 2 concern. Out of scope for P2; recorded in the registry note only.
4. **Football-Data non-CC0 (from D4):** Phase 2. When ingested later: raw files stay local /
   gitignored, no redistribution, per-file odds column maps. Recorded in registry only for P2.
5. **`THE_ODDS_API_KEY` (from D6):** Phase 2 / live. Optional; not needed for P2.
6. **News/social (D9/D10):** Phase 3 deferred, off the probability path. Not in P2.

## Conventions

- **Package root:** `worldcup_prediction_lab/` (only `README.md` exists today). Use the master
  plan's "Repository And File Plan" layout exactly.
- **Tooling:** `uv` for deps; `pytest` for tests; DuckDB + partitioned Parquet for analytical data;
  Polars or Pandas for parsing (match master plan / keep deps minimal).
- **Medallion layers:** `raw` (immutable snapshot + hash) → `bronze` (parsed, source-shaped) →
  `silver` (normalized entities, alias-resolved). `gold` is P3.
- **Determinism:** stable sort + canonical column order; manifests carry source URL, ingest UTC
  time, row count, and SHA-256 of the raw payload.
- **Secrets:** none required for P2. Never commit `.env`. Raw data under `data/raw/**` is
  gitignored; tiny test fixtures live in `tests/` and ARE committed.
- **Tests-first** where the master plan specifies it (registry, aliases, ingestion parsers).

## Outputs

- `worldcup_prediction_lab/` package scaffold (dirs, `pyproject.toml`, `.env.example`).
- `config/sources.yaml` + `src/wc_predictor/data/source_registry.py` (+ tests).
- `config/team_aliases.csv` + `src/wc_predictor/data/team_aliases.py` (+ tests).
- `src/wc_predictor/data/ingest_international_results.py` (+ tests) → bronze + silver `matches`/`fixtures`.
- `src/wc_predictor/data/ingest_openfootball_worldcup.py` (+ tests) → silver `fixtures` (groups + knockout).
- `reports/data_quality/` ingestion + DQ summary; manifests under each layer.

---

## Task I0: Package scaffold

**Files:** `worldcup_prediction_lab/pyproject.toml`, `.env.example`, the medallion + reports + runs
`.gitkeep` dirs, `src/wc_predictor/__init__.py`, `src/wc_predictor/config/settings.py`.

- [x] **Step 1: Create the directory + file skeleton**

Create exactly the structure from the master plan "Files and folders to create" (data/raw|bronze|
silver|gold, reports/{data_quality,model_cards,backtests}, runs/{predictions,evaluations,models},
config/, src/wc_predictor/{config,data}). Use `.gitkeep` for empty dirs.

- [x] **Step 2: pyproject + settings**

Minimal `pyproject.toml` (package `wc_predictor`, src layout, deps: pandas or polars, duckdb,
pyyaml, pydantic or dataclasses, pytest, httpx). `settings.py` exposes repo-root-relative paths to
each medallion layer + config dir. `.env.example` lists only future-optional secret NAMES
(`THE_ODDS_API_KEY=`) — no values.

- [x] **Step 3: gitignore data layers**

Ensure `worldcup_prediction_lab/data/raw/**`, `bronze/**`, `silver/**`, `gold/**` are gitignored
(keep `.gitkeep`). Confirm `.env` is ignored. Run `uv run python -c "import wc_predictor"` (or
py_compile) to confirm the package imports.

- [x] **Step 4: Findings/log.** Append to co-op log; Claude commits.

---

## Task I1: Source registry contract

**Files:** `config/sources.yaml`, `src/wc_predictor/data/source_registry.py`,
`tests/data/test_source_registry.py`.

- [x] **Step 1: Port the registry from discovery evidence**

Translate `discovery/sources_evidence.yaml` into `config/sources.yaml` using the master plan's
**full** field shape (add `display_name`, `source_type`, `allowed_use`, `refresh_cadence`,
`point_in_time_safe` on top of the discovery fields). Include all 9 discovery sources but mark P2
status honestly: martj42 + openfootball as Milestone-1 active; the rest as later-phase. Do not
invent fields not backed by discovery.

- [x] **Step 2: Loader + validation**

`source_registry.py`: load `sources.yaml` into typed `Source` objects; validate each has
`source_id`, non-empty `required_fields`, `raw_retention_days >= 0`, a `license_or_terms_url`, and a
valid `phase`/`status`. Expose lookup by `source_id`.

- [x] **Step 3: Tests**

Port the master plan's `test_sources_have_required_fields` shape: every source has an id, retention
>= 0, and non-empty required fields. Add a test that `international_results_martj42` and
`openfootball_worldcup_2026` are present and Phase 1. `uv run pytest .../test_source_registry.py -v`.

- [x] **Step 4: Findings/log.** Claude commits.

---

## Task I2: Team alias resolver

**Files:** `config/team_aliases.csv`, `src/wc_predictor/data/team_aliases.py`,
`tests/data/test_team_aliases.py`.

- [ ] **Step 1: Write alias tests first**

Cover the difficult cases from discovery: `USA`→`United States`, `Bosnia & Herzegovina`→
`Bosnia and Herzegovina`, `Czech Republic`/`Czechia`, `DR Congo`/`Congo DR`,
`Ivory Coast`/`Cote d'Ivoire`, `IR Iran`, `Korea Republic`, `Cabo Verde`, `Turkiye`/`Turkey`. Also
test that an unknown name raises (no silent pass).

- [ ] **Step 2: Seed `team_aliases.csv`**

Columns from the master plan: `canonical_team_id`, `canonical_name`, `source_name`,
`source_team_name`, `valid_from`, `valid_to`, `confidence`, `manual_review_status`. Seed all 48
WC-2026 teams (from D2 fixtures) + the alias variants observed in D1/D2. Source the canonical names
from the openfootball/FIFA display set; map martj42 `home_team`/`away_team` spellings as
`source_name=martj42`.

- [ ] **Step 3: Implement resolver**

`TeamAliasResolver.from_csv(...)`, `.resolve(name, source) -> Alias(canonical_team_id,
canonical_name)`. Exact match (case/whitespace-normalized) only; explicit failure on unknown. No
fuzzy matching in Milestone 1.

- [ ] **Step 4: Validate coverage against real data**

Load the D1 sample (`discovery/findings/d1-martj42-results-schema-sample.csv`) and the D2 fixture
team list; assert every WC-2026 fixture team resolves. List any martj42 team in recent results that
does NOT resolve (report, don't crash) so we can extend the table. Run tests.

- [ ] **Step 5: Findings/log.** Claude commits.

---

## Task I3: Historical results ingestion (martj42 / D1)

**Files:** `src/wc_predictor/data/ingest_international_results.py`,
`tests/data/test_ingest_international_results.py`.

- [ ] **Step 1: Parser test using an embedded fixture CSV**

Small embedded CSV with the real schema (`date, home_team, away_team, home_score, away_score,
tournament, city, country, neutral`), including **at least one blank-score future row** to prove the
fixtures/results split (decision #1).

- [ ] **Step 2: Implement ingestion (raw → bronze → silver)**

- Download raw `results.csv` from the registry URL; save raw snapshot + SHA-256 + manifest JSON
  (source URL, ingest UTC, row count, hash) under `data/raw/`.
- Parse to bronze Parquet (source-shaped, stable columns).
- **Split:** rows with both scores populated → silver `matches`; blank-score rows → silver
  `fixtures` (tagged `source=martj42`, status `scheduled`). Never let blank-score rows become labels.
- Normalize `home_team`/`away_team` via the I2 resolver → `home_team_id`/`away_team_id`.

- [ ] **Step 3: Data-quality checks**

- `matches`: no missing date/team/score; scores are non-negative integers; `neutral` boolean; no
  duplicate `(date, home_team_id, away_team_id, tournament, city)`.
- Freshness assertion: `matches` contains 2025 AND 2026 rows (D1 recorded 1,385 in 2025–2026).
- Every team id resolved (no nulls); unresolved names fail the run with a clear list.

- [ ] **Step 4: Run tests + DQ summary**

`uv run pytest .../test_ingest_international_results.py -v`. Write a short DQ summary to
`reports/data_quality/` (row counts per layer, date range, split counts, unresolved-name count).

- [ ] **Step 5: Findings/log.** Claude commits.

---

## Task I4: World Cup 2026 fixture ingestion (openfootball / D2)

**Files:** `src/wc_predictor/data/ingest_openfootball_worldcup.py`,
`tests/data/test_ingest_openfootball_worldcup.py`.

- [ ] **Step 1: Parser tests**

Test parsing a 2026 group line (e.g. `Group A | Mexico ...`) and a knockout line from
`cup_finals.txt` (e.g. `(73) 2026-06-28 2A v 2B @ Los Angeles (Inglewood)`), including the
placeholder slots (`1A`, `3A/B/C/D/F`, `W74`, `L101`).

- [ ] **Step 2: Implement the football.txt parser**

Parse `2026--usa/cup.txt` (groups + 72 group fixtures) and `2026--usa/cup_finals.txt` (32 knockout
fixtures) into a normalized silver `fixtures` table. Resolve real team names via I2; **leave
knockout placeholder slots as `home_slot`/`away_slot` strings** with null team ids (they resolve as
results come in — that's P3/live).

- [ ] **Step 3: Required fields + cross-check**

Fields: `fixture_id`, `stage` (group/RO32/RO16/QF/SF/3rd/final), `group`, `home_team_id`,
`away_team_id` (nullable for knockouts), `home_slot`/`away_slot`, `match_date`, `venue`,
`match_number`. Cross-check counts against D2: 12 groups, 48 teams, 72 group + 32 knockout = 104
fixtures, dates 2026-06-11→07-19. Assert all 48 group-stage teams resolve via I2.

- [ ] **Step 4: Reconcile martj42 vs openfootball fixtures**

Both D1 (blank-score rows) and D2 carry 2026 fixtures. Decide the **fixtures source of truth =
openfootball (D2)** (richer: stage/group/venue/bracket). Note martj42 future rows as a
cross-validation check only. Document any date/pairing disagreements found.

- [ ] **Step 5: Run tests + commit.** DQ summary appended; Claude commits.

---

## Task I5: Ingestion DQ rollup + Milestone-1 readiness gate

**Files:** `reports/data_quality/INGESTION_REPORT.md`, optional
`src/wc_predictor/data/quality.py`.

- [ ] **Step 1: Roll up manifests + DQ**

Aggregate the I3/I4 manifests + DQ summaries into one `INGESTION_REPORT.md`: per-source row counts
per layer, date ranges, split counts, alias coverage, any unresolved names, raw payload hashes.

- [ ] **Step 2: Readiness assertions for P3**

State explicitly that the silver `matches` table is leakage-safe for Elo training (chronologically
ordered, no future fixtures in labels) and that `fixtures` covers all 104 WC-2026 matches. List
exactly what P3 (Elo) will consume.

- [ ] **Step 3: Recommendations + commit.** Note any gaps/decisions for Claude before P3.

---

## Definition of done for P2

- `worldcup_prediction_lab/` scaffold + `pyproject.toml` import-clean.
- `config/sources.yaml` + registry loader + tests pass.
- `team_aliases.csv` + resolver + tests pass; all 48 WC-2026 teams resolve.
- `ingest_international_results.py`: raw→bronze→silver with the **fixtures/results split**; DQ + tests pass.
- `ingest_openfootball_worldcup.py`: 104 fixtures (groups + knockout) in silver; tests pass.
- `INGESTION_REPORT.md` confirms a leakage-safe `matches` table + complete `fixtures`.
- No secrets, no large raw payloads committed (`data/raw|bronze|silver|gold/**` gitignored).
- co-op.md log updated; Claude reviews before P3 (Elo model slice) is written.
