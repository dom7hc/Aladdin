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

export type ScenarioLayout = 'kpi-overview' | 'analytics-breakdown' | 'records-workspace'

/** A business case as an editor writes it (POST/PUT /content/scenarios). */
export interface ScenarioInput {
  title: string
  /** Who it is for: the target users. */
  audience: string
  problem: string
  layout: ScenarioLayout
  highlights: string[]
  /** Seeds the requirement chat when a user picks this case. */
  prompt: string
  enabled: boolean
}

/** A dashboard we build well, offered as a starting point. Stored and editable. */
export interface Scenario extends ScenarioInput {
  id: string
  order: number
  /** Shipped with the platform rather than added by an editor. */
  builtin: boolean
}

/** The home page texts (GET/PUT /content/home). Blank on save means default. */
export interface HomeContent {
  badge: string
  title: string
  titleHighlight: string
  subtitle: string
  placeholder: string
  scenariosLabel: string
  projectsTitle: string
  projectsSubtitle: string
}

export type DatasetColumnType = 'integer' | 'number' | 'date' | 'boolean' | 'text'

export interface DatasetColumn {
  key: string
  label: string
  type: DatasetColumnType
}

/** A user's uploaded CSV/Excel file, as the platform understood it. */
export interface DatasetInfo {
  filename: string
  rowCount: number
  usedRows: number
  truncated: boolean
  notes: string[]
  columns: DatasetColumn[]
  preview: Record<string, unknown>[]
}
