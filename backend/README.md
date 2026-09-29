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
| GET | `/api/projects/{id}` | Project summary |
| POST | `/api/projects/{id}/chat` | Requirement chat (agent updates structured requirements) |
| GET | `/api/projects/{id}/requirements` | Requirement state + completion |
| POST | `/api/projects/{id}/requirements/finalize` | Render `requirements.md`, set `REQUIREMENT_READY` |
| POST | `/api/projects/{id}/generate` | Start pipeline (background), `202` |
| GET | `/api/projects/{id}/status` | State machine status + per-step states |
| GET | `/api/projects/{id}/artifacts` | Persisted artifacts (requirements, architecture, review, test) |
| GET | `/api/projects/{id}/source` | ZIP of generated workspace |
| GET | `/health` | Liveness |

JSON uses camelCase (`missingFields`, `currentStep`, …).

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

## Notes

- Generated workspaces live in `backend/generated/` (gitignored); templates in `backend/templates/default-poc/`.
- Deviation from plan §4: no separate `models/` package — embedded documents and Pydantic schemas in `app/schemas/` serve that role.
- Auth is out of scope for the hackathon (plan §13).
