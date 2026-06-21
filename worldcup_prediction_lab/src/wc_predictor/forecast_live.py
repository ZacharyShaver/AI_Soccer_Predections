"""Live as-of 2026-06-21 Elo forecasts for remaining World Cup fixtures."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.ledger import write_prediction
from wc_predictor.models.base import MatchPrediction
from wc_predictor.models.elo import (
    HostAdvantageSide,
    btts_probability,
    elo_model,
    over_probability,
    top_scoreline,
)


AS_OF = "2026-06-21"
TRAINING_CUTOFF = "2026-06-20"
GENERATED_AT_UTC = "2026-06-21T00:00:00Z"
MODEL_ID = "elo_poisson_v1"

# Openfootball venue labels are city-first, with stadium municipalities in
# parentheses. World Cup 2026 is neutral-site except when a host nation plays
# in its own host country.
VENUE_HOST_COUNTRIES: dict[str, str] = {
    "Atlanta": "USA",
    "Boston (Foxborough)": "USA",
    "Dallas (Arlington)": "USA",
    "Houston": "USA",
    "Kansas City": "USA",
    "Los Angeles (Inglewood)": "USA",
    "Miami (Miami Gardens)": "USA",
    "New York/New Jersey (East Rutherford)": "USA",
    "Philadelphia": "USA",
    "San Francisco Bay Area (Santa Clara)": "USA",
    "San Francisco (Santa Clara)": "USA",
    "Seattle": "USA",
    "Toronto": "Canada",
    "Vancouver": "Canada",
    "Mexico City": "Mexico",
    "Guadalajara (Zapopan)": "Mexico",
    "Monterrey (Guadalupe)": "Mexico",
}

HOST_TEAM_ID_TO_COUNTRY = {
    "USA": "USA",
    "CAN": "Canada",
    "MEX": "Mexico",
}


@dataclass(frozen=True)
class LiveFixtureSplit:
    total_fixtures: int
    forecast_fixtures: pd.DataFrame
    skipped_already_played_count: int
    skipped_knockout_pending_count: int

    @property
    def forecast_count(self) -> int:
        return int(len(self.forecast_fixtures))


@dataclass(frozen=True)
class ForecastRow:
    fixture_id: str
    group: str
    match_date: str
    venue: str
    home_team_id: str
    away_team_id: str
    home_team_name: str
    away_team_name: str
    prob_home: float
    prob_draw: float
    prob_away: float
    top_scoreline: str
    top_scoreline_probability: float
    over_2_5_probability: float
    btts_probability: float
    prediction_hash: str


@dataclass(frozen=True)
class LiveForecastSummary:
    as_of: str
    training_cutoff: str
    total_fixtures: int
    training_match_count: int
    forecast_count: int
    skipped_already_played_count: int
    skipped_knockout_pending_count: int
    ledger_path: Path
    report_path: Path
    forecast_rows: list[ForecastRow]
    unmapped_venues: list[str]


def _has_team_id(value: object) -> bool:
    return pd.notna(value) and str(value).strip() != ""


def _date_text(value: object) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _team_names(teams_df: pd.DataFrame) -> dict[str, str]:
    if teams_df.empty:
        return {}
    required_columns = {"canonical_team_id", "canonical_name"}
    missing_columns = required_columns - set(teams_df.columns)
    if missing_columns:
        raise ValueError(f"teams_df missing required columns: {sorted(missing_columns)}")
    return {
        str(row.canonical_team_id): str(row.canonical_name)
        for row in teams_df[["canonical_team_id", "canonical_name"]].itertuples(
            index=False
        )
    }


def host_country_for_venue(venue: object) -> str | None:
    if pd.isna(venue):
        return None
    return VENUE_HOST_COUNTRIES.get(str(venue).strip())


def build_world_cup_host_advantage_fn():
    """Return the WC 2026 host-advantage hook for Elo neutral-site fixtures."""

    def host_advantage_fn(
        match_row: pd.Series,
        home_team_id: str,
        away_team_id: str,
    ) -> HostAdvantageSide:
        venue_country = host_country_for_venue(match_row.get("venue"))
        if venue_country is None:
            return None

        home_country = HOST_TEAM_ID_TO_COUNTRY.get(str(home_team_id))
        away_country = HOST_TEAM_ID_TO_COUNTRY.get(str(away_team_id))
        if home_country == venue_country:
            return "home"
        if away_country == venue_country:
            return "away"
        return None

    return host_advantage_fn


def split_live_fixtures(
    fixtures_df: pd.DataFrame,
    *,
    as_of: str = AS_OF,
) -> LiveFixtureSplit:
    """Split openfootball fixtures into forecastable, already-played, and pending."""

    required_columns = {"fixture_id", "home_team_id", "away_team_id", "match_date"}
    missing_columns = required_columns - set(fixtures_df.columns)
    if missing_columns:
        raise ValueError(f"fixtures_df missing required columns: {sorted(missing_columns)}")

    fixtures = fixtures_df.copy()
    fixtures["match_date"] = pd.to_datetime(fixtures["match_date"], errors="coerce")
    if fixtures["match_date"].isna().any():
        raise ValueError("fixtures_df contains invalid match_date values")

    as_of_ts = pd.Timestamp(as_of)
    resolvable = fixtures["home_team_id"].map(_has_team_id) & fixtures[
        "away_team_id"
    ].map(_has_team_id)
    pending = fixtures.loc[~resolvable].copy()
    resolved = fixtures.loc[resolvable].copy()
    already_played = resolved.loc[resolved["match_date"] <= as_of_ts].copy()
    forecast = resolved.loc[resolved["match_date"] > as_of_ts].copy()
    forecast = forecast.sort_values(
        ["match_date", "group", "fixture_id"],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)

    return LiveFixtureSplit(
        total_fixtures=int(len(fixtures)),
        forecast_fixtures=forecast,
        skipped_already_played_count=int(len(already_played)),
        skipped_knockout_pending_count=int(len(pending)),
    )


def _training_matches(
    matches_df: pd.DataFrame,
    *,
    training_cutoff: str = TRAINING_CUTOFF,
) -> pd.DataFrame:
    required_columns = {"date", "home_score", "away_score"}
    missing_columns = required_columns - set(matches_df.columns)
    if missing_columns:
        raise ValueError(f"matches_df missing required columns: {sorted(missing_columns)}")

    matches = matches_df.copy()
    matches["date"] = pd.to_datetime(matches["date"], errors="coerce")
    if matches["date"].isna().any():
        raise ValueError("matches_df contains invalid date values")

    cutoff_ts = pd.Timestamp(training_cutoff)
    completed = matches["home_score"].notna() & matches["away_score"].notna()
    train = matches.loc[completed & (matches["date"] <= cutoff_ts)].copy()
    return train.sort_values(["date", "match_id"], kind="mergesort").reset_index(drop=True)


def _fixture_match_row(
    fixture: pd.Series,
    team_names_by_id: dict[str, str],
) -> pd.Series:
    home_team_id = str(fixture["home_team_id"])
    away_team_id = str(fixture["away_team_id"])
    return pd.Series(
        {
            "match_id": str(fixture["fixture_id"]),
            "date": fixture["match_date"],
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "home_team": team_names_by_id.get(home_team_id, home_team_id),
            "away_team": team_names_by_id.get(away_team_id, away_team_id),
            "tournament": "FIFA World Cup",
            "neutral": True,
            "venue": fixture.get("venue"),
            "occurrence_index": 0,
        }
    )


def _build_prediction(
    *,
    model,
    fixture: pd.Series,
    team_names_by_id: dict[str, str],
    as_of: str,
    training_cutoff: str,
) -> tuple[MatchPrediction, ForecastRow]:
    match_row = _fixture_match_row(fixture, team_names_by_id)
    outcome = model.predict_match(match_row)
    scoreline_distribution = model.predict_scoreline(match_row)
    best_scoreline, best_scoreline_probability = top_scoreline(scoreline_distribution)
    prediction = MatchPrediction(
        prediction_id=f"{MODEL_ID}:{fixture['fixture_id']}:as_of={as_of}",
        match_id=str(fixture["fixture_id"]),
        model_id=MODEL_ID,
        model_version=str(model.model_version),
        generated_at_utc=GENERATED_AT_UTC,
        training_cutoff=training_cutoff,
        as_of=as_of,
        prob_home=float(outcome.prob_home),
        prob_draw=float(outcome.prob_draw),
        prob_away=float(outcome.prob_away),
        scoreline_distribution=scoreline_distribution,
    )
    home_team_id = str(fixture["home_team_id"])
    away_team_id = str(fixture["away_team_id"])
    group_value = fixture.get("group")
    forecast_row = ForecastRow(
        fixture_id=str(fixture["fixture_id"]),
        group=str(group_value) if pd.notna(group_value) else "Pending",
        match_date=_date_text(fixture["match_date"]),
        venue=str(fixture.get("venue", "")),
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_team_name=team_names_by_id.get(home_team_id, home_team_id),
        away_team_name=team_names_by_id.get(away_team_id, away_team_id),
        prob_home=float(outcome.prob_home),
        prob_draw=float(outcome.prob_draw),
        prob_away=float(outcome.prob_away),
        top_scoreline=best_scoreline,
        top_scoreline_probability=float(best_scoreline_probability),
        over_2_5_probability=float(over_probability(scoreline_distribution, 2.5)),
        btts_probability=float(btts_probability(scoreline_distribution)),
        prediction_hash=prediction.prediction_hash,
    )
    return prediction, forecast_row


def _format_percent(value: float) -> str:
    return f"{value * 100.0:.1f}%"


def _venue_mapping_lines() -> list[str]:
    lines = []
    for venue, country in sorted(VENUE_HOST_COUNTRIES.items()):
        lines.append(f"- {venue}: {country}")
    return lines


def write_forecast_report(
    summary: LiveForecastSummary,
    *,
    reports_dir: str | Path = settings.REPORTS_DIR,
) -> Path:
    report_path = Path(reports_dir) / "backtests" / f"live_forecast_{summary.as_of}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Live World Cup forecast as of {summary.as_of}",
        "",
        "These are Elo-only forecasts from `elo_poisson_v1`, the model bar proven in M6.",
        "They are not market-calibrated and do not include injuries, lineups, travel, or live odds.",
        "",
        "Statistical honesty caveat: M6 showed Elo beat climatology on a large walk-forward",
        "history, but single-match probabilities are still uncertain. Treat narrow edges as",
        "within normal forecast noise, not as certainties.",
        "",
        "Knockout fixtures are pending bracket resolution because openfootball stores placeholder",
        "slots with null team ids until the bracket is known.",
        "",
        "## Counts",
        "",
        f"- Total fixtures: {summary.total_fixtures}",
        f"- Forecast: {summary.forecast_count}",
        f"- Skipped already played (<= {summary.as_of}): {summary.skipped_already_played_count}",
        f"- Skipped knockout pending: {summary.skipped_knockout_pending_count}",
        f"- Training matches through {summary.training_cutoff}: {summary.training_match_count}",
        f"- Ledger: `{summary.ledger_path.as_posix()}`",
        "",
        "## Venue host-country mapping",
        "",
        *_venue_mapping_lines(),
        "",
    ]

    if summary.unmapped_venues:
        lines.extend(
            [
                "Unmapped forecast venues defaulted to neutral:",
                "",
                *[f"- {venue}" for venue in summary.unmapped_venues],
                "",
            ]
        )
    else:
        lines.extend(["All forecast venues were mapped to a host country.", ""])

    for group in sorted({row.group for row in summary.forecast_rows}):
        lines.extend([f"## Group {group}", ""])
        rows = [row for row in summary.forecast_rows if row.group == group]
        lines.extend(
            [
                "| Date | Venue | Match | Home | Draw | Away | Most likely score | O2.5 | BTTS |",
                "| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: |",
            ]
        )
        for row in rows:
            lines.append(
                "| "
                f"{row.match_date} | {row.venue} | "
                f"{row.home_team_name} vs {row.away_team_name} | "
                f"{_format_percent(row.prob_home)} | "
                f"{_format_percent(row.prob_draw)} | "
                f"{_format_percent(row.prob_away)} | "
                f"{row.top_scoreline} ({_format_percent(row.top_scoreline_probability)}) | "
                f"{_format_percent(row.over_2_5_probability)} | "
                f"{_format_percent(row.btts_probability)} |"
            )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def run_live_forecast(
    *,
    matches_df: pd.DataFrame,
    fixtures_df: pd.DataFrame,
    teams_df: pd.DataFrame,
    runs_dir: str | Path = settings.RUNS_DIR,
    reports_dir: str | Path = settings.REPORTS_DIR,
    as_of: str = AS_OF,
    training_cutoff: str = TRAINING_CUTOFF,
) -> LiveForecastSummary:
    train_matches = _training_matches(matches_df, training_cutoff=training_cutoff)
    split = split_live_fixtures(fixtures_df, as_of=as_of)
    team_names_by_id = _team_names(teams_df)
    model = elo_model(
        generated_at_utc=GENERATED_AT_UTC,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    ).fit(train_matches)

    forecast_rows: list[ForecastRow] = []
    ledger_path = (
        Path(runs_dir) / "predictions" / f"date={as_of}" / "predictions.jsonl"
    )
    for _, fixture in split.forecast_fixtures.iterrows():
        prediction, forecast_row = _build_prediction(
            model=model,
            fixture=fixture,
            team_names_by_id=team_names_by_id,
            as_of=as_of,
            training_cutoff=training_cutoff,
        )
        ledger_path = write_prediction(prediction, runs_dir=runs_dir)
        forecast_rows.append(forecast_row)

    unmapped_venues = sorted(
        {
            str(venue)
            for venue in split.forecast_fixtures["venue"].dropna().unique().tolist()
            if host_country_for_venue(venue) is None
        }
    )
    summary = LiveForecastSummary(
        as_of=as_of,
        training_cutoff=training_cutoff,
        total_fixtures=split.total_fixtures,
        training_match_count=int(len(train_matches)),
        forecast_count=split.forecast_count,
        skipped_already_played_count=split.skipped_already_played_count,
        skipped_knockout_pending_count=split.skipped_knockout_pending_count,
        ledger_path=Path(ledger_path),
        report_path=Path(reports_dir)
        / "backtests"
        / f"live_forecast_{as_of}.md",
        forecast_rows=forecast_rows,
        unmapped_venues=unmapped_venues,
    )
    report_path = write_forecast_report(summary, reports_dir=reports_dir)
    return LiveForecastSummary(
        as_of=summary.as_of,
        training_cutoff=summary.training_cutoff,
        total_fixtures=summary.total_fixtures,
        training_match_count=summary.training_match_count,
        forecast_count=summary.forecast_count,
        skipped_already_played_count=summary.skipped_already_played_count,
        skipped_knockout_pending_count=summary.skipped_knockout_pending_count,
        ledger_path=summary.ledger_path,
        report_path=report_path,
        forecast_rows=summary.forecast_rows,
        unmapped_venues=summary.unmapped_venues,
    )


def _silver_paths(silver_dir: str | Path = settings.SILVER_DIR) -> dict[str, Path]:
    silver_path = Path(silver_dir)
    return {
        "matches": silver_path / "martj42_matches.parquet",
        "fixtures": silver_path / "openfootball_worldcup_2026_fixtures.parquet",
        "teams": silver_path / "martj42_teams.parquet",
    }


def ensure_silver_inputs(silver_dir: str | Path = settings.SILVER_DIR) -> None:
    """Regenerate I3/I4 silver inputs if any required parquet is absent."""

    paths = _silver_paths(silver_dir)
    if all(path.exists() for path in paths.values()):
        return

    from wc_predictor.data.ingest_international_results import ingest as ingest_martj42
    from wc_predictor.data.ingest_openfootball_worldcup import ingest as ingest_openfootball

    ingest_martj42(silver_dir=silver_dir)
    ingest_openfootball(silver_dir=silver_dir)


def load_silver_data(
    silver_dir: str | Path = settings.SILVER_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ensure_silver_inputs(silver_dir)
    paths = _silver_paths(silver_dir)
    return (
        pd.read_parquet(paths["matches"]),
        pd.read_parquet(paths["fixtures"]),
        pd.read_parquet(paths["teams"]),
    )


def _summary_payload(summary: LiveForecastSummary) -> dict[str, object]:
    return {
        "as_of": summary.as_of,
        "training_cutoff": summary.training_cutoff,
        "total_fixtures": summary.total_fixtures,
        "training_match_count": summary.training_match_count,
        "forecast_count": summary.forecast_count,
        "skipped_already_played_count": summary.skipped_already_played_count,
        "skipped_knockout_pending_count": summary.skipped_knockout_pending_count,
        "ledger_path": str(summary.ledger_path),
        "report_path": str(summary.report_path),
        "examples": [
            {
                "match": f"{row.home_team_name} vs {row.away_team_name}",
                "date": row.match_date,
                "home": round(row.prob_home, 6),
                "draw": round(row.prob_draw, 6),
                "away": round(row.prob_away, 6),
                "top_scoreline": row.top_scoreline,
            }
            for row in summary.forecast_rows[:5]
        ],
    }


def main() -> None:
    matches, fixtures, teams = load_silver_data()
    summary = run_live_forecast(
        matches_df=matches,
        fixtures_df=fixtures,
        teams_df=teams,
    )
    print(json.dumps(_summary_payload(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
