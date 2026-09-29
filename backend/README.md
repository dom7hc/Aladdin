# AI PoC Builder – Backend

FastAPI + MongoDB (Motor) backend that orchestrates the PoC generation pipeline
(Requirement → Architect → Developer → Reviewer → Tester). Implements
`Achitecture/AI_PoC_Builder_Backend_Developer_Plan.md`.

## Setup

```bash
# 1. MongoDB (Docker)
docker compose up -d mongo   # from repo root

# 2. Python 3.12 venv + dependencies
py -V:Astral/CPython3.12.13 -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt

# 3. Configuration (optional; sane defaults apply)
copy .env.example .env
```

## Run

```bash
.venv\Scripts\uvicorn app.main:app --reload
```

## Test

```bash
.venv\Scripts\python.exe -m pytest          # hermetic: mongomock-motor, no MongoDB needed
.venv\Scripts\ruff.exe check app tests
.venv\Scripts\ruff.exe format --check app tests
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/projects` | Create project from an idea |
| GET | `/api/projects` | List recent projects (newest first, limit 20) |
| GET | `/api/projects/{id}` | Project summary |
| POST | `/api/projects/{id}/chat` | Requirement chat (agent updates structured requirements) |
| GET | `/api/projects/{id}/chat` | Full chat history (chronological) |
| GET | `/api/projects/{id}/requirements` | Requirement state + completion |
| POST | `/api/projects/{id}/requirements/finalize` | Render `requirements.md`, set `REQUIREMENT_READY` |
| POST | `/api/projects/{id}/generate` | Start pipeline (background), `202`. Also allowed from `FAILED` to retry |
| GET | `/api/projects/{id}/status` | State machine status + per-step states |
| GET | `/api/projects/{id}/artifacts` | Persisted artifacts (requirements, architecture, review, test) |
| GET | `/api/projects/{id}/source` | ZIP of generated workspace |
| GET | `/health` | Liveness |

JSON uses camelCase (`missingFields`, `currentStep`, …).

CORS is enabled for the origins in `CORS_ORIGINS` (default `http://localhost:5173`,
`http://localhost:5174`) so the SPA can call the API directly in development.

## Data model (MongoDB)

- `projects` — project state with **embedded** `requirements` and `artifacts` (bounded, always read together)
- `messages` — chat history (unbounded, separate collection, indexed by `project_id`)

## Agents

All five agents sit behind interfaces in `app/agents/base.py`. The current
implementations in `app/agents/stubs.py` are deterministic placeholders so the
whole pipeline (state machine, repair loop, workspaces, artifacts, ZIP export)
runs without LLM keys. The AI layer (AI Developer Plan) replaces the stubs
without touching orchestration or APIs.

Repair loop: reviewer/tester failure → developer fix → re-check, max
`MAX_REPAIR_ATTEMPTS` (default 3), attempt count persisted on the project.

### LLM agents (DeepSeek)

`app/agents/llm.py` provides real LLM implementations behind the same five
interfaces — enabled with `LLM_ENABLED=true`. With the flag off (the default)
the deterministic stubs run and **no LLM call is ever made** (tests stay
hermetic).

| Agent | LLM role | Deterministic guardrails |
|---|---|---|
| Requirement | Extracts fields from the chat, writes the reply | Only missing fields are filled; readiness/completion computed from `REQUIREMENT_FIELDS` |
| Architect | Proposes pages/apis/entities/services | Output shape validated (all five arrays required) |
| Developer | Generates PoC code as `{files: [{path, content}]}` | Path safety (no `..`, only `backend/`, `frontend/`, `README.md`), ≤ 16 files, size caps, `backend/main.py` + `frontend/package.json` required |
| Reviewer | Coverage review → `PASS`/`FAIL` + issues | Status/severity clamped to known values |
| Tester | Diagnoses a failed step (summary + suggested fix) | Build/test **execution stays deterministic** (§8); falls back to raw output on LLM errors |

Failure semantics: any LLM/API/validation error raises `LLMError` → the
generation service marks the project `FAILED` (fail fast), except the tester's
diagnosis which degrades to raw evidence.

Configuration (see `.env.example`; `backend/.env` is **not** auto-loaded —
export the variables in the shell, or set them in the VM's
`/opt/aladdin/<env>/runtime.env` which `deploy/compose.yml` passes through):

- `LLM_ENABLED` (default `false`)
- `LLM_BASE_URL` (default `https://api.deepseek.com`), `LLM_MODEL` (default `deepseek-flash`)
- `LLM_API_KEY` — required when enabled; never commit it
- `LLM_TIMEOUT_SECONDS` (default `120`), `LLM_MAX_TOKENS` (default `8192`)

## Build/test runner

Implements Backend Plan §10. The tester validates each generated PoC with an
ordered battery and records one normalized step per command
(`{step, status: PASSED|FAILED|SKIPPED, reason, category, result}`); the run
stops at the first failure and the `TEST_RESULT` artifact content JSON carries
`status`, `category`, `summary` and the full `commands` list.

| Order | Step | Command | Default |
|---|---|---|---|
| 1 | `pipInstall` | `python -m pip install -r requirements.txt` | off |
| 2 | `compile` | `python -m compileall -q .` | on |
| 3 | `pytest` | `python -m pytest -q -p no:cacheprovider .` | on |
| 4 | `npmInstall` | `npm install --no-audit --no-fund` | off |
| 5 | `npmBuild` | `npm run build` | off |

Failure categories: `MISSING_FILES`, `DEPENDENCY_INSTALL`, `COMPILE_ERROR`,
`TEST_FAILURE`, `BUILD_ERROR`, `TOOL_UNAVAILABLE`.

Environment flags (defaults keep the pipeline hermetic — no network, no
Node.js required; see `.env.example`):

- `TESTER_RUN_PIP_INSTALL` (default `false`) — opt-in: it mutates the host
  environment.
- `TESTER_RUN_PYTEST` (default `true`) — runs the generated backend's pytest
  suite (shipped in `templates/default-poc/backend/tests/`). Skipped with a
  recorded reason when pytest is not importable (e.g. the slim deployment
  image).
- `TESTER_RUN_NPM_BUILD` (default `false`) — opt-in frontend build; requires
  Node.js on the host. When enabled but `npm` is missing, the tester fails
  with `TOOL_UNAVAILABLE`.

## Notes

- Generated workspaces live in `backend/generated/` (gitignored); templates in `backend/templates/default-poc/`.
- Deviation from plan §4: no separate `models/` package — embedded documents and Pydantic schemas in `app/schemas/` serve that role.
- Auth is out of scope for the hackathon (plan §13).
