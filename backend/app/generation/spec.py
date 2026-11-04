"""Validation for the dashboard spec the generator produces.

The spec is the only frontend file the model writes: everything visual is
platform-owned in the template's ``frontend/src/kit/``. Keep this in step with
``kit/types.ts``, which describes the same shape for the renderer.

Validating before anything is written means a malformed spec fails the run with
an actionable message instead of producing a dashboard that renders empty.
"""

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
    "table": ("title", "columns"),
}

# A dashboard with no way to show a number is not a dashboard.
_VISUAL_KINDS = {"stat", "line", "bar", "table"}

MAX_WIDGETS = 10
# The series palette has eight slots and is never cycled.
MAX_SERIES = 8


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
            for key in ("palette", "fonts"):
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
        if not isinstance(endpoint, str) or not endpoint.startswith("/api/"):
            errors.append(f"{where}: 'endpoint' must be a path under /api/, got {endpoint!r}")

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
    widgets = spec.get("widgets")
    if not isinstance(widgets, list):
        return set()
    return {
        w["endpoint"] for w in widgets if isinstance(w, dict) and isinstance(w.get("endpoint"), str)
    }
