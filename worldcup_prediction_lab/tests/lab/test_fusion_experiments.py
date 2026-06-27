import pandas as pd
import pytest

from wc_predictor.lab import fusion_experiments


class CountingModel:
    def __init__(self):
        self.update_count = 0

    def _update_from_match(self, _row):
        self.update_count += 1

    def predict_match(self, _row):
        home = 0.50 + (0.10 * self.update_count)
        away = 0.20
        draw = 1.0 - home - away
        return type(
            "Prediction",
            (),
            {
                "prob_home": home,
                "prob_draw": draw,
                "prob_away": away,
                "pre_match_home_rating": 1500.0 + self.update_count,
                "pre_match_away_rating": 1490.0,
                "home_advantage_elo": 75.0,
            },
        )()


class FitCountingModel:
    def __init__(self, generated_at_utc: str):
        self.generated_at_utc = generated_at_utc
        self.fit_rows = 0

    def fit(self, train_matches):
        self.fit_rows = len(train_matches)
        return self

    def predict_match(self, _row):
        home = 0.50 + (0.05 * self.fit_rows)
        away = 0.20
        draw = 1.0 - home - away
        return type(
            "Prediction",
            (),
            {
                "prob_home": home,
                "prob_draw": draw,
                "prob_away": away,
                "pre_match_home_rating": 1500.0 + self.fit_rows,
                "pre_match_away_rating": 1490.0,
                "home_advantage_elo": 75.0,
            },
        )()


def _market_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "home_score": 2,
                "away_score": 0,
                "market_prob_home": 0.55,
                "market_prob_draw": 0.25,
                "market_prob_away": 0.20,
                "elo_prob_home": 0.60,
                "elo_prob_draw": 0.25,
                "elo_prob_away": 0.15,
                "form_prob_home": 0.70,
                "form_prob_draw": 0.20,
                "form_prob_away": 0.10,
            },
            {
                "home_score": 1,
                "away_score": 1,
                "market_prob_home": 0.35,
                "market_prob_draw": 0.30,
                "market_prob_away": 0.35,
                "elo_prob_home": 0.40,
                "elo_prob_draw": 0.30,
                "elo_prob_away": 0.30,
                "form_prob_home": 0.25,
                "form_prob_draw": 0.45,
                "form_prob_away": 0.30,
            },
            {
                "home_score": 0,
                "away_score": 1,
                "market_prob_home": 0.30,
                "market_prob_draw": 0.25,
                "market_prob_away": 0.45,
                "elo_prob_home": 0.35,
                "elo_prob_draw": 0.25,
                "elo_prob_away": 0.40,
                "form_prob_home": 0.20,
                "form_prob_draw": 0.25,
                "form_prob_away": 0.55,
            },
        ]
    )


def test_build_market_fusion_frame_aligns_market_and_attaches_variants():
    matches = pd.DataFrame(
        [
            {
                "match_id": "train-before",
                "date": "2026-01-01",
                "home_team_id": "A",
                "away_team_id": "B",
                "home_team": "A",
                "away_team": "B",
                "home_score": 1,
                "away_score": 0,
                "tournament": "Friendly",
            },
            {
                "match_id": "eval-1",
                "date": "2026-01-02",
                "home_team_id": "A",
                "away_team_id": "B",
                "home_team": "A",
                "away_team": "B",
                "home_score": 2,
                "away_score": 1,
                "tournament": "Friendly",
            },
        ]
    )
    market_odds = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "home_team_id": "A",
                "away_team_id": "B",
                "home_team_name": "A",
                "away_team_name": "B",
                "bookmaker": "B365",
                "source_sheet": "2026",
                "prob_home": 0.50,
                "prob_draw": 0.25,
                "prob_away": 0.25,
            }
        ]
    )

    frame, alignment = fusion_experiments.build_market_fusion_frame(
        matches,
        market_odds,
        variant_ids=["alpha"],
        generated_at_utc="2026-06-27T20:50:00Z",
        build_variant=lambda _variant_id, **kw: FitCountingModel(**kw),
    )

    assert alignment.usable_joined_rows == 1
    assert len(frame) == 1
    assert frame.loc[0, "market_prob_home"] == pytest.approx(0.50)
    assert frame.loc[0, "alpha_prob_home"] == pytest.approx(0.55)


def test_add_model_probability_columns_is_leak_free_by_match_date():
    aligned = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "match_id": "eval-1",
                "market_row_id": 1,
                "home_team_id": "A",
                "away_team_id": "B",
            }
        ]
    )
    matches = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "match_id": "train-before",
                "home_team_id": "A",
                "away_team_id": "B",
                "home_score": 1,
                "away_score": 0,
            },
            {
                "date": "2026-01-02",
                "match_id": "same-day-must-not-leak",
                "home_team_id": "C",
                "away_team_id": "D",
                "home_score": 3,
                "away_score": 0,
            },
        ]
    )

    frame = fusion_experiments.add_model_probability_columns(
        aligned,
        matches,
        model_factory=CountingModel,
        prefix="counting",
    )

    assert frame.loc[0, "counting_prob_home"] == pytest.approx(0.60)
    assert frame.loc[0, "counting_prob_draw"] == pytest.approx(0.20)
    assert frame.loc[0, "counting_prob_away"] == pytest.approx(0.20)
    assert frame.loc[0, "counting_home_rating"] == pytest.approx(1501.0)


def test_add_walkforward_model_probability_columns_uses_fit_cutoff():
    aligned = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "match_id": "eval-1",
                "market_row_id": 1,
                "home_team_id": "A",
                "away_team_id": "B",
            },
            {
                "date": "2026-01-03",
                "match_id": "eval-2",
                "market_row_id": 2,
                "home_team_id": "C",
                "away_team_id": "D",
            },
        ]
    )
    matches = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "match_id": "train-before-first",
                "home_team_id": "A",
                "away_team_id": "B",
                "home_score": 1,
                "away_score": 0,
            },
            {
                "date": "2026-01-02",
                "match_id": "same-day-for-first",
                "home_team_id": "C",
                "away_team_id": "D",
                "home_score": 2,
                "away_score": 0,
            },
        ]
    )

    frame = fusion_experiments.add_walkforward_model_probability_columns(
        aligned,
        matches,
        build_model_fn=lambda **kw: FitCountingModel(**kw),
        prefix="fit_counting",
        generated_at_utc="2026-06-27T20:00:00Z",
    )

    assert frame.loc[0, "fit_counting_prob_home"] == pytest.approx(0.55)
    assert frame.loc[1, "fit_counting_prob_home"] == pytest.approx(0.60)
    assert frame.loc[0, "fit_counting_home_rating"] == pytest.approx(1501.0)
    assert frame.loc[1, "fit_counting_home_rating"] == pytest.approx(1502.0)


def test_attach_variant_probability_columns_builds_each_variant():
    aligned = pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "match_id": "eval-1",
                "market_row_id": 1,
                "home_team_id": "A",
                "away_team_id": "B",
            }
        ]
    )
    matches = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "match_id": "train-before",
                "home_team_id": "A",
                "away_team_id": "B",
                "home_score": 1,
                "away_score": 0,
            }
        ]
    )
    built: list[str] = []

    def build_variant(variant_id, **kw):
        built.append(f"{variant_id}:{kw['generated_at_utc']}")
        return FitCountingModel(**kw)

    frame = fusion_experiments.attach_variant_probability_columns(
        aligned,
        matches,
        variant_ids=["alpha", "beta"],
        generated_at_utc="2026-06-27T20:20:00Z",
        build_variant=build_variant,
    )

    assert built == [
        "alpha:2026-06-27T20:20:00Z",
        "beta:2026-06-27T20:20:00Z",
    ]
    assert "alpha_prob_home" in frame.columns
    assert "beta_prob_home" in frame.columns
    assert frame.loc[0, "alpha_prob_home"] == pytest.approx(0.55)
    assert frame.loc[0, "beta_prob_home"] == pytest.approx(0.55)


def test_predict_fn_fuses_selected_variant_columns_in_order():
    predict = fusion_experiments.build_fused_predict_fn(
        variant_ids=["form", "elo"],
        weights=[0.75, 0.25],
        recipe="linear",
    )

    probs = predict(_market_frame().iloc[0])

    assert probs == pytest.approx((0.675, 0.2125, 0.1125))
    assert sum(probs) == pytest.approx(1.0)


def test_build_market_fusion_result_returns_ledger_ready_payload():
    result = fusion_experiments.build_market_fusion_result(
        frame=_market_frame(),
        variant_scores={"elo": 0.1574, "form": 0.1510},
        variant_ids=["form", "elo"],
        recipe="linear",
        weight_scheme="inverse_rps",
        exp_id="fusion-linear-top2-inverse",
        created_utc="2026-06-27T19:30:00Z",
        notes="synthetic market-frame smoke",
    )

    assert result["agent"] == "codex"
    assert result["task"] == "fuse"
    assert result["exp_id"] == "fusion-linear-top2-inverse"
    assert result["created_utc"] == "2026-06-27T19:30:00Z"
    assert result["config"]["recipe"] == "linear"
    assert result["config"]["variant_ids"] == ["form", "elo"]
    assert set(result["config"]["weights"]) == {"form", "elo"}
    assert result["samples"]["market964"]["n"] == 3
    assert "rps" in result["samples"]["market964"]
    assert "vs_market_paired" in result
    assert result["vs_best_constituent_paired"]["best_variant_id"] == "form"
    assert "mean_diff" in result["vs_best_constituent_paired"]
    assert result["notes"] == "synthetic market-frame smoke"
    assert result["promote"] is False


def test_build_market_fusion_result_supports_log_recipe_and_uniform_weights():
    result = fusion_experiments.build_market_fusion_result(
        frame=_market_frame(),
        variant_scores={"elo": 0.1574, "form": 0.1510},
        variant_ids=["form", "elo"],
        recipe="log",
        weight_scheme="uniform",
        exp_id="fusion-log-top2-uniform",
        created_utc="2026-06-27T19:31:00Z",
    )

    assert result["config"]["recipe"] == "log"
    assert result["config"]["weights"] == pytest.approx({"form": 0.5, "elo": 0.5})
    assert result["samples"]["market964"]["n"] == 3


def test_iter_market_fusion_specs_enumerates_fusion_one_and_two_grid():
    specs = list(
        fusion_experiments.iter_market_fusion_specs(
            variant_scores={
                "elo_recalibrated": 0.1574,
                "ensemble_top_k": 0.1582,
                "form_trend": 0.1610,
            },
            k_values=[2, 3],
            recipes=["linear", "log"],
            weight_schemes=["uniform", "inverse_rps"],
        )
    )

    assert [spec["exp_id"] for spec in specs] == [
        "fusion-linear-top2-uniform",
        "fusion-linear-top2-inverse-rps",
        "fusion-log-top2-uniform",
        "fusion-log-top2-inverse-rps",
        "fusion-linear-top3-uniform",
        "fusion-linear-top3-inverse-rps",
        "fusion-log-top3-uniform",
        "fusion-log-top3-inverse-rps",
    ]
    assert specs[0]["variant_ids"] == ["elo_recalibrated", "ensemble_top_k"]
    assert specs[-1]["variant_ids"] == [
        "elo_recalibrated",
        "ensemble_top_k",
        "form_trend",
    ]


def test_run_market_fusion_sweep_returns_and_records_payloads(tmp_path):
    specs = [
        {
            "exp_id": "fusion-linear-top2-uniform",
            "recipe": "linear",
            "weight_scheme": "uniform",
            "variant_ids": ["form", "elo"],
        },
        {
            "exp_id": "fusion-log-top2-uniform",
            "recipe": "log",
            "weight_scheme": "uniform",
            "variant_ids": ["form", "elo"],
        },
    ]

    results = fusion_experiments.run_market_fusion_sweep(
        frame=_market_frame(),
        variant_scores={"elo": 0.1574, "form": 0.1510},
        specs=specs,
        created_utc="2026-06-27T20:15:00Z",
        fusion_dir=tmp_path,
        record_results=True,
    )

    assert [result["exp_id"] for result in results] == [
        "fusion-linear-top2-uniform",
        "fusion-log-top2-uniform",
    ]
    assert all(result["samples"]["market964"]["n"] == 3 for result in results)
    assert sorted(path.name for path in tmp_path.glob("*.json")) == [
        "codex__fusion-linear-top2-uniform__2026-06-27T20-15-00Z.json",
        "codex__fusion-log-top2-uniform__2026-06-27T20-15-00Z.json",
    ]


def test_build_fused_predict_fn_rejects_missing_probability_columns():
    predict = fusion_experiments.build_fused_predict_fn(
        variant_ids=["missing"],
        weights=[1.0],
        recipe="linear",
    )

    with pytest.raises(ValueError, match="missing probability columns"):
        predict(_market_frame().iloc[0])
