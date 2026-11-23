"""All catalogue starters have deterministic, labelled, coherent sample data."""

import json
from itertools import pairwise

import pytest

from app.catalogue import SCENARIOS
from app.generation.samples import SAMPLE_CONFIGS, sample_for
from app.generation.spec import spec_endpoints, validate_spec


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_all_twenty_sample_contracts(scenario):
    fixture = sample_for(scenario.id)
    assert fixture == sample_for(scenario.id)
    assert len(fixture["rows"]) >= 12
    assert fixture["provenance"] == {
        "kind": "sample",
        "label": "Sample data",
        "fixtureId": scenario.id,
        "seed": 14,
        "dateAnchor": "2026-11-01",
    }
    assert validate_spec(fixture["spec"]) == []
    metric = fixture["metric"]
    assert metric["unit"] == fixture["spec"]["hero"]["unit"]
    assert isinstance(metric["lowerIsBetter"], bool)
    assert fixture["spec"]["hero"]["comparison"]["label"] == "Sample target"
    dates = sorted({r["date"] for r in fixture["rows"]})
    assert len(dates) >= 6
    assert dates[-2:] == ["2026-09-30", "2026-10-31"]
    assert len({sum(r["date"] == d for r in fixture["rows"]) for d in dates}) == 1
    # The provenance badge supplies the sample label; subtitle is period-only (B2).
    assert fixture["spec"]["subtitle"] == "October 2026"
    table = next(w for w in fixture["spec"]["widgets"] if w["kind"] == "table")
    assert all(c["field"] != "id" for c in table["columns"])
    assert len(fixture["payloads"]["/api/records"]) == 4
    assert all("variance" in row and "id" not in row for row in fixture["payloads"]["/api/records"])
    assert fixture["chartGuidance"]["reason"]
    assert spec_endpoints(fixture["spec"]) <= set(fixture["payloads"])
    json.dumps(fixture, allow_nan=False)


def test_registry_exactly_covers_catalogue_and_custom_fallback():
    assert set(SAMPLE_CONFIGS) == {s.id for s in SCENARIOS}
    fixture = sample_for("custom-live-case")
    assert fixture == sample_for(None)
    assert fixture["provenance"]["fixtureId"] == "generic"
    assert fixture["spec"]["title"] == "Sample activity overview"


def test_current_and_reference_are_derived_from_rows():
    fixture = sample_for("budget-vs-actual")
    rows = [r for r in fixture["rows"] if r["date"] == "2026-10-31"]
    metric = fixture["metric"]
    assert fixture["payloads"]["/api/metrics"]["actual"] == sum(r[metric["field"]] for r in rows)
    assert fixture["payloads"]["/api/metrics"]["target"] == sum(r["sample_target"] for r in rows)
    assert all(p["actual"] >= 0 for p in fixture["payloads"]["/api/breakdown"])


def test_sample_stories_vary_across_starters():
    """Sample dashboards must not all be red with the same trend (Opus B2 review F1)."""
    heroes, mixed, trends = set(), 0, set()
    for scenario_id in SAMPLE_CONFIGS:
        fixture = sample_for(scenario_id)
        lower = fixture["spec"]["hero"]["lowerIsBetter"]
        metrics = fixture["payloads"]["/api/metrics"]
        heroes.add((metrics["actual"] < metrics["target"]) == lower)
        bars = fixture["payloads"]["/api/breakdown"]
        misses = sum((b["actual"] > b["target"]) == lower for b in bars)
        mixed += 0 < misses < len(bars)
        series = [p["actual"] for p in fixture["payloads"]["/api/series"]]
        trends.add(tuple(b > a for a, b in pairwise(series)))
    assert heroes == {True, False}, "some starters on target, some off"
    assert mixed == len(SAMPLE_CONFIGS), "every starter mixes met and missed categories"
    assert len(trends) >= 3, "at least three different trend shapes"
