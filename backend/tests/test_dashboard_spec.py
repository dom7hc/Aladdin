"""Dashboard spec validation — the gate between the model and the renderer."""

from app.generation.spec import LAYOUTS, THEMES, prune_filters, spec_endpoints, validate_spec

GOOD = {
    "title": "Orders",
    "subtitle": "Last 30 days",
    "layout": "analytics-breakdown",
    "theme": "teal",
    "widgets": [
        {
            "kind": "stat",
            "endpoint": "/api/metrics",
            "label": "Orders",
            "field": "total",
            "deltaField": "change",
            "trendField": "trend",
        },
        {
            "kind": "line",
            "endpoint": "/api/series",
            "title": "Orders over time",
            "xField": "day",
            "series": [{"label": "Orders", "field": "value"}],
        },
        {
            "kind": "bar",
            "endpoint": "/api/by-region",
            "title": "By region",
            "categoryField": "region",
            "series": [{"label": "Orders", "field": "value"}],
        },
        {
            "kind": "table",
            "endpoint": "/api/orders",
            "title": "Recent orders",
            "columns": [{"label": "Ref", "field": "ref"}, {"label": "Total", "field": "total"}],
        },
        {
            "kind": "status",
            "endpoint": "/api/health",
            "title": "Feeds",
            "labelField": "name",
            "levelField": "level",
        },
    ],
    "filters": [{"label": "Region", "field": "region", "options": ["All", "EU", "US"]}],
}


def test_a_complete_spec_passes():
    assert validate_spec(GOOD) == []


def test_every_layout_and_theme_in_the_kit_is_accepted():
    """Guards against the Python list and kit/types.ts drifting apart."""
    for layout in LAYOUTS:
        assert validate_spec({**GOOD, "layout": layout}) == []
    for theme in THEMES:
        assert validate_spec({**GOOD, "theme": theme}) == []


def test_a_non_dashboard_layout_is_rejected():
    errors = validate_spec({**GOOD, "layout": "chatbot"})
    assert any("layout" in e for e in errors)


def test_unknown_widget_kind_is_rejected():
    spec = {**GOOD, "widgets": [{"kind": "chat", "endpoint": "/api/x"}]}
    assert any("kind" in e for e in validate_spec(spec))


def test_widget_missing_required_fields_is_rejected():
    spec = {**GOOD, "widgets": [{"kind": "line", "endpoint": "/api/s", "title": "T"}]}
    errors = validate_spec(spec)
    assert any("xField" in e for e in errors)
    assert any("series" in e for e in errors)


def test_endpoint_must_be_an_api_path():
    """A widget pointing anywhere but /api/ would fetch the dashboard's own HTML."""
    spec = {**GOOD, "widgets": [{**GOOD["widgets"][0], "endpoint": "https://example.test/x"}]}
    assert any("endpoint" in e for e in validate_spec(spec))


def test_series_cannot_exceed_the_palette():
    """The categorical palette has eight slots and is never cycled."""
    many = [{"label": f"S{i}", "field": f"f{i}"} for i in range(9)]
    spec = {**GOOD, "widgets": [{**GOOD["widgets"][1], "series": many}]}
    assert any("series" in e for e in validate_spec(spec))


def test_empty_and_malformed_specs_are_rejected():
    assert validate_spec("not a spec") == ["spec must be a JSON object"]
    assert any("widgets" in e for e in validate_spec({"title": "x", "layout": "kpi-overview"}))
    assert any("title" in e for e in validate_spec({**GOOD, "title": "  "}))


def test_unusable_filters_are_pruned_not_fatal():
    """Observed live: the architect emitted three filters with empty options.

    Failing a whole generation for optional sugar is disproportionate, and the
    model cannot know what values exist in data it has not generated yet.
    """
    spec = {
        **GOOD,
        "filters": [
            {"label": "Region", "field": "region", "options": []},
            {"label": "Tier", "field": "tier", "options": ["A", "B"]},
            "not even an object",
        ],
    }
    assert prune_filters(spec) == 2
    assert spec["filters"] == [{"label": "Tier", "field": "tier", "options": ["A", "B"]}]
    assert validate_spec(spec) == []


def test_filters_key_disappears_when_none_survive():
    spec = {**GOOD, "filters": [{"field": "region", "options": []}]}
    assert prune_filters(spec) == 1
    assert "filters" not in spec
    assert validate_spec(spec) == []


def test_layouts_and_themes_match_the_typescript_kit():
    """The same names live in Python and in the kit; nothing else stops drift.

    A layout the validator accepts but the renderer does not know would produce
    a dashboard that silently falls back to the wrong arrangement.
    """
    import re
    from pathlib import Path

    from app.config import TEMPLATES_DIR

    kit = Path(TEMPLATES_DIR) / "default-poc" / "frontend" / "src" / "kit"
    types_ts = (kit / "types.ts").read_text(encoding="utf-8")
    declared = set(re.findall(r'^\s*\|?\s*"([a-z-]+)";?\s*$', types_ts, re.MULTILINE))
    assert LAYOUTS <= declared, f"kit/types.ts is missing layouts: {LAYOUTS - declared}"

    theme_css = (kit / "theme.css").read_text(encoding="utf-8")
    styled = set(re.findall(r'\[data-theme="([a-z]+)"\]', theme_css))
    assert THEMES <= styled, f"theme.css has no tokens for: {THEMES - styled}"


def test_spec_endpoints_are_deduplicated():
    """Drives the fetch-once-per-endpoint behaviour in the renderer."""
    assert spec_endpoints(GOOD) == {
        "/api/metrics",
        "/api/series",
        "/api/by-region",
        "/api/orders",
        "/api/health",
    }
    duplicated = {**GOOD, "widgets": [GOOD["widgets"][0], GOOD["widgets"][0]]}
    assert spec_endpoints(duplicated) == {"/api/metrics"}
