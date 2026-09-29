# AI PoC Builder – Frontend Developer Plan

## 1. Goal

Build the user-facing web application for AI PoC Builder.

The frontend should guide users through:

```text
Idea
↓
Requirement Chat
↓
Requirement Review
↓
Generation Progress
↓
PoC Result
```

The frontend does not own business logic or agent orchestration. It consumes backend APIs and presents project state clearly.

---

## 2. Recommended Stack

```text
React
TypeScript
React Router
Fetch/Axios
Optional: React Query
```

Keep the frontend simple for the hackathon.

---

## 3. Main Screens

### 3.1 Home

Purpose:

Allow the user to describe an idea and create a project.

UI:

```text
AI PoC Builder

Turn your idea into a PoC

[ Describe your idea... ]

[ Start Building ]
```

API:

```http
POST /api/projects
```

Example request:

```json
{
  "idea": "I want an AI application that analyzes invoices."
}
```

After success:

```text
Redirect to /projects/{id}/chat
```

---

### 3.2 Requirement Chat

Purpose:

Collect requirements through conversation.

Suggested layout:

```text
┌──────────────────────────────┬──────────────────────┐
│ Chat                         │ Requirement Summary  │
│                              │                      │
│ AI: Who will use this app?   │ Goal            ✓   │
│                              │ Target user     ✓   │
│ User: Finance team           │ Features        ✓   │
│                              │ Inputs          ✓   │
│ AI: What should happen...?   │ Outputs         ○   │
│                              │ Success         ○   │
└──────────────────────────────┴──────────────────────┘
```

API:

```http
POST /api/projects/{id}/chat
```

Request:

```json
{
  "message": "Finance employees will use it."
}
```

Response:

```json
{
  "message": "What information should be extracted?",
  "requirements": {
    "targetUsers": [
      "Finance employees"
    ]
  },
  "completion": 60,
  "missingFields": [
    "outputs",
    "successCriteria"
  ],
  "ready": false
}
```

Frontend responsibilities:

- Render chat history
- Submit new messages
- Disable input while sending
- Show requirement completeness
- Show missing fields
- Show structured requirement summary
- Allow continue-chat flow
- Enable finalization only when backend returns `ready = true`

---

### 3.3 Requirement Review

Purpose:

Let the user confirm the requirement before generation.

Example:

```text
Project
Invoice Analyzer

Problem
Manual invoice review is slow.

Target Users
Finance employees

Features
✓ Upload PDF
✓ Extract invoice data
✓ Detect anomalies

[ Back to Chat ]
[ Confirm & Build ]
```

API:

```http
POST /api/projects/{id}/requirements/finalize
```

After success:

```text
Redirect to /projects/{id}/generate
```

---

### 3.4 Generation Progress

Purpose:

Show the user what the system is doing.

Example:

```text
Building your PoC

✓ Requirements
✓ Architect Agent
● Developer Agent
○ Reviewer Agent
○ Tester Agent
```

API:

```http
GET /api/projects/{id}/status
```

Example response:

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

Use polling for hackathon:

```text
Every 2–5 seconds
```

No WebSocket is required for MVP.

When status becomes:

```text
READY
```

redirect to:

```text
/projects/{id}/result
```

---

### 3.5 Result Screen

Purpose:

Show generated artifacts and handoff readiness.

Example:

```text
Your PoC is ready

Requirements
✓ requirements.md

Architecture
✓ architecture.md

Source
✓ Generated project

Review
✓ Passed

Tests
✓ Passed
```

Actions:

```text
[ View Requirements ]
[ View Architecture ]
[ View Source ]
[ Download Project ]
```

APIs:

```http
GET /api/projects/{id}/artifacts
GET /api/projects/{id}/source
```

---

## 4. Suggested Route Structure

```text
/
  Home

/projects/:id/chat
  Requirement Chat

/projects/:id/review
  Requirement Review

/projects/:id/generate
  Generation Progress

/projects/:id/result
  Result
```

---

## 5. Suggested Folder Structure

```text
frontend/
├── src/
│   ├── api/
│   │   ├── projectApi.ts
│   │   ├── chatApi.ts
│   │   └── artifactApi.ts
│   ├── components/
│   │   ├── LoadingState.tsx
│   │   ├── ErrorState.tsx
│   │   └── StatusBadge.tsx
│   ├── features/
│   │   ├── projects/
│   │   ├── requirements/
│   │   ├── generation/
│   │   └── artifacts/
│   ├── pages/
│   │   ├── HomePage.tsx
│   │   ├── ChatPage.tsx
│   │   ├── RequirementReviewPage.tsx
│   │   ├── GenerationPage.tsx
│   │   └── ResultPage.tsx
│   ├── hooks/
│   ├── types/
│   └── App.tsx
```

---

## 6. Shared Type Contracts

Define TypeScript interfaces matching backend JSON.

### ProjectStatus

```ts
export interface ProjectStatus {
  status: string;
  currentStep: string | null;
  completion: number;
  steps: Record<string, string>;
}
```

### RequirementResponse

```ts
export interface RequirementResponse {
  message: string;
  requirements: RequirementData;
  completion: number;
  missingFields: string[];
  ready: boolean;
}
```

### Artifact

```ts
export interface Artifact {
  type: string;
  version: number;
  content?: string;
}
```

---

## 7. Frontend Milestones

### Milestone 1 – Shell

Deliver:

```text
React app
Routing
Layout
API client
Basic error/loading handling
```

### Milestone 2 – Requirement Flow

Deliver:

```text
Home
Create project
Chat UI
Requirement summary
Completion indicator
Requirement review
```

### Milestone 3 – Generation Flow

Deliver:

```text
Generation progress page
Polling
Agent status display
Failure state
```

### Milestone 4 – Result Flow

Deliver:

```text
Artifact list
Artifact viewer
Download source
Ready-for-DevOps status
```

---

## 8. Out of Scope

Do not spend hackathon time on:

```text
Complex authentication
Role management
Realtime sockets
Rich code editor
Git UI
Deployment UI
Mobile app
Advanced dashboarding
```

---

## 9. Frontend Definition of Done

```text
Create project                        ✓
Chat with Requirement Agent          ✓
Show structured requirement summary  ✓
Finalize requirement                 ✓
Show generation progress             ✓
Handle failed state                  ✓
Show generated artifacts             ✓
Download generated project           ✓
```
