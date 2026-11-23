"""Platform preparation shared by stub and LLM generation, never a model write."""

import inspect
import json
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from app.design import systems as design
from app.generation.samples import aggregate_payloads, sample_for
from app.generation.spec import normalize_spec, validate_spec
from app.ingest import spreadsheet
from app.workspace import workspace as ws

DATASET_PATH = "backend/data/dataset.json"
FIXTURE_PATH = "backend/data/fixture.json"
DASHBOARD_SPEC_PATH = "frontend/src/dashboard.config.json"
DESIGN_CSS_PATH = "frontend/src/kit/design.css"
PROTECTED_DATA = {DATASET_PATH, FIXTURE_PATH}


def prepare_inputs(requirements: dict, dataset: Any) -> tuple[dict, dict]:
    """Uploads win unconditionally. Never add sample rows/targets to an upload."""
    content = deepcopy(requirements)
    content.pop("sample", None)
    if dataset is not None:
        content["dataset"] = spreadsheet.summary(dataset)
        return content, {"columns": [asdict(c) for c in dataset.columns], "rows": dataset.rows}
    fixture = sample_for(content.get("scenarioId"))
    rows = fixture["rows"]
    columns = [
        {
            "key": key,
            "label": key.replace("_", " ").capitalize(),
            "type": "number" if isinstance(value, (int, float)) else "string",
        }
        for key, value in rows[0].items()
    ]
    content["dataset"] = {
        "columns": columns,
        "rowCount": len(rows),
        "fileRowCount": len(rows),
        "examples": rows[:3],
        "provenance": fixture["provenance"],
    }
    content["sample"] = {k: fixture[k] for k in ("metric", "provenance", "chartGuidance", "spec")}
    return content, {"columns": columns, "rows": rows}


def write_dashboard(
    project_id: str,
    requirements: dict,
    architecture: dict,
    data: dict | None = None,
) -> list[str]:
    """Resolve authoritative provenance/theme/spec, and write finite protected data."""
    chosen = architecture.get("designSystem") or {}
    system = design.resolve(chosen.get("palette"), chosen.get("fonts"), chosen.get("style"))
    spec = normalize_spec(architecture)
    spec["designSystem"] = {
        "palette": system.palette.id,
        "fonts": system.fonts.id,
        "style": system.style,
    }
    dataset = requirements.get("dataset") or {}
    sample = requirements.get("sample")
    if sample:
        spec["provenance"] = deepcopy(sample["provenance"])
        spec.pop("source", None)
    elif dataset.get("filename"):
        spec["provenance"] = {"kind": "upload"}
        rows = int(dataset.get("rowCount") or 0)
        spec["source"] = {
            "filename": dataset["filename"],
            "rows": rows,
            "fileRows": int(dataset.get("fileRowCount") or rows),
        }
    else:
        spec["provenance"] = {"kind": "unknown"}
        spec.pop("source", None)
    errors = validate_spec(spec)
    if errors:
        raise ValueError("Invalid prepared dashboard: " + "; ".join(errors[:6]))
    written = []
    if data is not None:
        ws.write_file(
            project_id, DATASET_PATH, json.dumps(data, ensure_ascii=False, allow_nan=False)
        )
        written.append(DATASET_PATH)
    if sample:
        ws.write_file(
            project_id,
            FIXTURE_PATH,
            json.dumps(
                {k: sample[k] for k in ("metric", "provenance", "chartGuidance")},
                allow_nan=False,
            ),
        )
        written.append(FIXTURE_PATH)
    ws.write_file(
        project_id,
        DASHBOARD_SPEC_PATH,
        json.dumps(
            spec,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n",
    )
    ws.write_file(project_id, DESIGN_CSS_PATH, design.design_css(system))
    return [*written, DASHBOARD_SPEC_PATH, DESIGN_CSS_PATH]


def stub_architecture(requirements: dict) -> dict:
    sample = requirements.get("sample")
    if sample:
        return deepcopy(sample["spec"])
    dataset = requirements.get("dataset")
    if not dataset:
        return sample_for(requirements.get("scenarioId"))["spec"]
    columns = dataset["columns"]
    numeric = next((c for c in columns if c["type"] == "number"), None)
    widgets = []
    if numeric:
        widgets.append(
            {
                "kind": "stat",
                "label": f"Total {numeric['label']}",
                "field": "total",
                "endpoint": "/api/metrics",
            }
        )
    widgets.append(
        {
            "kind": "table",
            "title": "Uploaded records",
            "endpoint": "/api/records",
            "columns": [{"label": c["label"], "field": c["key"]} for c in columns],
        }
    )
    return normalize_spec(
        {
            "title": "Uploaded data overview",
            "layout": "records-workspace",
            "provenance": {"kind": "upload"},
            "widgets": widgets,
        }
    )


def stub_backend_source(requirements: dict) -> str:
    """Self-contained generated API; uses its dataset file, not platform imports."""
    header = (
        "import json\nfrom pathlib import Path\nfrom fastapi import FastAPI\n\n"
        "app = FastAPI(title='Generated dashboard')\n"
        "DATA = Path(__file__).parent / 'data' / 'dataset.json'\n"
        "@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n\n"
    )
    if requirements.get("sample"):
        metric = requirements["sample"]["metric"]
        return (
            header
            + inspect.getsource(aggregate_payloads)
            + "\n"
            + f"METRIC = {metric!r}\n"
            + "def payloads():\n    return aggregate_payloads(json.loads(DATA.read_text())['rows'], METRIC)\n"
            + "@app.get('/api/metrics')\ndef metrics():\n    return payloads()['/api/metrics']\n"
            + "@app.get('/api/series')\ndef series():\n    return payloads()['/api/series']\n"
            + "@app.get('/api/breakdown')\ndef breakdown():\n    return payloads()['/api/breakdown']\n"
            + "@app.get('/api/records')\ndef records():\n    return payloads()['/api/records']\n"
        )
    numeric = next(
        (
            c["key"]
            for c in requirements.get("dataset", {}).get("columns", [])
            if c["type"] == "number"
        ),
        None,
    )
    return (
        header
        + "def rows():\n    return json.loads(DATA.read_text())['rows']\n"
        + f"FIELD = {numeric!r}\n"
        + "@app.get('/api/metrics')\ndef metrics():\n"
        + "    numbers = [r[FIELD] for r in rows() if isinstance(r.get(FIELD), (int, float))]\n"
        + "    return {'total': sum(numbers), 'sampleCount': len(numbers)}\n"
        + "@app.get('/api/records')\ndef records():\n    return rows()\n"
    )
