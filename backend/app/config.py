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

# Comma-separated list of allowed browser origins (CORS).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(
        ","
    )
    if origin.strip()
]
