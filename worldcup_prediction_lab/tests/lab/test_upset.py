import pytest

from wc_predictor.lab.upset import assess_upset_risk, format_upset_risk


def test_upset_risk_treats_away_underdog_win_or_draw_as_risk():
    risk = assess_upset_risk((0.62, 0.23, 0.15))

    assert risk.favorite == "home"
    assert risk.underdog == "away"
    assert risk.underdog_avoid_defeat_probability == pytest.approx(0.38)
    assert risk.percent == pytest.approx(38.0)


def test_upset_risk_for_home_underdog_uses_home_win_or_draw():
    risk = assess_upset_risk((0.18, 0.27, 0.55))

    assert risk.favorite == "away"
    assert risk.underdog == "home"
    assert risk.underdog_avoid_defeat_probability == pytest.approx(0.45)
    assert risk.percent == pytest.approx(45.0)


def test_upset_risk_increases_when_favorite_is_fragile():
    confident = assess_upset_risk((0.78, 0.14, 0.08))
    fragile = assess_upset_risk((0.47, 0.29, 0.24))

    assert fragile.percent > confident.percent
    assert confident.label == "Low"
    assert fragile.label in {"Medium", "High"}


def test_format_upset_risk_returns_display_text():
    risk = assess_upset_risk((0.51, 0.29, 0.20))

    assert format_upset_risk(risk) == f"{risk.percent:.0f}% {risk.label}"


def test_dashboard_upset_cell_includes_percent_label_and_underdog():
    from wc_predictor.lab.dashboard import _upset_cell

    cell = _upset_cell((0.51, 0.29, 0.20))

    assert "49% High" in cell
    assert "underdog: away" in cell


def test_dashboard_writes_github_pages_copy(tmp_path):
    from wc_predictor.lab.dashboard import _write_dashboard_outputs

    dashboard_path = tmp_path / "research" / "dashboard.html"
    pages_path = tmp_path / "docs" / "index.html"

    written = _write_dashboard_outputs(
        "<!doctype html><title>Report</title>",
        out_path=dashboard_path,
        publish_pages=True,
        pages_path=pages_path,
    )

    assert written == dashboard_path
    assert dashboard_path.read_text(encoding="utf-8") == "<!doctype html><title>Report</title>"
    assert pages_path.read_text(encoding="utf-8") == "<!doctype html><title>Report</title>"


def test_dashboard_css_keeps_result_cards_wide_enough_for_mini_table():
    from wc_predictor.lab.dashboard import _TEMPLATE

    assert "minmax(440px,1fr)" in _TEMPLATE
    assert ".mini{{font-size:11px;table-layout:fixed}}" in _TEMPLATE
