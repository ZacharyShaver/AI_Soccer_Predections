"""Altitude reference + acclimatization helpers.

Validated in the 2026-06-28 edge-hunt session: at high-altitude venues the away
team underperforms Elo's expectation in proportion to how far it climbed above
its own baseline altitude (monotone, large at >2500m). Elo prices it only
partially. This module isolates the curated altitude data and the leak-free
baseline computation so both the betting tool and any future model variant can
share one source of truth.
"""

from __future__ import annotations

import unicodedata

import pandas as pd

# Metres above sea level for football cities/venues above ~1000 m. Curated
# (no external feed; effect is negligible below ~1500 m).
ALTITUDE_M: dict[str, int] = {
    "mexico city": 2240, "toluca": 2660, "puebla": 2135, "pachuca": 2400,
    "guadalajara": 1566, "leon": 1815, "queretaro": 1820, "saltillo": 1600,
    "la paz": 3640, "oruro": 3706, "cochabamba": 2558, "sucre": 2810,
    "quito": 2850, "ambato": 2577, "riobamba": 2754, "cuenca": 2560,
    "bogota": 2640, "medellin": 1495, "tunja": 2820, "pasto": 2527,
    "cusco": 3399, "arequipa": 2335, "juliaca": 3825, "huancayo": 3259,
    "san jose": 1170, "guatemala city": 1500, "addis ababa": 2355,
    "johannesburg": 1753, "pretoria": 1339, "nairobi": 1795, "asmara": 2325,
    "denver": 1609, "calgary": 1045,
}

ALTITUDE_FLOOR_M = 1000  # below this, no adjustment


def _normalize(name: object) -> str:
    if not isinstance(name, str):
        return ""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = text.lower().split("(")[0].strip()  # "Guadalajara (Zapopan)" -> "guadalajara"
    return text


def altitude_for(name: object) -> int:
    """Metres for a city/venue string (0 if unknown / sea level)."""
    norm = _normalize(name)
    if not norm:
        return 0
    if norm in ALTITUDE_M:
        return ALTITUDE_M[norm]
    for key, metres in ALTITUDE_M.items():
        if key in norm:
            return metres
    return 0


def team_altitude_baselines(matches_df: pd.DataFrame) -> dict[str, float]:
    """Each team's baseline altitude = median altitude of its non-neutral home games."""
    by_team: dict[str, list[int]] = {}
    if matches_df is None or matches_df.empty or "city" not in matches_df.columns:
        return {}
    for row in matches_df.itertuples(index=False):
        if bool(getattr(row, "neutral", False)):
            continue
        team = str(getattr(row, "home_team_id", ""))
        if team:
            by_team.setdefault(team, []).append(altitude_for(getattr(row, "city", None)))
    return {team: float(pd.Series(v).median()) for team, v in by_team.items()}


def home_advantage_delta_elo(
    venue: object,
    home_team_id: str,
    away_team_id: str,
    baselines: dict[str, float],
    *,
    coef: float = 60.0,
) -> float:
    """Extra Elo points for the home side from altitude acclimatization.

    Positive => favours the home side (away team climbed more than home).
    ``coef`` Elo per 1000 m of net climb (validated ~60). Returns 0 below the
    altitude floor.
    """
    alt = altitude_for(venue)
    if alt < ALTITUDE_FLOOR_M or coef == 0.0:
        return 0.0
    climb_away = max(0.0, alt - baselines.get(str(away_team_id), 0.0))
    climb_home = max(0.0, alt - baselines.get(str(home_team_id), 0.0))
    return coef * (climb_away - climb_home) / 1000.0
