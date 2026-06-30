"""In-tournament form: how much a team is over/under-performing its Elo here.

The knockout-stage analog of ``group_incentive`` (which goes dormant once groups
end). Instead of league-table incentives, this keys on *performance within the
current tournament*: for each 2026 World Cup match a team has played, compute the
residual (actual result minus the Elo win-expectation), and average it. A team
beating expectation in this tournament ("hot") gets a small Elo bump; a team
underperforming gets docked. Opponent-adjusted via the Elo expectation, so beating
strong sides counts more than beating minnows.

Leak-free in the lab's established sense: the per-team residual is computed once at
fit time over the training matches (same pattern as ``recent_form``), then applied
as a bounded home-advantage delta at predict time.
"""

from __future__ import annotations

import pandas as pd

from wc_predictor.models.elo import EloModel

VARIANT_ID = "tournament_form"
DESCRIPTION = "Elo adjusted for over/under-performance vs expectation in this World Cup."
FEATURE_IDEA = (
    "Mean residual (actual result - Elo win-expectation) over each team's 2026 WC "
    "matches; hot teams get a small Elo bump, cold teams a small dock. Opponent-adjusted."
)

WC_START = "2026-06-01"
FORM_COEF = 120.0   # residual ~[-0.5, 0.5] -> ~+-60 Elo before the cap
MAX_DELTA = 60.0


def _expectation(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-(rating_a - rating_b) / 400.0))


class TournamentFormElo(EloModel):
    model_version = "tournament_form_v1"

    def fit(self, train_matches_df):
        super().fit(train_matches_df)
        m = train_matches_df.copy()
        if "tournament" not in m.columns or "date" not in m.columns:
            self._tform = {}
            return self
        m["date"] = pd.to_datetime(m["date"], errors="coerce")
        wc = m[
            (m["date"] >= pd.Timestamp(WC_START))
            & (m["tournament"].astype(str).str.contains("World Cup", case=False, na=False))
        ]

        resid: dict[str, list[float]] = {}
        for _, r in wc.iterrows():
            hs, as_ = r.get("home_score"), r.get("away_score")
            if pd.isna(hs) or pd.isna(as_):
                continue
            h, a = str(r["home_team_id"]), str(r["away_team_id"])
            exp_home = _expectation(self.get_rating(h), self.get_rating(a))
            if hs > as_:
                actual_home = 1.0
            elif hs < as_:
                actual_home = 0.0
            else:
                actual_home = 0.5
            resid.setdefault(h, []).append(actual_home - exp_home)
            resid.setdefault(a, []).append((1.0 - actual_home) - (1.0 - exp_home))

        self._tform = {t: sum(v) / len(v) for t, v in resid.items() if v}
        return self

    def _home_advantage_elo(self, match_row, home_team_id, away_team_id):
        base = super()._home_advantage_elo(match_row, home_team_id, away_team_id)
        if not getattr(self, "_tform", None):
            return base
        fh = self._tform.get(str(home_team_id), 0.0)
        fa = self._tform.get(str(away_team_id), 0.0)
        delta = FORM_COEF * (fh - fa)
        delta = max(-MAX_DELTA, min(MAX_DELTA, delta))
        return base + delta


def build_model(*, generated_at_utc: str):
    from wc_predictor.forecast_live import build_world_cup_host_advantage_fn

    return TournamentFormElo(
        k_factor=20.0,
        generated_at_utc=generated_at_utc,
        host_advantage_fn=build_world_cup_host_advantage_fn(),
    )
