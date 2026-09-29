# AI PoC Builder – Hackathon Project Plan

## 1. Product Goal

**AI PoC Builder** helps non-technical users turn a business idea into a structured, buildable web PoC that can be handed off to DevOps for deployment.

### Core Flow

```text
Idea
↓
Chatbot collects requirements
↓
requirements.json + requirements.md
↓
Architect Agent
↓
architecture.md
↓
Developer Agent
↓
Source Code
↓
Reviewer Agent
↓
Tester Agent
↓
Ready-to-deploy PoC
↓
DevOps
```

The goal is not to generate production-ready software.

The hackathon goal is to prove that a vague idea can be transformed into a structured, reviewed, buildable PoC.

---

## 2. User Journey

### Step 1 – Create Project

The user enters an idea.

Example:

> I want an AI application that analyzes invoices and detects suspicious expenses.

The system creates:

```text
Project ID
Project Name
Status = REQUIREMENT_COLLECTION
```

The user is then redirected to the requirement chatbot.

---

## 3. Requirement Collection Chatbot

The chatbot is the main entry point of the product.

The AI should not use a fixed questionnaire.

Instead, it analyzes what information is missing and asks relevant follow-up questions.

Example:

```text
User:
I want an AI tool to analyze invoices.

AI:
Who will mainly use this application?

User:
Finance employees.

AI:
What should users be able to do with an invoice?

User:
Upload PDF, extract information and detect unusual values.

AI:
What information should be extracted?

User:
Supplier, invoice number, date and total amount.
```

### Requirement State

The backend maintains a structured requirement object.

```json
{
  "projectName": "Invoice Analyzer",
  "problem": "Manual invoice review is slow",
  "targetUsers": ["Finance employee"],
  "features": [
    "Upload invoice",
    "Extract invoice fields",
    "Detect anomalies"
  ],
  "inputs": ["PDF invoice"],
  "outputs": [
    "Supplier",
    "Invoice number",
    "Invoice date",
    "Total amount",
    "Anomaly result"
  ],
  "constraints": [],
  "successCriteria": []
}
```

### Important Rule

Raw chat history is not the source of truth.

```text
Chat
↓
Requirement Agent
↓
requirements.json
```

---

## 4. Requirement Completion

The Requirement Agent checks whether enough information has been collected.

```text
Project goal          ✓
Target user           ✓
Main workflow         ✓
Core features         ✓
Inputs                ✓
Expected outputs      ✓
Success criteria      ✕
```

The UI can display:

```text
Requirement completeness: 86%
```

When enough information is available:

```text
AI:
I have enough information to prepare the PoC specification.

[Review Requirements]
[Continue Chat]
```

The user reviews and confirms the requirements.

---

## 5. Requirement Artifacts

The backend generates two files:

- `requirements.json` – machine-readable source of truth
- `requirements.md` – human/agent-friendly version

### Example requirements.md

```markdown
# Invoice Analyzer

## Problem

Finance employees manually inspect invoices, which takes significant time.

## Target Users

- Finance employees

## Core Features

- Upload invoice PDF
- Extract invoice information
- Detect suspicious values
- Display analysis result

## Inputs

- PDF invoice

## Outputs

- Supplier
- Invoice number
- Invoice date
- Total amount
- Anomaly analysis

## Success Criteria

A user can upload an invoice and receive structured information and an anomaly assessment.
```

---

## 6. Standard PoC Architecture

To keep the hackathon scope manageable, all generated PoCs use a fixed technology stack.

```text
Frontend
React

Backend
Python + FastAPI

Database
PostgreSQL

AI
OpenAI / Azure OpenAI

Source Control
Git
```

The agents are not allowed to replace the technology stack.

---

## 7. Multi-Agent Pipeline

The system uses four simple agents.

```text
Architect Agent
↓
Developer Agent
↓
Reviewer Agent
↓
Tester Agent
```

The backend is the orchestrator. Agents do not freely chat with one another.

---

## 8. Architect Agent

### Input

```text
requirements.md
standard-architecture.md
```

### Responsibilities

- Understand requirements
- Define pages
- Define APIs
- Define domain entities
- Define AI integrations
- Define project structure
- Produce an implementation plan

### Output

```text
architecture.md
architecture.json
```

---

## 9. Developer Agent

### Input

```text
requirements.md
architecture.md
standard project template
```

### Responsibilities

The Developer Agent implements the architecture defined by the Architect Agent.

It must not redesign the project.

### Generation Workflow

```text
Create project from template
↓
Generate backend models
↓
Generate API
↓
Generate services
↓
Generate AI integration
↓
Generate frontend API client
↓
Generate frontend components
↓
Generate pages
↓
Generate README
```

---

## 10. Standard Project Template

```text
customer-poc/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.tsx
│   └── package.json
│
├── backend/
│   ├── api/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── ai/
│   └── main.py
│
├── docs/
│
├── README.md
└── .env.example
```

The Developer Agent fills this structure instead of generating a project architecture from scratch.

---

## 11. Reviewer Agent

### Input

```text
requirements.md
architecture.md
source code
```

### Responsibilities

- Requirement coverage
- Architecture compliance
- Missing functionality
- API/frontend mismatch
- Basic security issues
- Code structure
- Hardcoded secrets
- Obvious broken logic

### Output

```json
{
  "status": "FAIL",
  "issues": [
    {
      "severity": "HIGH",
      "file": "backend/api/invoices.py",
      "problem": "Invoice upload endpoint does not validate file type."
    }
  ]
}
```

If review fails:

```text
Reviewer Agent
↓
Developer Agent
↓
Fix
```

---

## 12. Tester Agent

The Tester Agent combines deterministic build/test execution with AI-assisted error analysis.

### Backend Validation

```bash
pip install -r requirements.txt
python -m compileall .
pytest
```

### Frontend Validation

```bash
npm install
npm run build
```

### Functional Checks

```text
Can frontend build?
Can backend start?
Does /health respond?
Are expected API routes available?
```

### Repair Loop

```text
Tester
↓
Developer Agent
↓
Fix
↓
Tester
```

Recommended limit:

```text
maxFixAttempts = 3
```

---

## 13. End-to-End Workflow

```text
                    ┌─────────────────┐
                    │      User       │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │ Chatbot Screen  │
                    └────────┬────────┘
                             ↓
                  ┌─────────────────────┐
                  │ Requirement Agent   │
                  └──────────┬──────────┘
                             ↓
               requirements.json / .md
                             ↓
                    ┌─────────────────┐
                    │ Architect Agent │
                    └────────┬────────┘
                             ↓
                       architecture.md
                             ↓
                    ┌─────────────────┐
                    │ Developer Agent │
                    └────────┬────────┘
                             ↓
                         Source Code
                             ↓
                    ┌─────────────────┐
                    │ Reviewer Agent  │
                    └────────┬────────┘
                             ↓
                           Pass?
                        ↙         ↘
                      No           Yes
                      ↓             ↓
                 Developer       Tester
                      ↑             ↓
                      └──── Fail ────┘
                                    ↓
                                  Pass
                                    ↓
                           Generated PoC
                                    ↓
                                  Git
                                    ↓
                                 DevOps
```

---

## 14. Backend Orchestration

For the hackathon, use a simple state machine.

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

### Project Table

```text
Project

id
name
status
created_at
updated_at
```

### Artifact Table

```text
ProjectArtifact

id
project_id
type
content
version
created_at
```

### Artifact Types

```text
REQUIREMENTS_JSON
REQUIREMENTS_MD
ARCHITECTURE_MD
REVIEW_RESULT
TEST_RESULT
```

---

## 15. API Design

```http
POST /api/projects
POST /api/projects/{id}/chat
GET  /api/projects/{id}/requirements
POST /api/projects/{id}/requirements/finalize
POST /api/projects/{id}/generate
GET  /api/projects/{id}/status
GET  /api/projects/{id}/artifacts
GET  /api/projects/{id}/source
```

---

## 16. Main UI Screens

### Screen 1 – Home

```text
Turn your idea into a PoC

[Describe your idea...]

[Start Building]
```

### Screen 2 – Requirement Chat

Left side:

```text
AI conversation
```

Right side:

```text
Requirement Summary

Project Goal       ✓
Target User        ✓
Features           ✓
Inputs             ✓
Outputs            ✓
Success Criteria   ○

Completion 83%
```

CTA:

```text
[Generate Specification]
```

### Screen 3 – Generation Progress

```text
Creating your PoC

✓ Requirements
✓ Architecture
✓ Backend
✓ Frontend
○ Review
○ Test
```

### Screen 4 – Result

```text
Your PoC is ready
```

Artifacts:

```text
Requirements
requirements.md

Architecture
architecture.md

Source Code
Git / Download

Review
Passed

Tests
Passed
```

Actions:

```text
[View Source]
[Download Project]
[Hand Off to DevOps]
```

---

## 17. Out of Scope

Do not build these during the hackathon:

```text
Kubernetes provisioning
Automatic cloud deployment
Multi-cloud support
Complex authentication
Billing
RAG platform
Vector database
Dynamic technology stacks
Mobile generation
Large template catalog
Fully autonomous agent conversations
```

---

## 18. Demo Scenario

Recommended demo:

**Invoice Analyzer**

Initial prompt:

> I want to build an AI solution that helps finance employees analyze supplier invoices and identify unusual values.

The Requirement Agent asks:

```text
Who uses it?
What file format?
What information should be extracted?
What does "unusual" mean?
What should the user see?
```

Then:

```text
requirements.md generated
↓
Architect Agent creates architecture
↓
Developer Agent generates project
↓
Reviewer Agent checks project
↓
Developer fixes issues
↓
Tester validates build
↓
PoC ready for DevOps
```

---

## 19. Hackathon Implementation Plan

### Phase 1 – Requirement Builder

```text
Project creation
Chat UI
Requirement Agent
requirements.json
requirements.md
```

### Phase 2 – Architect

```text
requirements.md
↓
LLM
↓
architecture.md
```

### Phase 3 – Developer

Use one standard template:

```text
React
+
FastAPI
```

Generate only:

```text
Pages
Models
Services
APIs
```

Aim for roughly 10–20 generated files.

### Phase 4 – Review + Test

Reviewer:

```text
LLM static review
```

Tester:

```text
npm run build
python -m compileall .
pytest
```

On failure:

```text
Developer Agent
↓
Fix
↓
Re-test
```

---

## 20. Agent Definitions

### Requirement Agent

```text
Your job is to understand the user's business idea.

Do not design architecture.

Collect only information required to define a PoC.

Maintain structured requirements.

Ask one or two useful questions at a time.

Stop when minimum PoC requirements are complete.
```

### Architect Agent

```text
Your job is to design a PoC based on requirements.

Use only the approved technology stack.

Do not implement code.

Output architecture and implementation plan.
```

### Developer Agent

```text
Your job is to implement the approved architecture.

Do not redesign the project.

Follow the standard project structure.

Only generate required files.
```

### Reviewer Agent

```text
Your job is to review generated code.

Check requirement coverage, architecture compliance and obvious defects.

Do not change architecture.

Return structured issues.
```

### Tester Agent

```text
Run deterministic tests and builds.

Collect failures.

Use AI only to analyze errors and prepare structured feedback for the Developer Agent.
```

---

## 21. High-Level Architecture

```text
                       React Web App
                             │
                             ↓
                       Backend API
                             │
                ┌────────────┼─────────────┐
                │            │             │
                ▼            ▼             ▼
          PostgreSQL       Git/Files       LLM
                                           │
                    ┌──────────────────────┤
                    │                      │
                    ▼                      ▼
           Requirement Agent         Architect Agent
                                           │
                                           ▼
                                    Developer Agent
                                           │
                                           ▼
                                     Reviewer Agent
                                           │
                                           ▼
                                       Test Runner
                                           │
                                           ▼
                                      Generated PoC
```

---

## 22. Value Proposition

> **AI PoC Builder converts a business idea into a structured, reviewed and buildable software PoC through a guided AI workflow.**

Differentiator:

> Instead of asking AI to blindly generate an application from a prompt, the platform first understands the requirements, creates an architecture, generates code, reviews it and validates the result before handing it to DevOps.

Short version:

```text
Idea
→ Understand
→ Design
→ Build
→ Review
→ Test
→ Deploy
```

---

## 23. MVP Success Criteria

The hackathon is successful if the end-to-end demo shows:

```text
User enters idea                 ✓
AI asks requirement questions   ✓
requirements.md generated       ✓
architecture.md generated       ✓
source project generated        ✓
frontend/backend build          ✓
review/test result visible      ✓
source ready for DevOps         ✓
```
