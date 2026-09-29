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


def render_architecture_md(architecture: dict[str, Any]) -> str:
    lines = ["# Architecture", ""]
    sections = [
        ("Pages", "pages", "name", "purpose"),
        ("APIs", "apis", "method", "path"),
        ("Entities", "entities", "name", "fields"),
        ("Services", "services", None, None),
        ("AI Capabilities", "aiCapabilities", None, None),
    ]
    for title, key, first, second in sections:
        values = architecture.get(key, [])
        lines += [f"## {title}"]
        for item in values:
            if isinstance(item, dict):
                second_value = item.get(second, "")
                if isinstance(second_value, list):
                    second_value = ", ".join(str(v) for v in second_value)
                lines.append(f"- **{item.get(first, '')}** – {second_value}")
            else:
                lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
