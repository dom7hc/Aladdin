"""Deterministic Markdown renderers.

JSON -> Markdown is done in code, never via the LLM (Backend Plan §6).
"""

import html
from typing import Any

from app.schemas.project import REQUIREMENT_FIELDS

_TITLES = {
    "problem": "Problem",
    "targetUsers": "Target Users",
    "mainWorkflow": "Main Workflow",
    "features": "Core Features",
    "inputs": "Inputs",
    "outputs": "Outputs",
    "constraints": "Constraints",
    "successCriteria": "Success Criteria",
}


def render_requirements_md(name: str, content: dict[str, Any]) -> str:
    lines = [f"# {name}", ""]
    for field in REQUIREMENT_FIELDS:
        value = content.get(field)
        lines += [f"## {_TITLES[field]}"]
        if isinstance(value, list):
            lines += [f"- {html.escape(str(item))}" for item in value] or ["- (not specified)"]
        else:
            lines += [html.escape(str(value or "(not specified)"))]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _widget_line(widget: dict[str, Any]) -> str:
    """One readable line per widget, whatever its kind."""
    kind = widget.get("kind", "?")
    name = widget.get("title") or widget.get("label") or "(untitled)"
    endpoint = widget.get("endpoint", "")
    detail = ""
    series = widget.get("series")
    columns = widget.get("columns")
    if isinstance(series, list) and series:
        detail = " — " + ", ".join(str(s.get("label", "")) for s in series if isinstance(s, dict))
    elif isinstance(columns, list) and columns:
        detail = " — " + ", ".join(str(c.get("label", "")) for c in columns if isinstance(c, dict))
    elif widget.get("field"):
        detail = f" — {widget['field']}"
    if widget.get("editable"):
        detail += " — editable"
    return f"- **{name}** (`{kind}`, `{endpoint}`){detail}"


def render_architecture_md(architecture: dict[str, Any]) -> str:
    """Render the dashboard spec as readable Markdown.

    Mirrors app/generation/spec.py's shape: the architecture *is* the dashboard
    spec now, so this describes widgets rather than pages and services.
    """
    lines = [f"# {architecture.get('title') or 'Dashboard'}", ""]
    if architecture.get("subtitle"):
        lines += [str(architecture["subtitle"]), ""]
    lines += [f"**Layout:** `{architecture.get('layout', '(unset)')}`"]
    if architecture.get("theme"):
        lines.append(f"**Theme:** `{architecture['theme']}`")
    lines.append("")

    widgets = architecture.get("widgets")
    lines.append("## Widgets")
    if isinstance(widgets, list) and widgets:
        lines += [_widget_line(w) for w in widgets if isinstance(w, dict)]
    else:
        lines.append("- (none)")
    lines.append("")

    endpoints = sorted(
        {
            str(w["endpoint"])
            for w in (widgets if isinstance(widgets, list) else [])
            if isinstance(w, dict) and w.get("endpoint")
        }
    )
    lines.append("## Endpoints the backend must serve")
    lines += [f"- `{endpoint}`" for endpoint in endpoints] or ["- (none)"]
    editable = [
        w
        for w in (widgets if isinstance(widgets, list) else [])
        if isinstance(w, dict) and w.get("editable") and isinstance(w.get("endpoint"), str)
    ]
    if editable:
        lines.append("")
        lines.append("## CRUD routes for editable tables")
        for widget in editable:
            base = str(widget["endpoint"]).rstrip("/")
            lines += [
                f"- `POST {base}` — create a row",
                f"- `PUT {base}/{{id}}` — update a row",
                f"- `DELETE {base}/{{id}}` — delete a row",
            ]
    lines.append("")

    filters = architecture.get("filters")
    if isinstance(filters, list) and filters:
        lines.append("## Filters")
        for item in filters:
            if isinstance(item, dict):
                options = item.get("options")
                joined = ", ".join(str(o) for o in options) if isinstance(options, list) else ""
                lines.append(f"- **{item.get('label') or item.get('field')}**: {joined}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
