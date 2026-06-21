"""Resolve source-specific team names to stable canonical team ids."""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from wc_predictor.config import settings


REQUIRED_COLUMNS = {
    "canonical_team_id",
    "canonical_name",
    "source_name",
    "source_team_name",
    "valid_from",
    "valid_to",
    "confidence",
    "manual_review_status",
}


@dataclass(frozen=True)
class TeamAlias:
    canonical_team_id: str
    canonical_name: str


def normalize_team_name(value: str) -> str:
    """Normalize only exact-match noise: case, whitespace, and diacritics."""

    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    collapsed = re.sub(r"\s+", " ", without_marks.strip())
    return collapsed.casefold()


def _default_alias_path() -> Path:
    return settings.CONFIG_DIR / "team_aliases.csv"


class TeamAliasResolver:
    def __init__(self, aliases: dict[tuple[str, str], TeamAlias]) -> None:
        self._aliases = aliases

    @classmethod
    def from_csv(cls, path: str | Path | None = None) -> "TeamAliasResolver":
        alias_path = Path(path) if path is not None else _default_alias_path()
        aliases: dict[tuple[str, str], TeamAlias] = {}

        with alias_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or [])
            missing_columns = REQUIRED_COLUMNS - columns
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise ValueError(f"{alias_path}: missing columns: {missing}")

            for line_number, row in enumerate(reader, start=2):
                source_name = (row["source_name"] or "").strip()
                source_team_name = (row["source_team_name"] or "").strip()
                canonical_team_id = (row["canonical_team_id"] or "").strip()
                canonical_name = (row["canonical_name"] or "").strip()

                if not all(
                    [source_name, source_team_name, canonical_team_id, canonical_name]
                ):
                    raise ValueError(
                        f"{alias_path}:{line_number}: alias rows require source, "
                        "source_team_name, canonical_team_id, and canonical_name"
                    )

                key = (source_name.casefold(), normalize_team_name(source_team_name))
                alias = TeamAlias(
                    canonical_team_id=canonical_team_id,
                    canonical_name=canonical_name,
                )
                existing = aliases.get(key)
                if existing is not None and existing != alias:
                    raise ValueError(
                        f"{alias_path}:{line_number}: conflicting alias for "
                        f"{source_name}:{source_team_name}"
                    )
                aliases[key] = alias

        return cls(aliases)

    def resolve(self, name: str, source: str) -> TeamAlias:
        normalized_name = normalize_team_name(name)
        normalized_source = source.strip().casefold()

        source_key = (normalized_source, normalized_name)
        manual_key = ("manual", normalized_name)
        alias = self._aliases.get(source_key) or self._aliases.get(manual_key)
        if alias is None:
            raise KeyError(
                f"Unknown team alias {name!r} for source {source!r}; "
                "add it to config/team_aliases.csv"
            )
        return alias

    def unresolved_names(self, names: set[str], source: str) -> list[str]:
        unresolved: list[str] = []
        for name in sorted(names):
            try:
                self.resolve(name, source=source)
            except KeyError:
                unresolved.append(name)
        return unresolved
