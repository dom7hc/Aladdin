# Aladdin

**AI PoC Builder** — turns a vague business idea into a structured, reviewed, buildable web PoC through a guided AI workflow:

```text
Idea → Requirements → Architecture → Code → Review → Test → Ready for DevOps
```

Hackathon project. The goal is not production-ready software; it is proving the end-to-end flow works.

## Repository layout

```text
Achitecture/            Plan documents (hackathon, backend, frontend, AI roles)
backend/                FastAPI + MongoDB backend (agent orchestration, APIs)
docker-compose.yml      Local MongoDB
```

## Quickstart (backend)

```powershell
# 1. MongoDB
docker compose up -d mongo

# 2. Python 3.12 venv + dependencies
cd backend
py -V:Astral/CPython3.12.13 -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt

# 3. Run
.venv\Scripts\uvicorn app.main:app --reload
```

Interactive API docs: `http://localhost:8000/docs` — see `backend/README.md` for the full API table and configuration.

## Full stack locally (Docker)

Build and run frontend + backend + MongoDB from source — no Azure needed:

```powershell
docker compose -f docker-compose.local.yml up -d --build
```

Then open **http://localhost:8080** (health: `/health`, API: `/api/projects`).
Override the port with `LOCAL_PORT`. To test with the DeepSeek agents instead
of the deterministic stubs, put this in a root `.env` (gitignored) before
`up`: `LLM_ENABLED=true` and `LLM_API_KEY=<key>`. Teardown:
`docker compose -f docker-compose.local.yml down` (add `-v` to also drop the
local Mongo/generated volumes).

## Tests

Hermetic — no MongoDB required:

```powershell
cd backend
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check app tests
```

## Status

- [x] Plan documents (PostgreSQL → MongoDB updated)
- [x] Backend: APIs, requirement chat, generation pipeline, repair loop, workspaces, artifacts, ZIP export
  - Agents are deterministic stubs behind interfaces; the pipeline runs end-to-end without LLM keys
- [ ] Frontend (React)
- [ ] Real LLM agents (Requirement → Architect → Developer → Reviewer → Tester)

Auth and cloud deployment are out of scope for the hackathon (see `Achitecture/AI_PoC_Builder_Backend_Developer_Plan.md` §13).
