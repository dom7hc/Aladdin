"""Environment-driven configuration. No real .env is committed; see .env.example."""

import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "aladdin_poc")
GENERATED_DIR = os.getenv("GENERATED_DIR", os.path.join(_BACKEND_DIR, "generated"))
TEMPLATES_DIR = os.path.join(_BACKEND_DIR, "templates")
MAX_REPAIR_ATTEMPTS = int(os.getenv("MAX_REPAIR_ATTEMPTS", "3"))
MONGO_TIMEOUT_MS = int(os.getenv("MONGO_TIMEOUT_MS", "5000"))
