export type ProjectStatusValue =
  | 'CREATED'
  | 'REQUIREMENT_COLLECTION'
  | 'REQUIREMENT_READY'
  | 'ARCHITECTING'
  | 'ARCHITECTURE_READY'
  | 'GENERATING'
  | 'REVIEWING'
  | 'TESTING'
  | 'READY'
  | 'FAILED'

export type StepState = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export interface Project {
  id: string
  name: string
  description: string
  status: ProjectStatusValue
  completion: number
  currentStep?: string | null
  createdAt: string
  updatedAt: string
  preview?: PreviewState
}

export interface RequirementData {
  problem: string
  targetUsers: string[]
  mainWorkflow: string[]
  features: string[]
  inputs: string[]
  outputs: string[]
  constraints: string[]
  successCriteria: string[]
}

export type RequirementField = keyof RequirementData

export interface RequirementResponse {
  message: string
  requirements: RequirementData
  completion: number
  missingFields: string[]
  ready: boolean
}

export interface ChatMessage {
  id: string
  projectId: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
}

export type ArtifactType =
  | 'REQUIREMENTS_JSON'
  | 'REQUIREMENTS_MD'
  | 'ARCHITECTURE_JSON'
  | 'ARCHITECTURE_MD'
  | 'REVIEW_RESULT'
  | 'TEST_RESULT'

export interface Artifact {
  id?: string
  projectId?: string
  type: ArtifactType
  version: number
  content?: string
  createdAt: string
}

export interface FinalizeResult {
  status: ProjectStatusValue
  artifactCount: number
}

export interface ProjectStatus {
  status: ProjectStatusValue
  currentStep: string | null
  completion: number
  steps: Record<string, StepState>
  message?: string
}

export type PreviewStatus = 'none' | 'building' | 'running' | 'failed' | 'unhealthy'

export interface PreviewState {
  status: PreviewStatus
  port: number | null
  url: string | null
  message: string | null
  updatedAt: string | null
}

export interface CreateProjectRequest {
  idea: string
}

export interface ChatRequest {
  message: string
}

/** A dashboard we build well, offered as a starting point. */
export interface Scenario {
  id: string
  title: string
  audience: string
  problem: string
  highlights: string[]
  prompt: string
}
