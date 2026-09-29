# Contributing to Aladdin

This repository uses pull requests for every change. Do not push application or deployment changes directly to `develop` or `main`. Until `develop` is created, the one-time repository bootstrap pull request may target `main`.

## Branch Flow

- `develop` is the integration branch and deploys the development stack.
- `main` is the demo/release branch and deploys the production stack.
- Normal work targets `develop`.
- Only release pull requests from `develop` target `main`.

Create branches from the latest `develop`:

```bash
git switch develop
git pull --ff-only origin develop
git switch -c <type>/<short-description>
```

Use one of these branch prefixes:

- `feature/` for product functionality
- `fix/` for bug fixes
- `infra/` for infrastructure and CI/CD
- `docs/` for documentation
- `chore/` for maintenance

Examples:

```text
feature/requirement-chat
fix/project-status-polling
infra/backend-container
docs/api-contract
```

## Pull Request Rules

Keep each pull request focused on one outcome. If the title needs the word "and" to join unrelated changes, split the work.

Use a Conventional Commit style title:

```text
feat: add requirement chat screen
fix: preserve generation status after refresh
infra: add backend container image
docs: document agent response schema
```

Before requesting review:

- Rebase or merge the latest target branch and resolve conflicts.
- Run all checks relevant to the files changed.
- Add or update tests for changed behavior.
- Update API contracts and documentation when interfaces change.
- Confirm no credentials, tokens, connection strings, or `.env` files are committed.
- Confirm generated files, dependency folders, and build output are not committed.
- Describe deployment, database, environment-variable, and rollback impact.
- Keep the pull request in draft while known checks are failing.

## Required Container Contract

CI/CD expects two independently buildable images:

```text
frontend/Dockerfile
backend/Dockerfile
```

Frontend changes should preserve these package scripts:

```text
npm run lint
npm test
npm run build
```

Backend changes should provide:

```text
pytest
GET /health
```

The API and worker should use the same backend image with different runtime commands. Containers must not contain credentials and should run as non-root users where practical.

Tell the CI/CD owner before changing:

- Dockerfile locations
- Build contexts
- Container ports
- Health-check paths
- Required environment variables
- Compose service names
- Persistent volume paths

## Testing Evidence

List the commands you ran and their results in the pull request. Do not write only "tested locally."

Example:

```text
npm run lint       PASS
npm test           PASS (18 tests)
npm run build      PASS
pytest             PASS (24 tests)
docker compose up  PASS
GET /health        200 OK
```

Include screenshots for visible UI changes and request/response examples for API changes.

## Review and Merge

- Obtain at least one teammate approval.
- Resolve every review conversation before merging.
- Required CI checks must pass.
- Use squash merge for normal feature branches.
- Delete the source branch after merge.
- Do not bypass checks to meet a demo deadline without team agreement.

## Release Pull Requests

A release pull request goes from `develop` to `main` and should contain only changes already validated in the development environment.

The release description must include:

- Features and fixes included
- Development environment validation result
- Configuration or secret changes required
- Database or data migration steps
- Production smoke-test steps
- Rollback plan
