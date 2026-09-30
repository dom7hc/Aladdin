# Aladdin — AI PoC Builder (Frontend)

User-facing web app for **AI PoC Builder**. It guides a user through:

```
Idea → Requirement Chat → Requirement Review → Generation Progress → PoC Result
```

The frontend owns no business logic; it consumes the backend APIs and renders project
state. For hackathon/demo purposes it ships with an in-browser **mock backend** so the
whole flow runs without the FastAPI service.

## Stack

- React 19 + TypeScript
- Vite
- React Router v6
- TanStack Query v5 (polling + mutations)
- Tailwind CSS v3 with the "Agrabah Nights" design tokens

## Getting started

```bash
npm install
npm run dev      # http://localhost:5173
```

Other scripts:

```bash
npm run build    # tsc -b && vite build
npm run lint     # oxlint
npm run preview  # preview the production build
```

## Backend mode (mock vs real)

Configured through environment variables (see `.env.example`):

| Variable                 | Default                 | Purpose                                             |
| ------------------------ | ----------------------- | --------------------------------------------------- |
| `VITE_API_BASE_URL`      | `/api`                  | Base path for real backend requests                 |
| `VITE_USE_MOCK`          | `true`                  | `true` = in-browser mock, `false` = real FastAPI    |
| `VITE_API_PROXY_TARGET`  | `http://localhost:8000` | Dev-server proxy target for `/api` when mock is off |

The mock persists projects, chat, requirements, artifacts and generation progress to
`localStorage` under `aladdin.mock.state.v1`. It simulates the pipeline
(Architect → Developer → Reviewer → Tester → READY) over ~13 seconds.

To talk to the real backend:

```bash
# .env.local
VITE_USE_MOCK=false
VITE_API_PROXY_TARGET=http://localhost:8000
```

Then start the full stack:

```bash
# repo root — MongoDB
docker compose up -d mongo

# backend (FastAPI + Motor)
cd backend && .venv/bin/uvicorn app.main:app --reload   # :8000

# frontend
cd frontend && npm run dev                               # :5173
```

The Vite dev server proxies `/api` to the backend, so no CORS setup is needed in dev.
The backend also enables CORS for `http://localhost:5173`/`5174` (see its
`CORS_ORIGINS`) if you point `VITE_API_BASE_URL` at the API directly.

## Routes

| Route                          | Screen              |
| ------------------------------ | ------------------- |
| `/`                            | Home / composer     |
| `/projects/:id/chat`           | Requirement Chat    |
| `/projects/:id/review`         | Requirement Review  |
| `/projects/:id/generate`       | Generation Progress |
| `/projects/:id/result`         | Result              |

## API surface consumed

```
GET    /api/projects
POST   /api/projects
GET    /api/projects/:id
GET    /api/projects/:id/chat
POST   /api/projects/:id/chat
GET    /api/projects/:id/requirements
POST   /api/projects/:id/requirements/autofill
POST   /api/projects/:id/requirements/finalize
POST   /api/projects/:id/generate
GET    /api/projects/:id/status
GET    /api/projects/:id/artifacts
GET    /api/projects/:id/source
```

## Project structure

```
src/
├── api/          # typed API clients + fetch wrapper (mock-aware)
├── components/   # layout, ui primitives, feature components
├── config/       # env access
├── hooks/        # React Query hooks + query keys
├── lib/          # formatting, status + requirement helpers
├── mocks/        # in-browser mock backend (handlers, renderers, store)
├── pages/        # route screens
└── types/        # shared JSON contracts
```
