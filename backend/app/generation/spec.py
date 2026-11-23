"""Validation for the dashboard spec the generator produces.

The spec is the only frontend file the model writes: everything visual is
platform-owned in the template's ``frontend/src/kit/``. Keep this in step with
``kit/types.ts``, which describes the same shape for the renderer.

Validating before anything is written means a malformed spec fails the run with
an actionable message instead of producing a dashboard that renders empty.
"""

import json
import re
from copy import deepcopy
from datetime import datetime
from typing import Any

# operations-monitor is deliberately absent: it existed only to arrange status
# widgets, and health pills are engineering furniture that a non-technical user
# does not need on an HR or sales dashboard.
LAYOUTS = {
    "kpi-overview",
    "analytics-breakdown",
    "records-workspace",
}

THEMES = {"indigo", "teal", "amber", "rose", "violet", "graphite"}

# Fields each widget kind needs beyond "kind" and "endpoint".
REQUIRED_BY_KIND: dict[str, tuple[str, ...]] = {
    "stat": ("label", "field"),
    "line": ("title", "xField", "series"),
    "bar": ("title", "categoryField", "series"),
    "donut": ("title", "categoryField", "valueField"),
    "progress": ("title", "labelField", "valueField", "targetField"),
    "ranking": ("title", "labelField", "valueField"),
    "table": ("title", "columns"),
}

# A dashboard with no way to show a number is not a dashboard.
_VISUAL_KINDS = set(REQUIRED_BY_KIND)

# Stat tile icons, in step with the template's kit/icons.tsx. Not validated:
# the kit guesses one from the label when the name is unknown, which beats
# failing a generation over an icon.
ICONS = (
    "users",
    "money",
    "cart",
    "package",
    "trend",
    "clock",
    "calendar",
    "check",
    "alert",
    "activity",
    "target",
    "bolt",
    "star",
    "truck",
    "building",
    "heart",
    "globe",
    "percent",
    "file",
    "chart",
    "gauge",
    "thermometer",
)

MAX_WIDGETS = 10
# The series palette has eight slots and is never cycled.
MAX_SERIES = 8
SCHEMA_VERSION = 2
_API_PATH = re.compile(r"/api/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*")


def safe_endpoint(value: Any) -> bool:
    """Only local absolute GET paths; no query, encoding or path normalization."""
    return isinstance(value, str) and _API_PATH.fullmatch(value) is not None


def _bindings(spec: dict[str, Any]) -> list[dict[str, Any]]:
    widgets = spec.get("widgets", [])
    result = [w for w in widgets if isinstance(w, dict)] if isinstance(widgets, list) else []
    if isinstance(spec.get("hero"), dict):
        result.append(spec["hero"])
    return result


def normalize_spec(value: Any) -> Any:
    """Non-mutating, idempotent legacy defaults BEFORE validation.

    Cosmetic/optional filters are recoverable; unsafe paths never are. Do not
    guess metric direction or invent a comparison for an uploaded/legacy spec.
    """
    spec = deepcopy(value)
    if not isinstance(spec, dict):
        return spec
    for binding in _bindings(spec):
        for item in (binding, binding.get("comparison")):
            if (
                isinstance(item, dict)
                and "endpoint" in item
                and not safe_endpoint(item["endpoint"])
            ):
                raise ValueError("unsafe endpoint in dashboard spec")
    spec.setdefault("schemaVersion", SCHEMA_VERSION)
    spec.setdefault("provenance", {"kind": "upload" if spec.get("source") else "unknown"})
    widgets = spec.get("widgets")
    if isinstance(widgets, list):
        for index, widget in enumerate(widgets):
            if isinstance(widget, dict):
                widget.setdefault("id", f"widget-{index + 1}")
        if "hero" not in spec:
            stat = next(
                (w for w in widgets if isinstance(w, dict) and w.get("kind") == "stat"), None
            )
            spec["hero"] = (
                {
                    k: deepcopy(stat[k])
                    for k in (
                        "id",
                        "endpoint",
                        "label",
                        "field",
                        "unit",
                        "lowerIsBetter",
                        "comparison",
                    )
                    if k in stat
                }
                if stat
                else None
            )
        if isinstance(spec.get("hero"), dict):
            spec["hero"].setdefault("lowerIsBetter", None)
            spec["hero"].setdefault("minSamples", 2)
    prune_filters(spec)
    return spec


def _finite_json(value: Any) -> bool:
    try:
        json.dumps(value, allow_nan=False)
        return True
    except (TypeError, ValueError, OverflowError):
        return False


def _check_binding(binding: dict[str, Any], where: str, errors: list[str]) -> None:
    if not safe_endpoint(binding.get("endpoint")):
        errors.append(f"{where}: unsafe endpoint")
    if "unit" in binding and not isinstance(binding["unit"], str):
        errors.append(f"{where}: unit must be a string")
    direction = binding.get("lowerIsBetter")
    if direction is not None and not isinstance(direction, bool):
        errors.append(f"{where}: lowerIsBetter must be boolean or null (unknown)")
    comparison = binding.get("comparison")
    if comparison is None:
        return
    if not isinstance(comparison, dict):
        errors.append(f"{where}: comparison must be an object")
        return
    for key in ("label", "field", "unit"):
        if not isinstance(comparison.get(key), str) or not comparison[key].strip():
            errors.append(f"{where}: comparison needs {key}")
    if comparison.get("kind") not in ("target", "prior"):
        errors.append(f"{where}: comparison kind must be target or prior")
    if not safe_endpoint(comparison.get("endpoint")):
        errors.append(f"{where}: comparison unsafe endpoint")
    if comparison.get("unit") != binding.get("unit", ""):
        errors.append(f"{where}: comparison unit must match current unit")
    if (
        comparison.get("kind") == "prior"
        and binding.get("kind") not in (None, "stat")
        and (not isinstance(comparison.get("keyField"), str) or not comparison["keyField"])
    ):
        errors.append(f"{where}: prior series needs keyField alignment")


def _check_series(widget: dict[str, Any], where: str, errors: list[str]) -> None:
    series = widget.get("series")
    if not isinstance(series, list) or not series:
        errors.append(f"{where}: 'series' must be a non-empty array")
        return
    if len(series) > MAX_SERIES:
        errors.append(f"{where}: at most {MAX_SERIES} series (the palette has {MAX_SERIES} slots)")
    for index, entry in enumerate(series):
        if not isinstance(entry, dict):
            errors.append(f"{where}: series[{index}] must be an object")
            continue
        for key in ("label", "field"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                errors.append(f"{where}: series[{index}] needs a non-empty '{key}'")


def _check_columns(widget: dict[str, Any], where: str, errors: list[str]) -> None:
    columns = widget.get("columns")
    if not isinstance(columns, list) or not columns:
        errors.append(f"{where}: 'columns' must be a non-empty array")
        return
    for index, entry in enumerate(columns):
        if not isinstance(entry, dict):
            errors.append(f"{where}: columns[{index}] must be an object")
            continue
        for key in ("label", "field"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                errors.append(f"{where}: columns[{index}] needs a non-empty '{key}'")


def validate_spec(spec: Any) -> list[str]:
    """Return every problem with a dashboard spec; empty means it is usable."""
    errors: list[str] = []

    if not isinstance(spec, dict):
        return ["spec must be a JSON object"]
    if not _finite_json(spec):
        errors.append("spec must contain finite JSON values")
    if spec.get("schemaVersion", SCHEMA_VERSION) != SCHEMA_VERSION:
        errors.append("unsupported schemaVersion")
    provenance = spec.get("provenance")
    if provenance is not None and (
        not isinstance(provenance, dict)
        or provenance.get("kind") not in ("unknown", "sample", "upload")
    ):
        errors.append("invalid provenance")
    hero = spec.get("hero")
    if hero is not None:
        if not isinstance(hero, dict):
            errors.append("hero must be an object or null")
        else:
            _check_binding(hero, "hero", errors)
            for key in ("id", "label", "field"):
                if not isinstance(hero.get(key), str) or not hero[key].strip():
                    errors.append(f"hero needs {key}")
            minimum = hero.get("minSamples", 2)
            if type(minimum) is not int or minimum < 2:
                errors.append("hero minSamples must be an integer >=2")

    if not isinstance(spec.get("title"), str) or not spec["title"].strip():
        errors.append("'title' must be a non-empty string")

    layout = spec.get("layout")
    if layout not in LAYOUTS:
        errors.append(f"'layout' must be one of {sorted(LAYOUTS)}, got {layout!r}")

    design = spec.get("designSystem")
    if design is not None:
        if not isinstance(design, dict):
            errors.append("'designSystem' must be an object when present")
        else:
            # Unknown ids are not fatal: systems.resolve falls back to the
            # default, which is better than failing a whole generation over a
            # cosmetic choice. Only a wrong shape is an error.
            for key in ("palette", "fonts", "style"):
                value = design.get(key)
                if value is not None and not isinstance(value, str):
                    errors.append(f"designSystem.{key} must be a string id")

    theme = spec.get("theme")
    if theme is not None and theme not in THEMES:
        errors.append(f"'theme' must be one of {sorted(THEMES)}, got {theme!r}")

    widgets = spec.get("widgets")
    if not isinstance(widgets, list) or not widgets:
        errors.append("'widgets' must be a non-empty array")
        return errors
    if len(widgets) > MAX_WIDGETS:
        errors.append(f"at most {MAX_WIDGETS} widgets")
    ids = [w.get("id") for w in widgets if isinstance(w, dict) and "id" in w]
    if any(not isinstance(i, str) or not i.strip() for i in ids):
        errors.append("widget id must be a non-empty string")
    elif len(ids) != len(set(ids)):
        errors.append("widget ids must be unique")

    for index, widget in enumerate(widgets):
        where = f"widgets[{index}]"
        if not isinstance(widget, dict):
            errors.append(f"{where} must be an object")
            continue

        kind = widget.get("kind")
        if kind not in REQUIRED_BY_KIND:
            errors.append(
                f"{where}: 'kind' must be one of {sorted(REQUIRED_BY_KIND)}, got {kind!r}"
            )
            continue

        endpoint = widget.get("endpoint")
        if not safe_endpoint(endpoint):
            errors.append(f"{where}: 'endpoint' must be a path under /api/, got {endpoint!r}")
        _check_binding(widget, where, errors)

        for key in REQUIRED_BY_KIND[kind]:
            if key in ("series", "columns"):
                continue
            if not isinstance(widget.get(key), str) or not widget[key].strip():
                errors.append(f"{where}: '{kind}' widget needs a non-empty '{key}'")

        if kind in ("line", "bar"):
            _check_series(widget, where, errors)
        if kind == "table":
            _check_columns(widget, where, errors)
            if widget.get("editable") and not any(
                isinstance(c, dict) and c.get("field") == "id"
                for c in widget.get("columns", [])
                if isinstance(c, dict)
            ):
                errors.append(
                    f"{where}: 'editable' tables need an 'id' column so rows can be updated"
                )

    if not any(isinstance(w, dict) and w.get("kind") in _VISUAL_KINDS for w in widgets):
        errors.append("a dashboard needs at least one stat, chart or table widget")

    return errors


def _usable_filter(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    if not isinstance(entry.get("field"), str) or not entry["field"].strip():
        return False
    options = entry.get("options")
    return isinstance(options, list) and bool(options)


def prune_filters(spec: dict[str, Any]) -> int:
    """Drop filters that cannot render, in place. Returns how many went.

    Filters are optional sugar, so a malformed one must not fail a whole
    generation the way a bad layout or widget does — the model cannot know what
    values exist in data it has not generated yet, and routinely emits a filter
    with an empty options list. The dashboard is complete without them.
    """
    filters = spec.get("filters")
    if filters is None:
        return 0
    if not isinstance(filters, list):
        spec.pop("filters", None)
        return 1
    keep = [f for f in filters if _usable_filter(f)]
    dropped = len(filters) - len(keep)
    if keep:
        spec["filters"] = keep
    else:
        spec.pop("filters", None)
    return dropped


def spec_endpoints(spec: dict[str, Any]) -> set[str]:
    """Every /api path the dashboard reads, for the backend contract check."""
    paths = set()
    for binding in _bindings(spec):
        for item in (binding, binding.get("comparison")):
            if isinstance(item, dict) and isinstance(item.get("endpoint"), str):
                if not safe_endpoint(item["endpoint"]):
                    raise ValueError("unsafe endpoint in dashboard spec")
                paths.add(item["endpoint"])
    return paths


def validate_snapshot(snapshot: Any, spec: dict[str, Any]) -> list[str]:
    """Versioned initial/default endpoint map, independent of slide rendering."""
    if not isinstance(snapshot, dict):
        return ["snapshot must be an object"]
    errors = []
    if not _finite_json(snapshot):
        errors.append("snapshot must contain finite JSON")
    if snapshot.get("schemaVersion") != 1:
        errors.append("unsupported snapshot schemaVersion")
    if not re.fullmatch(r"[a-f0-9]{64}", str(snapshot.get("specHash", ""))):
        errors.append("snapshot needs specHash")
    try:
        stamp = datetime.fromisoformat(snapshot.get("capturedAt", ""))
        if stamp.tzinfo is None:
            raise ValueError()
    except (TypeError, ValueError, AttributeError):
        errors.append("snapshot needs timezone-aware capturedAt")
    if not isinstance(snapshot.get("scope"), str) or not snapshot["scope"]:
        errors.append("snapshot needs scope")
    if snapshot.get("provenance") != spec.get("provenance"):
        errors.append("snapshot provenance mismatch")
    endpoints = snapshot.get("endpoints")
    if not isinstance(endpoints, dict):
        errors.append("snapshot endpoints must be an object")
    else:
        if any(not safe_endpoint(p) for p in endpoints):
            errors.append("snapshot unsafe endpoint")
        if spec_endpoints(spec) - endpoints.keys():
            errors.append("snapshot missing required endpoints")
        if any(not isinstance(p, (dict, list)) for p in endpoints.values()):
            errors.append("snapshot payloads must be objects or arrays")
    return errors
