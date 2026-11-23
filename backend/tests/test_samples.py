"""All catalogue starters have deterministic, labelled, coherent sample data."""

import json

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
    assert {r["date"] for r in fixture["rows"]} == {"2026-09-30", "2026-10-31"}
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
