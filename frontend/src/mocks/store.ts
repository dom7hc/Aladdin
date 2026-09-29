import type {
  Artifact,
  ChatMessage,
  Project,
  RequirementData,
} from '@/types'

export interface GenerationState {
  startedAt: number | null
  fail: boolean
}

export interface PreviewBuildState {
  startedAt: number
}

export interface MockState {
  projects: Project[]
  requirements: Record<string, RequirementData>
  messages: Record<string, ChatMessage[]>
  artifacts: Record<string, Artifact[]>
  generation: Record<string, GenerationState>
  previewBuilds: Record<string, PreviewBuildState>
}

const STORAGE_KEY = 'aladdin.mock.state.v1'

const emptyState = (): MockState => ({
  projects: [],
  requirements: {},
  messages: {},
  artifacts: {},
  generation: {},
  previewBuilds: {},
})

let state: MockState | null = null

function load(): MockState {
  if (state) return state
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    state = raw ? { ...emptyState(), ...(JSON.parse(raw) as MockState) } : emptyState()
  } catch {
    state = emptyState()
  }
  return state
}

export function getState(): MockState {
  return load()
}

export function persist(): void {
  if (!state) return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Ignore quota / privacy-mode failures — mock state simply stays in memory.
  }
}

export function resetMockState(): void {
  state = emptyState()
  persist()
}

export function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function findProject(id: string): Project | undefined {
  return load().projects.find((project) => project.id === id)
}

export function touchProject(project: Project): void {
  project.updatedAt = new Date().toISOString()
  persist()
}
