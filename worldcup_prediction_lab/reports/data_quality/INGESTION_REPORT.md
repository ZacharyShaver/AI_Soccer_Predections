# Ingestion Report: Milestone 1 Data Layer

Generated for P2 / I5 on 2026-06-21 from the committed I3/I4 data-quality reports
and verified against the local silver parquet outputs.

## Source Rollup

| Source | Raw rows | Bronze rows | Silver tables | Date range | Key counts | Raw SHA-256 |
| --- | ---: | ---: | --- | --- | --- | --- |
| `international_results_martj42` | 49,477 | 49,477 | `martj42_matches`: 49,441; `martj42_fixtures`: 36; `martj42_teams`: 336 | matches: 1872-11-30 to 2026-06-20; fixtures: 2026-06-21 to 2026-06-27 | 49,441 completed matches; 36 blank-score fixtures; 336 canonical teams; 288 auto-registered teams; 1 double-header natural-key group; `match_id` unique | `ceba28c9203f1ad6ebdd926d6eda26b48b0f605d25c74accaa6920cf77167b67` |
| `openfootball_worldcup_2026` | 351 raw text lines (`cup`: 274; `cup_finals`: 77) | n/a (I4 parses source text directly to silver) | `openfootball_worldcup_2026_fixtures`: 104 | fixtures: 2026-06-11 to 2026-07-19 | 12 groups; 48 group teams resolved; 104 fixtures (72 group + 32 knockout); `fixture_id` unique; 3 home/away-order reconciliation diffs vs martj42 | `cup`: `e9a0814b413447792206abe2b9dfe04fa0a50564584e075390fe0aba97c7a77d`; `cup_finals`: `d5b8dc1ee3c06c65ad6bf71f6bbf7fcb4c9acc465999b08b49a3c86238b96db8` |

## Silver Verification

Verified locally with `uv run --with pandas --with pyarrow python ...` against:

- `data/silver/martj42_matches.parquet`
- `data/silver/martj42_fixtures.parquet`
- `data/silver/martj42_teams.parquet`
- `data/silver/openfootball_worldcup_2026_fixtures.parquet`

`martj42_matches` has 49,441 rows, `match_id` is unique, rows are ordered by
date, score fields have 0 blanks, score fields have 0 negative values, and
home/away team ids have 0 nulls.

`martj42_fixtures` has 36 rows, all with blank scores, and remains separate
from `martj42_matches`.

`martj42_teams` has 336 unique canonical team ids, including 288
auto-registered martj42 teams.

`openfootball_worldcup_2026_fixtures` has 104 rows, `fixture_id` is unique,
and stage counts are:

| Stage | Count |
| --- | ---: |
| group | 72 |
| round_of_32 | 16 |
| round_of_16 | 8 |
| quarter_final | 4 |
| semi_final | 2 |
| third_place | 1 |
| final | 1 |

All 48 group-stage team ids in the openfootball fixtures are present in the
martj42 teams dimension, so group-stage fixtures join to the training-history
team ids. Knockout placeholders intentionally keep null team ids until the
bracket resolves.

## P3 Readiness Gate

### Pass

- Completed-result labels and blank-score fixtures are split: `martj42_matches`
  contains 0 blank-score rows, while the 36 blank-score rows are in
  `martj42_fixtures`.
- `martj42_matches` is chronologically ordered by date and has unique
  `match_id` values.
- `openfootball_worldcup_2026_fixtures` covers all 104 scheduled WC-2026
  matches: 72 group fixtures and 32 knockout fixtures.
- All 48 group-stage teams resolve to canonical ids present in the martj42
  teams dimension, so fixture teams can join to historical training rows.
- Openfootball remains the WC-2026 fixture source of truth. Martj42 future rows
  are cross-validation only.

### Gap Before P3

The strict pre-tournament leakage assertion does not hold for the current local
silver data: `martj42_matches` max date is 2026-06-20, while the openfootball
WC-2026 fixture table starts on 2026-06-11. The 36 `martj42_matches` rows on or
after 2026-06-11 are already completed `FIFA World Cup` matches.

Therefore P3 must make the training cutoff explicit:

- For a pre-tournament forecast, train Elo only on rows before 2026-06-11.
- For an as-of 2026-06-21/live forecast, the 2026-06-11 to 2026-06-20 completed
  WC rows may be valid history, but the run metadata must record that `as_of`
  date and must forecast only remaining fixtures.

## P3 Inputs

P3 Elo should consume exactly these silver tables:

- `martj42_matches.parquet` for training labels and match chronology. Columns:
  `match_id`, `date`, `home_team_id`, `away_team_id`, `home_team`,
  `away_team`, `home_score`, `away_score`, `tournament`, `city`, `country`,
  `neutral`, `source`, `occurrence_index`.
- `martj42_teams.parquet` as the team dimension. Columns:
  `canonical_team_id`, `canonical_name`, `source_team_name`, `source`,
  `auto_registered`.
- `openfootball_worldcup_2026_fixtures.parquet` for forecasting. Columns:
  `fixture_id`, `stage`, `group`, `home_team_id`, `away_team_id`, `home_slot`,
  `away_slot`, `match_date`, `venue`, `match_number`.

P3 should not use `martj42_fixtures.parquet` as the WC fixture source of truth;
it is a cross-validation artifact.

## P3 Caveat: Home/Away Is Nominal

I4 found 3 martj42-vs-openfootball home/away-order reconciliation diffs:
CAN/SUI, MEX/CZE, and USA/TUR. For World Cup forecasting, Elo home advantage
must use neutral/host logic, not nominal fixture home/away ordering.

## P2 Definition Of Done

| Item | Status | Notes |
| --- | --- | --- |
| `worldcup_prediction_lab/` scaffold + `pyproject.toml` import-clean | Done | Established in I0; final verification should rerun import. |
| `config/sources.yaml` + registry loader + tests pass | Done | Established in I1. |
| `team_aliases.csv` + resolver + tests pass; all 48 WC-2026 teams resolve | Done | Established in I2 and rechecked through openfootball silver group ids. |
| `ingest_international_results.py`: raw to bronze to silver with fixtures/results split; DQ + tests pass | Done | I3 report confirms split and DQ; silver rechecked here. |
| `ingest_openfootball_worldcup.py`: 104 fixtures in silver; tests pass | Done | I4 report confirms counts; silver rechecked here. |
| `INGESTION_REPORT.md` confirms leakage-safe `matches` table + complete `fixtures` | Partial | Complete fixtures confirmed. Label split is clean, but pre-tournament leakage requires a P3 cutoff because 36 completed WC-2026 rows are already in `martj42_matches`. |
| No secrets, no large raw payloads committed | Pending Claude review | Raw/bronze/silver layers are gitignored by design; Codex did not run git. |
| `co-op.md` log updated; Claude reviews before P3 | Done by I5 | See Codex log entry. |

## Recommendations / Decisions For Claude Before P3

1. Decide whether P3's first Elo benchmark is a pre-tournament forecast
   (`training_cutoff < 2026-06-11`) or an as-of-live forecast
   (`as_of=2026-06-21`, training through 2026-06-20).
2. Require P3 run metadata to record `training_cutoff`, `as_of`, and the
   fixture subset being forecast so leakage checks are reproducible.
3. Implement Elo home advantage from `neutral` plus host-country logic, not
   nominal home/away ordering.
4. Keep openfootball as the fixture/bracket source of truth and use martj42
   fixture rows only for source reconciliation.
