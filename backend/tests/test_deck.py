"""The .pptx deck that presents a generated dashboard."""

import io

import pytest
from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE

from app.deck.builder import SCAFFOLD_NOTE, build_deck

SPEC = {
    "title": "Regional Sales",
    "subtitle": "This month",
    "layout": "analytics-breakdown",
    "theme": "teal",
    "widgets": [
        {"kind": "stat", "endpoint": "/api/kpi", "label": "Revenue", "field": "revenue"},
        {
            "kind": "line",
            "endpoint": "/api/trend",
            "title": "Revenue by day",
            "xField": "day",
            "series": [{"label": "Revenue", "field": "revenue"}],
        },
        {
            "kind": "bar",
            "endpoint": "/api/regions",
            "title": "Revenue by region",
            "categoryField": "region",
            "series": [
                {"label": "This year", "field": "current"},
                {"label": "Last year", "field": "previous"},
            ],
        },
    ],
}

REQUIREMENTS = {
    "problem": "Managers cannot see regional revenue without asking finance.",
    "targetUsers": ["Regional sales managers", "Finance team"],
    "mainWorkflow": ["Open the dashboard", "Compare regions", "Drill into orders"],
    "successCriteria": ["A manager sees this month's revenue in five seconds"],
}


@pytest.fixture()
def deck() -> Presentation:
    return Presentation(io.BytesIO(build_deck(SPEC, REQUIREMENTS)))


def test_deck_is_a_readable_pptx(deck: Presentation):
    """Opening it is the test: a corrupt file would raise here."""
    assert len(deck.slides) >= 6


def test_deck_is_widescreen(deck: Presentation):
    """4:3 would letterbox on every modern projector."""
    ratio = deck.slide_width / deck.slide_height
    assert round(ratio, 2) == round(16 / 9, 2)


def test_deck_opens_on_the_dashboard_title(deck: Presentation):
    text = "\n".join(
        shape.text_frame.text for shape in deck.slides[0].shapes if shape.has_text_frame
    )
    assert "Regional Sales" in text
    assert "This month" in text


def test_deck_carries_the_requirements(deck: Presentation):
    everything = "\n".join(
        shape.text_frame.text
        for slide in deck.slides
        for shape in slide.shapes
        if shape.has_text_frame
    )
    assert "asking finance" in everything
    assert "Regional sales managers" in everything
    assert "Compare regions" in everything
    assert "five seconds" in everything


def test_every_chart_widget_becomes_a_native_editable_chart(deck: Presentation):
    """Native charts, not images: the team must be able to edit them."""
    charts = [shape.chart for slide in deck.slides for shape in slide.shapes if shape.has_chart]
    assert len(charts) == 2  # one line widget, one bar widget

    kinds = {chart.chart_type for chart in charts}
    assert XL_CHART_TYPE.LINE_MARKERS in kinds
    assert XL_CHART_TYPE.COLUMN_CLUSTERED in kinds


def test_multi_series_charts_get_a_legend_and_single_series_do_not():
    """Identity is never colour alone, but one series needs no legend box."""
    deck = Presentation(io.BytesIO(build_deck(SPEC, REQUIREMENTS)))
    by_series = {
        len(list(shape.chart.series)): shape.chart
        for slide in deck.slides
        for shape in slide.shapes
        if shape.has_chart
    }
    assert by_series[1].has_legend is False
    assert by_series[2].has_legend is True


def test_scaffolded_series_are_labelled_as_such(deck: Presentation):
    """Never present invented numbers as measurements."""
    everything = "\n".join(
        shape.text_frame.text
        for slide in deck.slides
        for shape in slide.shapes
        if shape.has_text_frame
    )
    assert SCAFFOLD_NOTE in everything
    assert "/api/trend" in everything  # the real source is named


def test_deck_survives_a_spec_with_no_charts_and_empty_requirements():
    spec = {"title": "Bare", "layout": "kpi-overview", "widgets": [SPEC["widgets"][0]]}
    result = Presentation(io.BytesIO(build_deck(spec, {})))
    assert len(result.slides) >= 5
    assert not any(shape.has_chart for slide in result.slides for shape in slide.shapes)


def test_unknown_theme_falls_back_rather_than_raising():
    spec = {**SPEC, "theme": "chartreuse"}
    assert len(Presentation(io.BytesIO(build_deck(spec, REQUIREMENTS))).slides) >= 6
