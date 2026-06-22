"""Ingest Polymarket Gamma World Cup match prices and compare them to Elo."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.data.devig import remove_vig
from wc_predictor.data.team_aliases import TeamAliasResolver, normalize_team_name
from wc_predictor.forecast_live import (
    AS_OF,
    TRAINING_CUTOFF,
    run_live_forecast,
)


GAMMA_BASE = "https://gamma-api.polymarket.com"
WORLD_CUP_TAG_ID = "102232"
EVENT_PAGE_LIMIT = 100
SOURCE_NAME = "polymarket"
ALIAS_SOURCES = ("polymarket", "manual", "fifa", "openfootball", "martj42")
MARKET_COLUMNS = [
    "event_id",
    "event_title",
    "home_team_name",
    "away_team_name",
    "home_team_id",
    "away_team_id",
    "market_type",
    "prob_home",
    "prob_draw",
    "prob_away",
    "home_market_id",
    "draw_market_id",
    "away_market_id",
    "raw_home_price",
    "raw_draw_price",
    "raw_away_price",
]


@dataclass(frozen=True)
class RawSnapshot:
    source_url: str
    ingest_utc: str
    sha256: str
    byte_count: int
    raw_path: str
    manifest_path: str
    event_count: int
    request_count: int


@dataclass(frozen=True)
class MarketDisagreementResult:
    market_rows: pd.DataFrame
    comparison: pd.DataFrame
    summary: dict[str, Any]
    report_path: Path


def _utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _empty_market_rows() -> pd.DataFrame:
    return pd.DataFrame(columns=MARKET_COLUMNS)


def _json_array(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def _yes_price(market: dict[str, Any]) -> float | None:
    outcomes = _json_array(market.get("outcomes"))
    prices_raw = _json_array(market.get("outcomePrices"))
    if outcomes is None or prices_raw is None or len(outcomes) != len(prices_raw):
        return None

    prices: list[float] = []
    for raw_price in prices_raw:
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(price):
            return None
        prices.append(price)

    yes_index = None
    for index, outcome in enumerate(outcomes):
        if str(outcome).strip().casefold() == "yes":
            yes_index = index
            break
    if yes_index is None:
        return None

    yes = prices[yes_index]
    if yes <= 0.0 or yes >= 1.0:
        return None
    return yes


def _match_title_teams(title: Any) -> tuple[str, str] | None:
    text = str(title or "").strip()
    if not text:
        return None
    lower = text.casefold()
    if "more markets" in lower or "exact score" in lower or "second half result" in lower:
        return None

    base_title = re.split(r"\s+-\s+", text, maxsplit=1)[0].strip()
    parts = re.split(r"\s+vs\.?\s+", base_title, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    home = parts[0].strip()
    away = parts[1].strip()
    if not home or not away:
        return None
    return home, away


def _question_role(question: Any, home_name: str, away_name: str) -> str | None:
    normalized = normalize_team_name(str(question or ""))
    home_variants = _team_name_variants(home_name)
    away_variants = _team_name_variants(away_name)
    if "draw" in normalized or "end in a draw" in normalized:
        return "draw"
    win_terms = (" win", " beat")
    if any(normalized.startswith(f"will {home} ") for home in home_variants) and any(
        term in normalized for term in win_terms
    ):
        return "home"
    if any(normalized.startswith(f"will {away} ") for away in away_variants) and any(
        term in normalized for term in win_terms
    ):
        return "away"
    if any(home in normalized for home in home_variants) and any(
        term in normalized for term in win_terms
    ):
        return "home"
    if any(away in normalized for away in away_variants) and any(
        term in normalized for term in win_terms
    ):
        return "away"
    return None


def _team_name_candidates(name: str) -> list[str]:
    candidates = [name]
    if "-" in name:
        candidates.append(name.replace("-", " "))
        candidates.append(name.replace("-", " and "))
    return list(dict.fromkeys(candidates))


def _team_name_variants(name: str) -> set[str]:
    return {normalize_team_name(candidate) for candidate in _team_name_candidates(name)}


def _resolve_team_id(
    name: str,
    resolver: TeamAliasResolver,
    unmatched_names: set[str],
) -> str | None:
    for candidate in _team_name_candidates(name):
        for source in ALIAS_SOURCES:
            try:
                return resolver.resolve(candidate, source=source).canonical_team_id
            except KeyError:
                continue
    unmatched_names.add(name)
    return None


def parse_world_cup_match_events(
    events: list[dict[str, Any]],
    *,
    resolver: TeamAliasResolver | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Parse Gamma event payloads into de-vigged match result probabilities."""

    resolver = resolver or TeamAliasResolver.from_csv()
    rows: list[dict[str, Any]] = []
    unmatched_names: set[str] = set()
    skipped_invalid_price = 0
    skipped_non_match_events = 0
    skipped_incomplete_match_events = 0

    for event in events:
        teams = _match_title_teams(event.get("title"))
        if teams is None:
            skipped_non_match_events += 1
            continue

        home_name, away_name = teams
        role_markets: dict[str, tuple[dict[str, Any], float]] = {}
        for market in event.get("markets") or []:
            if not isinstance(market, dict):
                continue
            price = _yes_price(market)
            if price is None:
                skipped_invalid_price += 1
                continue
            role = _question_role(market.get("question"), home_name, away_name)
            if role is None:
                continue
            role_markets[role] = (market, price)

        required_roles = {"home", "draw", "away"}
        if not required_roles <= role_markets.keys():
            skipped_incomplete_match_events += 1
            continue

        home_price = role_markets["home"][1]
        draw_price = role_markets["draw"][1]
        away_price = role_markets["away"][1]
        prob_home, prob_draw, prob_away = remove_vig(
            [home_price, draw_price, away_price]
        )
        rows.append(
            {
                "event_id": str(event.get("id")),
                "event_title": str(event.get("title") or ""),
                "home_team_name": home_name,
                "away_team_name": away_name,
                "home_team_id": _resolve_team_id(home_name, resolver, unmatched_names),
                "away_team_id": _resolve_team_id(away_name, resolver, unmatched_names),
                "market_type": "three_way",
                "prob_home": prob_home,
                "prob_draw": prob_draw,
                "prob_away": prob_away,
                "home_market_id": str(role_markets["home"][0].get("id")),
                "draw_market_id": str(role_markets["draw"][0].get("id")),
                "away_market_id": str(role_markets["away"][0].get("id")),
                "raw_home_price": home_price,
                "raw_draw_price": draw_price,
                "raw_away_price": away_price,
            }
        )

    market_rows = _empty_market_rows() if not rows else pd.DataFrame(rows)
    if not market_rows.empty:
        market_rows = market_rows.loc[:, MARKET_COLUMNS].sort_values(
            ["event_title", "event_id"],
            kind="mergesort",
        )
    market_rows = market_rows.reset_index(drop=True)
    summary = {
        "events_seen": int(len(events)),
        "events_matched": int(len(market_rows)),
        "markets_skipped_invalid_price": int(skipped_invalid_price),
        "events_skipped_non_match": int(skipped_non_match_events),
        "events_skipped_incomplete_match": int(skipped_incomplete_match_events),
        "unmatched_team_names": sorted(unmatched_names),
        "unmatched_team_count": int(len(unmatched_names)),
    }
    market_rows.attrs.update(summary)
    return market_rows, summary


def _api_get(client: Any, path: str, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    response = client.get(f"{GAMMA_BASE}{path}", params=params)
    facts = {
        "url": str(response.url),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "bytes": len(response.content),
    }
    if response.status_code != 200:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"GET {response.url} returned HTTP {response.status_code}: {preview}")
    content_type = facts["content_type"].casefold()
    if "application/json" not in content_type:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(
            f"GET {response.url} returned HTTP 200 but non-JSON content-type "
            f"{facts['content_type']!r}: {preview}"
        )
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"GET {response.url} returned invalid JSON: {preview}") from exc
    return payload, facts


def fetch_world_cup_markets(
    *,
    raw_dir: str | Path = settings.RAW_DIR / SOURCE_NAME,
    tag_id: str = WORLD_CUP_TAG_ID,
) -> tuple[RawSnapshot, list[dict[str, Any]]]:
    """Fetch active open 2026 World Cup events from public Gamma and save raw JSON."""

    import httpx

    events: list[dict[str, Any]] = []
    request_facts: list[dict[str, Any]] = []
    headers = {"Accept": "application/json", "User-Agent": "AI-Soccer-Predictions/0.1"}
    with httpx.Client(headers=headers, timeout=60.0, follow_redirects=True) as client:
        offset = 0
        while True:
            params = {
                "tag_id": tag_id,
                "limit": EVENT_PAGE_LIMIT,
                "offset": offset,
                "active": "true",
                "closed": "false",
                "order": "volume",
                "ascending": "false",
            }
            payload, facts = _api_get(client, "/events", params)
            if not isinstance(payload, list):
                raise RuntimeError(
                    f"GET {facts['url']} returned JSON {type(payload).__name__}, expected list"
                )
            request_facts.append({**facts, "event_count": len(payload)})
            if not payload:
                break
            events.extend(payload)
            if len(payload) < EVENT_PAGE_LIMIT:
                break
            offset += EVENT_PAGE_LIMIT

    if not events:
        raise RuntimeError("Gamma returned no active open World Cup events")

    raw_payload = {
        "source": "Polymarket Gamma API",
        "tag_id": tag_id,
        "ingest_utc": _utc_iso(),
        "requests": request_facts,
        "events": events,
    }
    raw_bytes = json.dumps(raw_payload, indent=2, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(raw_bytes).hexdigest()
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    snapshot_path = raw_path / f"worldcup_events_{_utc_slug()}_{digest[:12]}.json"
    manifest_path = snapshot_path.with_suffix(".manifest.json")
    snapshot_path.write_bytes(raw_bytes)
    snapshot = RawSnapshot(
        source_url=request_facts[0]["url"],
        ingest_utc=raw_payload["ingest_utc"],
        sha256=digest,
        byte_count=len(raw_bytes),
        raw_path=str(snapshot_path),
        manifest_path=str(manifest_path),
        event_count=len(events),
        request_count=len(request_facts),
    )
    manifest_path.write_text(
        json.dumps(asdict(snapshot), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot, events


def compare_market_to_elo(
    market_rows: pd.DataFrame,
    forecast_rows: list[Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    market = market_rows.copy()
    resolved_market = market[
        market["home_team_id"].notna() & market["away_team_id"].notna()
    ].copy()
    forecasts = pd.DataFrame([asdict(row) for row in forecast_rows])
    if forecasts.empty or resolved_market.empty:
        comparison = pd.DataFrame()
    else:
        comparison = forecasts.merge(
            resolved_market,
            on=["home_team_id", "away_team_id"],
            how="inner",
            suffixes=("_elo", "_market"),
        )
        if not comparison.empty:
            comparison["abs_home_win_diff"] = (
                comparison["prob_home_elo"] - comparison["prob_home_market"]
            ).abs()
            comparison["market_favorite"] = comparison.apply(
                lambda row: _favorite(
                    row["prob_home_market"],
                    row["prob_draw_market"],
                    row["prob_away_market"],
                    row["home_team_name_elo"],
                    row["away_team_name_elo"],
                ),
                axis=1,
            )
            comparison["elo_favorite"] = comparison.apply(
                lambda row: _favorite(
                    row["prob_home_elo"],
                    row["prob_draw_elo"],
                    row["prob_away_elo"],
                    row["home_team_name_elo"],
                    row["away_team_name_elo"],
                ),
                axis=1,
            )
            comparison = comparison.sort_values(
                ["abs_home_win_diff", "event_title"],
                ascending=[False, True],
                kind="mergesort",
            ).reset_index(drop=True)

    forecast_pairs = {
        (str(row.home_team_id), str(row.away_team_id)) for row in forecast_rows
    }
    market_pairs = {
        (str(row.home_team_id), str(row.away_team_id))
        for row in resolved_market.itertuples(index=False)
    }
    summary = {
        "market_events_matched": int(len(market_rows)),
        "market_events_with_both_team_ids": int(len(resolved_market)),
        "elo_forecast_count": int(len(forecast_rows)),
        "comparison_count": int(len(comparison)),
        "market_only_count": int(len(market_pairs - forecast_pairs)),
        "elo_only_count": int(len(forecast_pairs - market_pairs)),
        "unmatched_team_names": market_rows.attrs.get("unmatched_team_names", []),
    }
    return comparison, summary


def _favorite(
    prob_home: float,
    prob_draw: float,
    prob_away: float,
    home_name: str,
    away_name: str,
) -> str:
    values = [
        (float(prob_home), str(home_name)),
        (float(prob_draw), "Draw"),
        (float(prob_away), str(away_name)),
    ]
    return max(values, key=lambda item: item[0])[1]


def _pct(value: float) -> str:
    return f"{float(value) * 100.0:.1f}%"


def write_market_disagreement_report(
    *,
    comparison: pd.DataFrame,
    summary: dict[str, Any],
    snapshot: RawSnapshot | None,
    parse_summary: dict[str, Any],
    report_path: str | Path = settings.REPORTS_DIR
    / "backtests"
    / f"market_disagreement_{AS_OF}.md",
) -> Path:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = _utc_iso()
    raw_lines: list[str]
    if snapshot is None:
        raw_lines = ["- Raw snapshot: not fetched in this run."]
    else:
        raw_lines = [
            f"- Raw snapshot: `{snapshot.raw_path}`",
            f"- Raw SHA-256: `{snapshot.sha256}`",
            f"- Raw manifest: `{snapshot.manifest_path}`",
            f"- Gamma event requests: {snapshot.request_count}",
        ]

    unmatched = summary.get("unmatched_team_names", [])
    unmatched_lines = [f"- {name}" for name in unmatched] if unmatched else ["- None"]
    lines = [
        f"# Live Polymarket vs Elo disagreement as of {AS_OF}",
        "",
        f"Generated: `{generated}`",
        "",
        "This compares live Polymarket Gamma match-result prices to the current",
        f"host-aware Elo forecast trained through {TRAINING_CUTOFF}. Polymarket prices",
        "are parsed from the public no-auth Gamma API, filtered for positive Yes prices,",
        "and proportionally de-vigged across each mutually exclusive H/D/A event.",
        "",
        "## Counts",
        "",
        f"- Gamma events seen: {parse_summary['events_seen']:,}",
        f"- Match-result market events parsed: {summary['market_events_matched']:,}",
        f"- Parsed market events with both canonical team ids: {summary['market_events_with_both_team_ids']:,}",
        f"- Elo remaining-fixture forecasts: {summary['elo_forecast_count']:,}",
        f"- Matches present in both Elo and Polymarket: {summary['comparison_count']:,}",
        f"- Market-only resolved match events: {summary['market_only_count']:,}",
        f"- Elo-only forecast fixtures: {summary['elo_only_count']:,}",
        f"- Markets skipped for null/missing/placeholder prices: {parse_summary['markets_skipped_invalid_price']:,}",
        *raw_lines,
        "",
        "Unmatched Polymarket team names:",
        "",
        *unmatched_lines,
        "",
        "## Biggest disagreements",
        "",
    ]
    if comparison.empty:
        lines.extend(
            [
                "No overlapping resolved match-result markets were available, so no",
                "Elo-vs-market disagreement table was produced.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "| Date | Match | Elo H/D/A | Market H/D/A | Abs home diff | Elo fav | Market fav |",
                "| --- | --- | --- | --- | ---: | --- | --- |",
            ]
        )
        for row in comparison.head(15).itertuples(index=False):
            lines.append(
                "| "
                f"{row.match_date} | {row.home_team_name_elo} vs {row.away_team_name_elo} | "
                f"{_pct(row.prob_home_elo)} / {_pct(row.prob_draw_elo)} / {_pct(row.prob_away_elo)} | "
                f"{_pct(row.prob_home_market)} / {_pct(row.prob_draw_market)} / {_pct(row.prob_away_market)} | "
                f"{_pct(row.abs_home_win_diff)} | {row.elo_favorite} | {row.market_favorite} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "",
            "The comparison is prediction-vs-prediction, not a score test. Elo is an",
            "internal form-only rating with host advantage; Polymarket is a live market",
            "that can incorporate injuries, lineups, sentiment, liquidity, and late news.",
            "Large gaps are therefore useful flags for review, not automatic model errors.",
            "",
            "Caveats:",
            "",
            "- Gamma prices are live and can move after this snapshot.",
            "- Only individual match-result events are included; props, spreads, totals, exact scores, group, and outright markets are excluded.",
            "- If Polymarket uses a team spelling outside the alias table, the market is reported but cannot join Elo until the alias is added.",
            "- If only two-way match-winner markets appear in a future snapshot, this parser will currently skip them rather than mixing two-way and three-way probabilities.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run(
    *,
    raw_dir: str | Path = settings.RAW_DIR / SOURCE_NAME,
    report_path: str | Path = settings.REPORTS_DIR
    / "backtests"
    / f"market_disagreement_{AS_OF}.md",
) -> MarketDisagreementResult:
    snapshot, events = fetch_world_cup_markets(raw_dir=raw_dir)
    market_rows, parse_summary = parse_world_cup_match_events(events)
    matches, fixtures, teams = _load_silver_data_duckdb()
    live_summary = run_live_forecast(
        matches_df=matches,
        fixtures_df=fixtures,
        teams_df=teams,
    )
    comparison, summary = compare_market_to_elo(market_rows, live_summary.forecast_rows)
    summary.update(
        {
            "raw_path": snapshot.raw_path,
            "raw_sha256": snapshot.sha256,
            "manifest_path": snapshot.manifest_path,
        }
    )
    path = write_market_disagreement_report(
        comparison=comparison,
        summary=summary,
        snapshot=snapshot,
        parse_summary=parse_summary,
        report_path=report_path,
    )
    return MarketDisagreementResult(
        market_rows=market_rows,
        comparison=comparison,
        summary=summary,
        report_path=path,
    )


def _read_parquet_duckdb(path: Path) -> pd.DataFrame:
    import duckdb

    escaped_path = str(path).replace("'", "''")
    with duckdb.connect(database=":memory:") as connection:
        return connection.execute(
            f"SELECT * FROM read_parquet('{escaped_path}')"
        ).fetchdf()


def _load_silver_data_duckdb() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        _read_parquet_duckdb(settings.SILVER_DIR / "martj42_matches.parquet"),
        _read_parquet_duckdb(
            settings.SILVER_DIR / "openfootball_worldcup_2026_fixtures.parquet"
        ),
        _read_parquet_duckdb(settings.SILVER_DIR / "martj42_teams.parquet"),
    )


def main() -> None:
    result = run()
    print(
        "[ingest_polymarket] "
        f"market_events={result.summary['market_events_matched']} "
        f"resolved={result.summary['market_events_with_both_team_ids']} "
        f"overlap={result.summary['comparison_count']} "
        f"report={result.report_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
