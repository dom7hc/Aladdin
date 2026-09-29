# AI PoC Builder – Backend Developer Plan

## 1. Goal

Build the backend service that owns:

```text
Project state
Chat history
Requirement storage
Artifacts
Agent orchestration
Project workspaces
Build/test execution
Source export
```

The backend is the central orchestrator.

---

## 2. Recommended Stack

```text
Python
FastAPI
PostgreSQL
SQLAlchemy
Pydantic
```

Keep the backend as one service for the hackathon.

Do not split it into microservices.

---

## 3. High-Level Architecture

```text
React Frontend
      ↓
FastAPI
      ↓
Application Services
      ↓
Agent Orchestrator
      ↓
LLM / Agents
      ↓
Project Workspace
      ↓
PostgreSQL
```

---

## 4. Suggested Folder Structure

```text
backend/
├── app/
│   ├── api/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   ├── agents/
│   ├── generation/
│   ├── workspace/
│   └── main.py
├── templates/
├── generated/
└── tests/
```

---

## 5. Core Data Model

### Project

```text
id
name
description
status
current_step
completion
created_at
updated_at
```

Possible status values:

```text
CREATED
REQUIREMENT_COLLECTION
REQUIREMENT_READY
ARCHITECTING
ARCHITECTURE_READY
GENERATING
REVIEWING
TESTING
READY
FAILED
```

---

### ProjectRequirement

```text
project_id
content_json
completion
updated_at
```

Use JSONB for hackathon.

Example:

```json
{
  "problem": "",
  "targetUsers": [],
  "features": [],
  "inputs": [],
  "outputs": [],
  "constraints": [],
  "successCriteria": []
}
```

---

### ChatMessage

```text
id
project_id
role
content
created_at
```

---

### ProjectArtifact

```text
id
project_id
type
content
version
created_at
```

Artifact types:

```text
REQUIREMENTS_JSON
REQUIREMENTS_MD
ARCHITECTURE_JSON
ARCHITECTURE_MD
REVIEW_RESULT
TEST_RESULT
```

---

## 6. Core APIs

### Create Project

```http
POST /api/projects
```

Example:

```json
{
  "idea": "I want an AI application that analyzes invoices."
}
```

---

### Get Project

```http
GET /api/projects/{id}
```

---

### Requirement Chat

```http
POST /api/projects/{id}/chat
```

Flow:

```text
Receive user message
↓
Load requirement state
↓
Load recent chat
↓
Call Requirement Agent
↓
Update requirements
↓
Store conversation
↓
Return agent response
```

---

### Get Requirements

```http
GET /api/projects/{id}/requirements
```

---

### Finalize Requirements

```http
POST /api/projects/{id}/requirements/finalize
```

Flow:

```text
requirements.json
↓
Markdown Renderer
↓
requirements.md
↓
Save artifact
↓
Status = REQUIREMENT_READY
```

Use deterministic Markdown rendering.

Do not call the LLM just to convert JSON to Markdown.

---

### Start Generation

```http
POST /api/projects/{id}/generate
```

Start:

```text
Architect
↓
Developer
↓
Reviewer
↓
Tester
```

---

### Project Status

```http
GET /api/projects/{id}/status
```

Example:

```json
{
  "status": "GENERATING",
  "currentStep": "DEVELOPER",
  "completion": 55,
  "steps": {
    "requirements": "COMPLETED",
    "architect": "COMPLETED",
    "developer": "RUNNING",
    "reviewer": "PENDING",
    "tester": "PENDING"
  }
}
```

---

### Artifacts

```http
GET /api/projects/{id}/artifacts
```

---

### Download Source

```http
GET /api/projects/{id}/source
```

Create ZIP from the project workspace.

---

## 7. Project Workspace

Each project gets an isolated workspace.

```text
generated/
└── {project-id}/
    ├── requirements.md
    ├── architecture.md
    └── source/
        ├── frontend/
        └── backend/
```

Standard project template:

```text
templates/
└── default-poc/
    ├── frontend/
    └── backend/
```

Flow:

```text
default-poc
↓
Copy template
↓
generated/{project-id}/source
↓
Developer Agent modifies files
```

---

## 8. Orchestration Service

Create a single generation service.

Conceptually:

```python
class PocGenerationService:
    async def generate(self, project_id):
        architecture = await architect.run(...)
        source = await developer.run(...)
        review = await reviewer.run(...)
        test = await tester.run(...)
```

Main flow:

```text
REQUIREMENT_READY
↓
ARCHITECTING
↓
ARCHITECTURE_READY
↓
GENERATING
↓
REVIEWING
↓
TESTING
↓
READY
```

On failure:

```text
FAILED
```

---

## 9. Repair Loop

Reviewer failure:

```text
Reviewer
↓
Developer fix
↓
Reviewer
```

Tester failure:

```text
Tester
↓
Developer fix
↓
Tester
```

Recommended:

```text
MAX_REPAIR_ATTEMPTS = 3
```

Persist attempt count.

Stop after max retries.

---

## 10. Build/Test Runner

Frontend commands:

```bash
npm install
npm run build
```

Backend commands:

```bash
pip install -r requirements.txt
python -m compileall .
pytest
```

Capture:

```text
stdout
stderr
exit code
duration
```

Normalize into structured result:

```json
{
  "status": "FAILED",
  "command": "npm run build",
  "exitCode": 1,
  "errors": []
}
```

For the hackathon, execution may happen on the backend host.

For production, generated code should run inside isolated containers.

---

## 11. Required Internal Interfaces

Keep AI integration behind interfaces.

Example:

```python
class RequirementAgent:
    async def run(...): ...

class ArchitectAgent:
    async def run(...): ...

class DeveloperAgent:
    async def run(...): ...

class ReviewerAgent:
    async def run(...): ...

class TesterAgent:
    async def run(...): ...
```

Also create workspace services:

```text
read_file
write_file
list_files
copy_template
zip_project
```

---

## 12. Backend Milestones

### Milestone 1 – Foundation

Deliver:

```text
FastAPI app
Database
Project model
Project status
Basic APIs
```

### Milestone 2 – Requirement Flow

Deliver:

```text
Chat storage
Requirement JSONB
Requirement Agent integration
Finalize endpoint
requirements.md renderer
```

### Milestone 3 – Generation Flow

Deliver:

```text
Project workspace
Template copying
Generation orchestrator
Agent status updates
Artifact storage
```

### Milestone 4 – Quality Flow

Deliver:

```text
Reviewer loop
Build/test runner
Tester loop
Retry limit
Failure handling
```

### Milestone 5 – Handoff

Deliver:

```text
Artifacts API
ZIP source export
READY state
```

---

## 13. Out of Scope

Do not build now:

```text
Microservices
Kafka
RabbitMQ
Temporal
Kubernetes orchestration
Automatic deployment
Multi-cloud support
Enterprise auth
GitHub/GitLab integration
```

---

## 14. Backend Definition of Done

```text
Project creation              ✓
Requirement state             ✓
Chat persistence              ✓
requirements.md generation    ✓
Agent orchestration           ✓
Project workspace             ✓
Artifact persistence          ✓
Review loop                   ✓
Build/test execution          ✓
Repair loop                   ✓
ZIP export                    ✓
Status API                    ✓
```
