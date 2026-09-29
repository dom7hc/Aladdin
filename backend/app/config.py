"""Environment-driven configuration. No real .env is committed; see .env.example."""

import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "aladdin_poc")
GENERATED_DIR = os.getenv("GENERATED_DIR", os.path.join(_BACKEND_DIR, "generated"))
TEMPLATES_DIR = os.path.join(_BACKEND_DIR, "templates")
MAX_REPAIR_ATTEMPTS = int(os.getenv("MAX_REPAIR_ATTEMPTS", "3"))
MONGO_TIMEOUT_MS = int(os.getenv("MONGO_TIMEOUT_MS", "5000"))


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# Build/test runner battery (Backend Plan §10). Defaults keep the pipeline
# hermetic: no network installs and no tooling requirements beyond Python.
# - pip install mutates the host environment, so it is opt-in.
# - npm requires Node.js on the host, so the frontend build is opt-in; when
#   enabled but npm is missing, the tester records TOOL_UNAVAILABLE.
# - pytest runs by default and is skipped with a recorded reason when pytest
#   is not importable (e.g. the slim deployment image).
TESTER_RUN_PIP_INSTALL = _env_flag("TESTER_RUN_PIP_INSTALL", "false")
TESTER_RUN_PYTEST = _env_flag("TESTER_RUN_PYTEST", "true")
TESTER_RUN_NPM_BUILD = _env_flag("TESTER_RUN_NPM_BUILD", "false")

# LLM-backed agents (replaces the deterministic stubs when enabled). The key
# never lives in Git: set LLM_API_KEY in the local shell or in the VM's
# /opt/aladdin/<env>/runtime.env. With LLM_ENABLED=false the stub agents run
# and no LLM call is ever made.
LLM_ENABLED = _env_flag("LLM_ENABLED", "false")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-flash")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8192"))
# Thinking models spend reasoning tokens out of the max_tokens budget; the
# structured agents do not need deep reasoning. "off" omits the parameter.
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low")
# deepseek-flash reasons without bound by default and can exhaust the whole
# token budget before emitting any content (observed: 32k reasoning tokens,
# zero output). Structured agents default to thinking disabled; set "enabled"
# for open-ended chat workloads.
LLM_THINKING = os.getenv("LLM_THINKING", "disabled")

# Generated-PoC preview deployment. The backend builds and runs the generated
# PoC via the host Docker daemon through the mounted socket.
#
# Previews occupy numbered slots rather than arbitrary ports, because each one
# needs a public address the reverse proxy knows about ahead of time. Slot N
# publishes on loopback PREVIEW_PORT_BASE + N and is served publicly on
# PREVIEW_PUBLIC_PORT_BASE + N. Both bases must stay in step with the site
# blocks in deploy/caddy/Caddyfile.
PREVIEW_PORT_BASE = int(os.getenv("PREVIEW_PORT_BASE", "8200"))
PREVIEW_SLOTS = int(os.getenv("PREVIEW_SLOTS", "6"))
PREVIEW_PUBLIC_PORT_BASE = int(os.getenv("PREVIEW_PUBLIC_PORT_BASE", "9000"))
# Previews are health-checked from a throwaway container on the PoC's own
# compose network, because the stack binds its port to loopback and that is not
# reachable from this container. Any image with busybox wget will do.
PREVIEW_PROBE_IMAGE = os.getenv("PREVIEW_PROBE_IMAGE", "alpine:3")
PREVIEW_HEALTH_TIMEOUT_SECONDS = float(os.getenv("PREVIEW_HEALTH_TIMEOUT_SECONDS", "90"))
# How long a preview stays up before the reaper stops it.
PREVIEW_TTL_SECONDS = float(os.getenv("PREVIEW_TTL_SECONDS", "3600"))
PREVIEW_REAP_INTERVAL_SECONDS = float(os.getenv("PREVIEW_REAP_INTERVAL_SECONDS", "300"))

# The site is open, so anyone can start a generation. Each one is a chain of
# LLM calls plus a test run, so an unbounded number would exhaust the VM and
# the LLM budget. Requests beyond this are refused with a clear message rather
# than queued invisibly.
MAX_CONCURRENT_GENERATIONS = int(os.getenv("MAX_CONCURRENT_GENERATIONS", "3"))

# Public origin of this deployment, used to build preview URLs that work from
# a browser. Without it previews would advertise localhost, which only
# resolves for someone sitting at the Docker host.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost")

# Comma-separated list of allowed browser origins (CORS).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(
        ","
    )
    if origin.strip()
]
