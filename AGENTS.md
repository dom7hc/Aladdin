# AGENTS.md

## Repository

- Two-stack monorepo: `backend/` (FastAPI + Motor/MongoDB, Python 3.12) and `frontend/` (React 19 + TypeScript + Vite). CI/CD lives in `.github/workflows/` + `deploy/`.
- `Achitecture/` (sic — the typo is baked into paths and docs; do not "fix" it) holds the plan documents the code implements.
- Root `README.md` "Status" is stale (frontend marked as not started; it is built and integrated). `backend/README.md` and `frontend/README.md` are accurate — prefer them.
- `stitch_ai_poc_builder/` is static design mockups (HTML/PNG) — no build, nothing imports it.
- Root `docker-compose.yml` is the local full stack (builds frontend + backend + mongo, app on :8080, `LOCAL_PORT` override; LLM flags come from a gitignored root `.env`). `docker compose up -d mongo` still works alone for API-only dev. The deployment stack is a separate file: `deploy/compose.yml` (no mongo service — Cosmos DB for MongoDB via `runtime.env`), fronted by `deploy/caddy/Caddyfile`.

## Backend (run from `backend/`)

```powershell
# Setup — py launcher / system python may be absent; uv works:
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt

# CI runs these three in this order (see .github/workflows/backend-ci.yml):
.venv\Scripts\ruff.exe check app tests
.venv\Scripts\ruff.exe format --check app tests
.venv\Scripts\python.exe -m pytest

# Run the API (needs `docker compose up -d mongo` from repo root first):
.venv\Scripts\uvicorn app.main:app --reload
```

- Tests are hermetic (mongomock-motor) — no MongoDB needed for pytest.
- `asyncio_mode = "auto"` in `pyproject.toml` — async tests need no `@pytest.mark.asyncio` marker.
- `backend/.env` is never auto-loaded (no dotenv call; uvicorn gets no `--env-file`). Config is plain `os.getenv` in `app/config.py`; local defaults (localhost Mongo) just work. Only `uvicorn[standard]` pulls in python-dotenv as a dependency.
- Ruff line-length is 100 (`pyproject.toml`).

Architecture facts:
- API JSON is camelCase via `CamelModel` (to_camel aliases) in `app/schemas/project.py`; Python stays snake_case. `REQUIREMENT_FIELDS` order there drives the stub agent, completion %, and missing-field report (`constraints` is the only optional field).
- The five pipeline agents (Requirement → Architect → Developer → Reviewer → Tester) sit behind interfaces in `app/agents/base.py`. Two implementations: deterministic `app/agents/stubs.py` (default; whole pipeline runs with no LLM keys, tests stay hermetic) and real LLM `app/agents/llm.py` (DeepSeek via the OpenAI SDK, `LLM_ENABLED=true`; import is lazy). Swap implementations only behind the interfaces — don't alter orchestration/APIs.
- Generation runs in-process via FastAPI `BackgroundTasks` (`app/api/projects.py` → `services/generation_service.py`), not a worker queue. Repair loop bounded by `MAX_REPAIR_ATTEMPTS` (default 3); concurrent generations capped by `MAX_CONCURRENT_GENERATIONS` (default 3, refused not queued).
- Generated PoC source is written to `backend/generated/` (gitignored) from templates in `backend/templates/default-poc/`. It lives only on disk/Docker volume — never mirrored into Mongo.
- Preview feature: the backend builds and runs a generated PoC as its own Docker stack via the mounted `/var/run/docker.sock` (`app/preview/`). The local compose mounts the socket; the deployed VM does not (preview returns `409` there). Slot N publishes loopback `8200+N` and is served publicly on `9000+N` — these must stay in step with the site blocks in `deploy/caddy/Caddyfile`.
- `app/generation/contract.py` enforces that generated PoC frontends call absolute `/api/...` paths — that is why each preview gets its own port/origin instead of a shared path prefix.
- Mongo data model: `projects` embeds requirements + artifacts; `messages` is a separate collection indexed by `project_id`.
- `create_app(db=...)` lets tests inject a DB; `TestClient` must be used inside `with` or the lifespan never sets `app.state.db` (see `tests/conftest.py`).

## Frontend (run from `frontend/`)

```bash
npm ci            # CI uses npm ci, not npm install
npm run lint      # oxlint — NOT eslint
npm run build     # tsc -b && vite build — this IS the typecheck; no separate typecheck script
npm run dev       # :5173, proxies /api to VITE_API_PROXY_TARGET (default :8000)
```

- No frontend test runner exists. `CONTRIBUTING.md` mentions `npm test`, but there is no such script and CI runs only lint + build — never claim frontend tests.
- Mock backend is the default (`VITE_USE_MOCK=true`): all requests flow through `src/api/httpClient.ts`, which branches to `src/mocks/` handlers persisted in localStorage. For the real backend create `frontend/.env.local` with `VITE_USE_MOCK=false` (`.env.local` is gitignored; `frontend/.env` is TRACKED — don't put local overrides there).
- `@` import alias resolves to `src/` (vite + tsconfig).

Contract-change checklist — one API shape change touches all of:
1. backend `app/schemas/project.py` + endpoints,
2. `frontend/src/types/index.ts`,
3. mock handlers `src/mocks/handlers.ts` (must stay behaviorally in sync — the mock is the default demo path),
4. React Query hooks in `src/hooks/` (query keys in `queryKeys.ts`).

## Git / CI / CD

- Pull requests only. Normal work targets `develop` (push auto-deploys the dev stack); releases are `develop` → `main` (production). Squash merge; Conventional-Commit-style PR titles; branch prefixes `feature/`, `fix/`, `infra/`, `docs/`, `chore/`.
- Public entry is Caddy (`deploy/caddy/Caddyfile`): production on default HTTPS, development on :8443. Behind it, `deploy.yml` publishes the frontend loopback-only on :8080 (dev) / :8081 (prod); everything else stays inside the compose network.
- `.github/workflows/` and `deploy/` require CODEOWNER approval (@dom7hc, see `CODEOWNERS`); notify the CI/CD owner before changing Dockerfiles, container ports, health-check paths, required env vars, or compose service names (see `CONTRIBUTING.md`).
- Deploy images are tagged with the commit SHA only (never `latest`); all deployments serialize on one shared-VM concurrency group (`aladdin-vm-deployment`).
- `.gitattributes` forces LF for `*.sh`, `Dockerfile`, `*.yml`, `*.yaml`, `nginx.conf`, `Caddyfile` — a CR breaks shebangs on the deploy VM; keep these files LF.
- PR descriptions must list every validation command run and its result (template enforces this).
