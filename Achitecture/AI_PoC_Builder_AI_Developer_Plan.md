# AI PoC Builder – AI Developer Plan

## 1. Goal

Build the AI layer that turns user ideas into:

```text
Structured requirements
↓
Architecture
↓
Generated source code
↓
Review feedback
↓
Test diagnosis
```

The AI layer should stay narrow and predictable.

The backend controls the workflow. Agents do not freely chat with each other.

---

## 2. Agent Overview

Use five logical AI roles:

```text
Requirement Agent
Architect Agent
Developer Agent
Reviewer Agent
Tester Agent
```

Generation pipeline:

```text
Requirement Agent
↓
Architect Agent
↓
Developer Agent
↓
Reviewer Agent
↓
Tester Agent
```

---

## 3. Core Principle

Every agent must have:

```text
Clear input
Clear responsibility
Structured output
Strict boundaries
```

Avoid:

```text
One giant autonomous agent
Agents deciding infrastructure
Agents changing the tech stack
Unstructured free-form agent conversations
```

---

# 4. Requirement Agent

## Purpose

Convert a vague business idea and follow-up conversation into structured requirements.

## Input

```text
Current requirements JSON
Recent chat history
Latest user message
```

## Output

Must be structured JSON.

Example:

```json
{
  "assistantMessage": "What should happen after the invoice is uploaded?",
  "requirements": {
    "problem": "Manual invoice review is slow",
    "targetUsers": [
      "Finance employees"
    ],
    "features": [
      "Upload invoice"
    ],
    "inputs": [
      "PDF invoice"
    ],
    "outputs": [],
    "constraints": [],
    "successCriteria": []
  },
  "completion": 65,
  "missingFields": [
    "outputs",
    "successCriteria"
  ],
  "ready": false
}
```

## Required Fields

```text
Problem
Target users
Main workflow
Core features
Inputs
Outputs
Success criteria
```

## Rules

```text
Do not design architecture.
Do not generate code.
Do not discuss deployment.
Ask only 1–2 useful questions at a time.
Do not overwrite confirmed requirements without reason.
Do not invent customer requirements.
```

## Definition of Done

The agent is done when:

```text
Minimum fields are complete
User intent is understandable
Success criteria are clear
ready = true
```

---

# 5. Architect Agent

## Purpose

Turn finalized requirements into a small implementation plan.

## Input

```text
requirements.md
fixed technology stack
standard project template description
```

## Fixed Stack

Example:

```text
Frontend: React
Backend: FastAPI
Database: PostgreSQL
AI: OpenAI / Azure OpenAI
```

The Architect Agent must not replace this stack.

## Output

Produce:

```text
architecture.json
architecture.md
```

Example:

```json
{
  "pages": [
    {
      "name": "UploadInvoicePage",
      "purpose": "Upload invoice files"
    },
    {
      "name": "InvoiceResultPage",
      "purpose": "Display extraction and anomaly results"
    }
  ],
  "apis": [
    {
      "method": "POST",
      "path": "/api/invoices"
    }
  ],
  "entities": [
    {
      "name": "Invoice",
      "fields": [
        "id",
        "filename",
        "supplier",
        "invoiceNumber",
        "totalAmount"
      ]
    }
  ],
  "services": [
    "InvoiceService",
    "InvoiceAIService"
  ],
  "aiCapabilities": [
    "invoice extraction",
    "anomaly detection"
  ]
}
```

## Rules

```text
No source code.
No new frameworks.
No cloud/infrastructure design.
Keep the PoC small.
Prefer simple architecture.
Only design what the requirement needs.
```

---

# 6. Developer Agent

## Purpose

Implement the approved architecture inside the standard template.

## Input

```text
requirements.md
architecture.json
existing template files
review feedback if retry
test feedback if retry
```

## Main Responsibility

The Developer Agent should modify files, not return one giant code block.

Conceptual tools:

```text
list_files
read_file
write_file
replace_file
```

Flow:

```text
Developer Agent
↓
File Tools
↓
Project Workspace
```

## Generation Order

Use a fixed order:

```text
1. Backend models
2. Backend schemas
3. Backend services
4. Backend APIs
5. AI integration
6. Frontend types
7. Frontend API client
8. Frontend components
9. Frontend pages
10. README
```

## Rules

```text
Do not redesign architecture.
Do not change technology stack.
Do not delete unrelated template code.
Do not introduce dependencies unless required.
Prefer existing template patterns.
Keep implementation minimal.
```

## Retry Input

If Reviewer or Tester returns issues, include only:

```text
Relevant issue
Affected files
Required context
```

Avoid resending the entire repository when possible.

---

# 7. Reviewer Agent

## Purpose

Review generated source before running it.

## Input

```text
requirements
architecture
generated source
```

## Review Categories

```text
Requirement coverage
Architecture compliance
Frontend/backend contract
Missing files
Hardcoded secrets
Obvious security issues
Obvious logic errors
Unimplemented features
```

## Output

Structured JSON only.

Example:

```json
{
  "status": "FAIL",
  "issues": [
    {
      "id": "REV-001",
      "severity": "HIGH",
      "file": "backend/api/invoices.py",
      "problem": "PDF validation is missing",
      "recommendation": "Validate file type before processing."
    }
  ]
}
```

## Rules

```text
Do not modify source code.
Do not redesign architecture.
Do not add new features.
Only identify concrete issues.
Avoid subjective style comments for hackathon MVP.
```

---

# 8. Tester Agent

## Purpose

Convert deterministic test/build failures into useful structured feedback.

The Tester Agent should not replace the real test runner.

Correct flow:

```text
Build/Test Runner
↓
Raw output
↓
Tester Agent
↓
Structured diagnosis
```

Example raw error:

```text
Property 'total' does not exist on type Invoice.
```

Output:

```json
{
  "status": "FAILED",
  "category": "TYPE_ERROR",
  "files": [
    "frontend/src/pages/InvoiceResult.tsx"
  ],
  "summary": "Frontend expects `total` but the API model exposes `totalAmount`.",
  "suggestedFix": "Update the frontend type and usage to use totalAmount."
}
```

## Rules

```text
Do not invent test results.
Only analyze provided runner output.
Do not modify source.
Return concise actionable diagnosis.
```

---

# 9. Agent Workflow

```text
requirements.md
      ↓
┌──────────────────┐
│ Architect Agent  │
└────────┬─────────┘
         ↓
 architecture.json
         ↓
┌──────────────────┐
│ Developer Agent  │◄─────────────────────┐
└────────┬─────────┘                      │
         ↓                                │
     Source Code                          │
         ↓                                │
┌──────────────────┐                      │
│ Reviewer Agent   │                      │
└────────┬─────────┘                      │
         ↓                                │
       PASS?                              │
      /     \                             │
    No       Yes                          │
    │          ↓                          │
    └──────────┐                          │
               ↓                          │
       ┌──────────────────┐               │
       │ Tester Agent     │               │
       └────────┬─────────┘               │
                ↓                         │
              PASS?                       │
             /     \                      │
           No       Yes                   │
           │         │                    │
           └─────────┼────────────────────┘
                     ↓
                 PoC Ready
```

---

# 10. Shared Schemas

The AI developer should define strict schemas for:

```text
requirements.json
architecture.json
review-result.json
test-result.json
```

Use Pydantic or JSON Schema so backend can validate agent outputs.

---

## 10.1 requirements.json

```json
{
  "problem": "",
  "targetUsers": [],
  "mainWorkflow": [],
  "features": [],
  "inputs": [],
  "outputs": [],
  "constraints": [],
  "successCriteria": []
}
```

---

## 10.2 architecture.json

```json
{
  "pages": [],
  "apis": [],
  "entities": [],
  "services": [],
  "aiCapabilities": []
}
```

---

## 10.3 review-result.json

```json
{
  "status": "PASS",
  "issues": []
}
```

---

## 10.4 test-result.json

```json
{
  "status": "PASSED",
  "category": null,
  "files": [],
  "summary": ""
}
```

---

# 11. Prompt Design

Each agent should have its own system prompt.

Do not reuse one generic prompt for all agents.

Each prompt should contain:

```text
Role
Allowed inputs
Expected output schema
Responsibilities
Forbidden actions
Tech constraints
Scope constraints
```

Prefer structured-output capable LLM calls.

---

# 12. Context Strategy

Do not send the entire project to every agent.

### Requirement Agent

Send:

```text
Requirement JSON
Recent chat
Latest message
```

### Architect Agent

Send:

```text
requirements.md
fixed stack
template description
```

### Developer Agent

Send:

```text
architecture.json
requirements.md
relevant template files
affected source files
```

### Reviewer Agent

Send:

```text
requirements
architecture
generated files
```

### Tester Agent

Send:

```text
Raw test/build output
Relevant files if needed
```

This reduces token use and hallucination.

---

# 13. AI Developer Milestones

## Milestone 1 – Requirement Agent

Deliver:

```text
Requirement schema
Requirement prompt
Structured-output parser
Completeness calculation
Missing-field detection
```

## Milestone 2 – Architect Agent

Deliver:

```text
Architecture schema
Architect prompt
architecture.json output
architecture.md renderer
```

## Milestone 3 – Developer Agent

Deliver:

```text
File tool abstraction
Template-aware prompt
File generation flow
Retry/fix mode
```

## Milestone 4 – Reviewer Agent

Deliver:

```text
Review schema
Review prompt
PASS/FAIL output
Issue severity
```

## Milestone 5 – Tester Agent

Deliver:

```text
Test diagnosis schema
Build error parser
Tester prompt
Actionable developer feedback
```

---

# 14. AI Evaluation Plan

Create a small set of test ideas.

Examples:

```text
Invoice Analyzer
HR FAQ Assistant
Customer Feedback Dashboard
Document Classifier
```

For each scenario, verify:

```text
Requirement completeness
Architecture correctness
No stack deviation
Generated files match architecture
Reviewer finds obvious issues
Tester diagnosis matches real errors
```

---

# 15. Out of Scope

Do not build now:

```text
Self-planning autonomous agents
Agent-to-agent free conversation
Dynamic model routing
Dynamic framework selection
RAG platform
Long-term agent memory
Autonomous deployment
Complex planning trees
```

---

# 16. AI Definition of Done

```text
Requirement Agent returns valid structured data      ✓
Architect returns valid architecture                 ✓
Developer modifies project files successfully        ✓
Reviewer returns structured PASS/FAIL                ✓
Tester diagnoses real build/test errors              ✓
Repair feedback can be sent back to Developer        ✓
Agent outputs validate against schemas               ✓
Agents respect fixed tech stack                      ✓
