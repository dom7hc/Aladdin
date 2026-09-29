import { ApiError } from '@/api/errors'
import {
  EMPTY_REQUIREMENTS,
  missingRequirementFields,
  requirementCompletion,
} from '@/lib/requirements'
import type {
  Artifact,
  ArtifactType,
  ChatMessage,
  Project,
  ProjectStatus,
  ProjectStatusValue,
  RequirementData,
  RequirementResponse,
  StepState,
} from '@/types'

import {
  GREETING,
  advanceRequirements,
  deriveProjectName,
} from './requirementFlow'
import {
  buildArchitecture,
  buildReviewResult,
  buildTestResult,
  renderArchitectureMarkdown,
  renderRequirementsMarkdown,
} from './renderers'
import {
  findProject,
  getState,
  newId,
  persist,
  touchProject,
  type MockState,
} from './store'

const STEP_KEYS = ['requirements', 'architect', 'developer', 'reviewer', 'tester']

interface Phase {
  at: number
  status: ProjectStatusValue
  currentStep: string | null
  completion: number
  completed: string[]
  running: string | null
}

const PHASES: Phase[] = [
  {
    at: 0,
    status: 'ARCHITECTING',
    currentStep: 'ARCHITECT',
    completion: 12,
    completed: ['requirements'],
    running: 'architect',
  },
  {
    at: 2,
    status: 'GENERATING',
    currentStep: 'DEVELOPER',
    completion: 40,
    completed: ['requirements', 'architect'],
    running: 'developer',
  },
  {
    at: 6,
    status: 'REVIEWING',
    currentStep: 'REVIEWER',
    completion: 68,
    completed: ['requirements', 'architect', 'developer'],
    running: 'reviewer',
  },
  {
    at: 9,
    status: 'TESTING',
    currentStep: 'TESTER',
    completion: 88,
    completed: ['requirements', 'architect', 'developer', 'reviewer'],
    running: 'tester',
  },
  {
    at: 13,
    status: 'READY',
    currentStep: null,
    completion: 100,
    completed: ['requirements', 'architect', 'developer', 'reviewer', 'tester'],
    running: null,
  },
]

function buildSteps(completed: string[], running: string | null): Record<string, StepState> {
  return STEP_KEYS.reduce<Record<string, StepState>>((acc, key) => {
    if (completed.includes(key)) acc[key] = 'COMPLETED'
    else if (key === running) acc[key] = 'RUNNING'
    else acc[key] = 'PENDING'
    return acc
  }, {})
}

function getRequirements(state: MockState, projectId: string): RequirementData {
  return state.requirements[projectId] ?? { ...EMPTY_REQUIREMENTS }
}

function addArtifact(
  state: MockState,
  projectId: string,
  type: ArtifactType,
  content: string,
  version = 1,
): Artifact {
  const artifact: Artifact = {
    id: newId(),
    projectId,
    type,
    version,
    content,
    createdAt: new Date().toISOString(),
  }
  state.artifacts[projectId] = [...(state.artifacts[projectId] ?? []), artifact]
  return artifact
}

function ensureRequirementsArtifacts(state: MockState, project: Project): void {
  const existing = state.artifacts[project.id] ?? []
  if (existing.some((artifact) => artifact.type === 'REQUIREMENTS_MD')) return
  const requirements = getRequirements(state, project.id)
  addArtifact(
    state,
    project.id,
    'REQUIREMENTS_JSON',
    JSON.stringify(requirements, null, 2),
  )
  addArtifact(
    state,
    project.id,
    'REQUIREMENTS_MD',
    renderRequirementsMarkdown(project.name, requirements),
  )
}

function ensureGenerationArtifacts(state: MockState, project: Project): void {
  const existing = state.artifacts[project.id] ?? []
  if (existing.some((artifact) => artifact.type === 'ARCHITECTURE_MD')) return
  const requirements = getRequirements(state, project.id)
  const architecture = buildArchitecture(requirements)
  addArtifact(
    state,
    project.id,
    'ARCHITECTURE_JSON',
    JSON.stringify(architecture, null, 2),
  )
  addArtifact(
    state,
    project.id,
    'ARCHITECTURE_MD',
    renderArchitectureMarkdown(project.name, architecture),
  )
  addArtifact(
    state,
    project.id,
    'REVIEW_RESULT',
    JSON.stringify(buildReviewResult(project.name), null, 2),
  )
  addArtifact(
    state,
    project.id,
    'TEST_RESULT',
    JSON.stringify(buildTestResult(), null, 2),
  )
}

function computeStatus(state: MockState, project: Project): ProjectStatus {
  const generation = state.generation[project.id]
  const requirements = getRequirements(state, project.id)
  const reqCompletion = requirementCompletion(requirements)
  const reqReady = missingRequirementFields(requirements).length === 0

  if (project.status === 'FAILED' || generation?.fail) {
    const failed = generation?.fail && generation.startedAt !== null
    if (failed && project.status !== 'READY') {
      const elapsed = (Date.now() - (generation.startedAt ?? Date.now())) / 1000
      if (elapsed >= 6) {
        project.status = 'FAILED'
        project.currentStep = 'DEVELOPER'
        touchProject(project)
        return {
          status: 'FAILED',
          currentStep: 'DEVELOPER',
          completion: project.completion,
          steps: buildSteps(['requirements', 'architect'], 'developer'),
          message:
            'The Developer Agent could not compile the generated source. The repair loop stopped after the maximum attempts.',
        }
      }
    }
  }

  if (!generation || generation.startedAt === null) {
    const status: ProjectStatusValue = reqReady
      ? 'REQUIREMENT_READY'
      : 'REQUIREMENT_COLLECTION'
    if (project.status !== status) {
      project.status = status
      project.completion = reqReady ? 100 : reqCompletion
      touchProject(project)
    }
    return {
      status,
      currentStep: reqReady ? null : 'REQUIREMENTS',
      completion: reqReady ? 100 : reqCompletion,
      steps: buildSteps(reqReady ? ['requirements'] : [], reqReady ? null : 'requirements'),
    }
  }

  const elapsed = (Date.now() - generation.startedAt) / 1000
  const phase = [...PHASES].reverse().find((item) => elapsed >= item.at) ?? PHASES[0]

  project.status = phase.status
  project.completion = phase.completion
  project.currentStep = phase.currentStep
  touchProject(project)

  if (phase.status === 'READY') {
    ensureGenerationArtifacts(state, project)
    persist()
  }

  return {
    status: phase.status,
    currentStep: phase.currentStep,
    completion: phase.completion,
    steps: buildSteps(phase.completed, phase.running),
  }
}

function parseSegments(path: string): string[] {
  return path.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean)
}

interface MockRequest {
  method: string
  path: string
  body?: unknown
}

export function handleMockRequest({ method, path, body }: MockRequest): unknown {
  const state = getState()
  const segments = parseSegments(path)
  const [resource, projectId, sub, action] = segments

  if (resource !== 'projects') {
    throw new ApiError(404, `Unknown mock endpoint: ${method} ${path}`)
  }

  // /projects collection
  if (!projectId) {
    if (method === 'POST') {
      const idea = String((body as { idea?: string } | undefined)?.idea ?? '').trim()
      if (!idea) throw new ApiError(400, 'idea is required')
      return createProject(idea)
    }
    if (method !== 'GET') throw new ApiError(405, 'Method not allowed')
    return [...state.projects].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  }

  const project = findProject(projectId)
  if (!project) throw new ApiError(404, `Project ${projectId} not found`)

  // POST /projects
  if (segments.length === 1) {
    if (method !== 'GET') throw new ApiError(405, 'Method not allowed')
    return project
  }

  // /projects/:id/chat
  if (sub === 'chat') {
    if (method === 'GET') return state.messages[projectId] ?? []

    if (method === 'POST') {
      const message = String((body as { message?: string } | undefined)?.message ?? '').trim()
      if (!message) throw new ApiError(400, 'message is required')

      const current = getRequirements(state, projectId)
      const existingMessages = state.messages[projectId] ?? []
      const userTurnIndex = existingMessages.filter((item) => item.role === 'user').length

      const userMessage: ChatMessage = {
        id: newId(),
        projectId,
        role: 'user',
        content: message,
        createdAt: new Date().toISOString(),
      }
      const result = advanceRequirements(current, message, userTurnIndex)
      const assistantMessage: ChatMessage = {
        id: newId(),
        projectId,
        role: 'assistant',
        content: result.message,
        createdAt: new Date().toISOString(),
      }

      state.messages[projectId] = [...existingMessages, userMessage, assistantMessage]
      state.requirements[projectId] = result.requirements

      const completion = requirementCompletion(result.requirements)
      const missingFields = missingRequirementFields(result.requirements)
      project.completion = missingFields.length === 0 ? 100 : completion
      project.status =
        missingFields.length === 0 ? 'REQUIREMENT_READY' : 'REQUIREMENT_COLLECTION'
      touchProject(project)

      const response: RequirementResponse = {
        message: result.message,
        requirements: result.requirements,
        completion,
        missingFields,
        ready: missingFields.length === 0,
      }
      return response
    }

    throw new ApiError(405, 'Method not allowed')
  }

  // /projects/:id/requirements
  if (sub === 'requirements') {
    if (action === 'finalize' && method === 'POST') {
      const requirements = getRequirements(state, projectId)
      if (missingRequirementFields(requirements).length > 0) {
        throw new ApiError(409, 'Requirements are not complete yet')
      }
      project.status = 'REQUIREMENT_READY'
      project.completion = 100
      project.currentStep = null
      ensureRequirementsArtifacts(state, project)
      touchProject(project)
      const artifactCount = (state.artifacts[projectId] ?? []).filter((artifact) =>
        artifact.type.startsWith('REQUIREMENTS_'),
      ).length
      return { status: 'REQUIREMENT_READY', artifactCount }
    }

    if (method === 'GET') {
      return {
        requirements: getRequirements(state, projectId),
        completion: requirementCompletion(getRequirements(state, projectId)),
        missingFields: missingRequirementFields(getRequirements(state, projectId)),
      }
    }

    throw new ApiError(405, 'Method not allowed')
  }

  // /projects/:id/generate — mirrors backend 202 {projectId, status}
  if (sub === 'generate' && method === 'POST') {
    if (!['REQUIREMENT_READY', 'FAILED'].includes(project.status)) {
      throw new ApiError(
        409,
        `Project is ${project.status}; generate requires REQUIREMENT_READY or FAILED.`,
      )
    }
    if (project.status === 'FAILED') {
      project.status = 'REQUIREMENT_READY'
      project.completion = 100
      project.currentStep = null
    }
    const generation = state.generation[projectId] ?? { startedAt: null, fail: false }
    generation.startedAt = Date.now()
    state.generation[projectId] = generation
    project.status = 'ARCHITECTING'
    touchProject(project)
    return { projectId, status: 'STARTED' }
  }

  // /projects/:id/status
  if (sub === 'status' && method === 'GET') {
    return computeStatus(state, project)
  }

  // /projects/:id/artifacts
  if (sub === 'artifacts' && method === 'GET') {
    if (project.status === 'READY') {
      ensureGenerationArtifacts(state, project)
      persist()
    }
    return state.artifacts[projectId] ?? []
  }

  // /projects/:id/source
  if (sub === 'source' && method === 'GET') {
    return buildSourceBundle(project)
  }

  throw new ApiError(404, `Unknown mock endpoint: ${method} ${path}`)
}

export function createProject(idea: string): Project {
  const state = getState()
  const name = deriveProjectName(idea)
  const now = new Date().toISOString()

  const project: Project = {
    id: newId(),
    name,
    description: idea.trim(),
    status: 'REQUIREMENT_COLLECTION',
    currentStep: 'REQUIREMENTS',
    completion: 0,
    createdAt: now,
    updatedAt: now,
  }

  state.projects.push(project)
  state.requirements[project.id] = { ...EMPTY_REQUIREMENTS }
  state.messages[project.id] = [
    {
      id: newId(),
      projectId: project.id,
      role: 'assistant',
      content: GREETING,
      createdAt: now,
    },
  ]
  state.artifacts[project.id] = []
  state.generation[project.id] = {
    startedAt: null,
    fail: /\bfail\b/i.test(idea),
  }
  persist()

  return project
}

export function markProjectFailed(projectId: string): void {
  const state = getState()
  const project = findProject(projectId)
  if (!project) return
  state.generation[projectId] = { startedAt: Date.now(), fail: true }
  persist()
}

export function buildSourceBundle(project: Project): {
  filename: string
  content: string
} {
  const state = getState()
  const requirements = getRequirements(state, project.id)
  const architecture = buildArchitecture(requirements)
  const slug = project.name.toLowerCase().replace(/\s+/g, '-')

  const content = [
    `# ${project.name} — Generated PoC Bundle`,
    '',
    'Generated by Aladdin AI PoC Builder.',
    '',
    '## File tree',
    '```',
    `${slug}/`,
    '├── requirements.md',
    '├── architecture.md',
    '├── source/',
    '│   ├── frontend/',
    '│   └── backend/',
    '```',
    '',
    '---',
    '',
    renderRequirementsMarkdown(project.name, requirements),
    '',
    '---',
    '',
    renderArchitectureMarkdown(project.name, architecture),
  ].join('\n')

  return { filename: `${slug}-source.txt`, content }
}
