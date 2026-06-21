"""Load and validate data source registry definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from wc_predictor.config import settings


class SourceRegistryError(ValueError):
    """Raised when the source registry is missing required contract fields."""


@dataclass(frozen=True)
class Source:
    source_id: str
    display_name: str
    source_type: str
    access_method: str
    license_or_terms_url: str
    allowed_use: str
    refresh_cadence: str
    requires_secret: bool
    point_in_time_safe: bool
    raw_retention_days: int
    bronze_retention_days: int
    primary_keys: list[str]
    required_fields: list[str]
    phase: int
    status: str


def _default_registry_path() -> Path:
    return settings.CONFIG_DIR / "sources.yaml"


def _validate_source(source: Source) -> None:
    if not source.source_id:
        raise SourceRegistryError("source_id must be non-empty")
    if not source.required_fields:
        raise SourceRegistryError(
            f"{source.source_id}: required_fields must contain at least one field"
        )
    if source.raw_retention_days < 0:
        raise SourceRegistryError(
            f"{source.source_id}: raw_retention_days must be >= 0"
        )
    if not source.license_or_terms_url:
        raise SourceRegistryError(
            f"{source.source_id}: license_or_terms_url must be non-empty"
        )
    if source.phase is None or not source.status:
        raise SourceRegistryError(f"{source.source_id}: phase and status are required")


def _source_from_mapping(item: dict[str, Any]) -> Source:
    try:
        source = Source(
            source_id=str(item["source_id"]).strip(),
            display_name=str(item["display_name"]).strip(),
            source_type=str(item["source_type"]).strip(),
            access_method=str(item["access_method"]).strip(),
            license_or_terms_url=str(item["license_or_terms_url"]).strip(),
            allowed_use=str(item["allowed_use"]).strip(),
            refresh_cadence=str(item["refresh_cadence"]).strip(),
            requires_secret=bool(item["requires_secret"]),
            point_in_time_safe=bool(item["point_in_time_safe"]),
            raw_retention_days=int(item["raw_retention_days"]),
            bronze_retention_days=int(item["bronze_retention_days"]),
            primary_keys=list(item["primary_keys"]),
            required_fields=list(item["required_fields"]),
            phase=int(item["phase"]),
            status=str(item["status"]).strip(),
        )
    except KeyError as exc:
        missing = exc.args[0]
        source_id = item.get("source_id", "<unknown>")
        raise SourceRegistryError(f"{source_id}: missing required key {missing}") from exc
    except (TypeError, ValueError) as exc:
        source_id = item.get("source_id", "<unknown>")
        raise SourceRegistryError(f"{source_id}: invalid source registry entry") from exc

    _validate_source(source)
    return source


def load_sources(path: str | Path | None = None) -> dict[str, Source]:
    """Load source definitions keyed by source_id."""

    registry_path = Path(path) if path is not None else _default_registry_path()
    with registry_path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}

    raw_sources = document.get("sources")
    if not isinstance(raw_sources, list):
        raise SourceRegistryError(f"{registry_path}: top-level 'sources' must be a list")

    sources: dict[str, Source] = {}
    for item in raw_sources:
        if not isinstance(item, dict):
            raise SourceRegistryError(f"{registry_path}: each source must be a mapping")
        source = _source_from_mapping(item)
        if source.source_id in sources:
            raise SourceRegistryError(f"{source.source_id}: duplicate source_id")
        sources[source.source_id] = source

    return sources


def get_source(source_id: str) -> Source:
    """Return one source by id, raising KeyError for unknown ids."""

    sources = load_sources()
    try:
        return sources[source_id]
    except KeyError as exc:
        raise KeyError(f"Unknown source_id: {source_id}") from exc
