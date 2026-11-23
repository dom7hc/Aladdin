"""Atomic snapshot bundle publication and read-only integrity-checked retrieval."""

import json
import os
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path

from app.design import systems
from app.generation import snapshot
from app.generation.prepare import DASHBOARD_SPEC_PATH
from app.generation.spec import normalize_spec, validate_snapshot, validate_spec
from app.workspace import workspace as ws

SCHEMA_VERSION = 1
RENDERER_VERSION = "dashboard-kit-014-v1"
MAX_INPUT_BYTES = 4_000_000


class InputUnavailable(Exception):
    """Bounded, nonsecret reason suitable for the API."""


def _directory(project_id: str) -> Path:
    # Validate without workspace_dir(): a read must not create directories.
    if len(project_id) != 24 or not set(project_id) <= set("abcdefABCDEF0123456789"):
        raise InputUnavailable("Presentation workspace unavailable.")
    return Path(ws.GENERATED_DIR) / project_id / "presentation"


def invalidate(project_id: str) -> None:
    directory = _directory(project_id)
    if directory.exists():
        shutil.rmtree(directory)


def publish(project_id: str, requirements: dict) -> dict:
    """Return additive project metadata. Capture failure never fails generation."""
    try:
        invalidate(project_id)
        source = ws.source_dir(project_id)
        spec = normalize_spec(json.loads((source / DASHBOARD_SPEC_PATH).read_bytes()))
        if validate_spec(spec):
            raise snapshot.CaptureError("Presentation dashboard spec invalid.")
        captured = snapshot.capture(source, spec)
        if validate_snapshot(captured, spec) or captured["specHash"] != snapshot.content_hash(spec):
            raise snapshot.CaptureError("Presentation snapshot invalid.")
        chosen = spec.get("designSystem") or {}
        system = systems.resolve(chosen.get("palette"), chosen.get("fonts"), chosen.get("style"))
        # Trusted platform CSS, not arbitrary model-authored HTML/scripts/styles.
        kit = Path(ws.TEMPLATES_DIR) / "default-poc/frontend/src/kit"
        css = (
            "\n".join(
                (kit / name).read_text(encoding="utf-8") for name in ("theme.css", "looks.css")
            )
            + "\n"
            + systems.design_css(system)
        )
        bundle = {
            "schemaVersion": SCHEMA_VERSION,
            "rendererVersion": RENDERER_VERSION,
            "spec": spec,
            "snapshot": captured,
            "theme": {
                "css": css,
                "attributes": {
                    "data-theme": spec.get("theme") or "design",
                    "data-mode": "light",
                    "data-look": system.style,
                },
                "designSystem": spec["designSystem"],
            },
            # Plain data only. The browser renderer MUST escape on DOM/HTML output.
            "copy": {
                key: requirements.get(key, "" if key == "problem" else [])
                for key in ("problem", "targetUsers", "successCriteria", "features", "mainWorkflow")
            },
            "hashes": {
                "spec": captured["specHash"],
                "endpoints": snapshot.content_hash(captured["endpoints"]),
                "css": sha256(css.encode("utf-8")).hexdigest(),
                "dataset": sha256((source / "backend/data/dataset.json").read_bytes()).hexdigest(),
                "backend": sha256((source / "backend/main.py").read_bytes()).hexdigest(),
            },
        }
        encoded = snapshot.canonical_bytes(bundle)
        if len(encoded) > MAX_INPUT_BYTES:
            raise snapshot.CaptureError("Presentation input exceeded payload limit.")
        input_hash = snapshot.content_hash(bundle)
        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "rendererVersion": RENDERER_VERSION,
            "inputHash": input_hash,
            "capturedAt": captured["capturedAt"],
            "scope": captured["scope"],
            "hashes": bundle["hashes"],
        }
        parent = _directory(project_id).parent
        with tempfile.TemporaryDirectory(prefix=".presentation-", dir=parent) as temp:
            staging = Path(temp) / "presentation"
            staging.mkdir()
            (staging / "input.json").write_bytes(encoded)
            (staging / "manifest.json").write_bytes(snapshot.canonical_bytes(manifest))
            # Directory rename publishes the pair together, on the same volume.
            os.replace(staging, _directory(project_id))
        return {
            "status": "available",
            "schemaVersion": SCHEMA_VERSION,
            "inputHash": input_hash,
            "capturedAt": captured["capturedAt"],
            "scope": captured["scope"],
        }
    except snapshot.CaptureError as exc:
        return {"status": "unavailable", "reason": str(exc)}
    except Exception:  # noqa: BLE001 -- optional capture must never fail a valid generation
        # Never leak generated exceptions, dataset contents, or host paths.
        return {"status": "unavailable", "reason": "Presentation input could not be prepared."}


def read_input(project_id: str, metadata: dict | None) -> dict:
    if not metadata or metadata.get("status") != "available":
        reason = (metadata or {}).get("reason") or "Presentation unavailable for this project."
        raise InputUnavailable(reason[:200])
    try:
        directory = _directory(project_id)
        with (directory / "input.json").open("rb") as file:
            encoded = file.read(MAX_INPUT_BYTES + 1)
        with (directory / "manifest.json").open("rb") as file:
            manifest_bytes = file.read(16_001)
        if len(encoded) > MAX_INPUT_BYTES or len(manifest_bytes) > 16_000:
            raise ValueError()
        bundle = json.loads(encoded)
        manifest = json.loads(manifest_bytes)
        digest = snapshot.content_hash(bundle)
        if (
            digest != manifest["inputHash"]
            or digest != metadata.get("inputHash")
            or bundle["schemaVersion"] != SCHEMA_VERSION
            or manifest["schemaVersion"] != SCHEMA_VERSION
            or bundle["rendererVersion"] != RENDERER_VERSION
            or validate_spec(bundle["spec"])
            or validate_snapshot(bundle["snapshot"], bundle["spec"])
            or bundle["snapshot"]["specHash"] != snapshot.content_hash(bundle["spec"])
        ):
            raise ValueError()
        return bundle
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise InputUnavailable(
            "Stored presentation input missing or invalid; regenerate."
        ) from None
