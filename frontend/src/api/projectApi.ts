import type {
  FinalizeResult,
  PreviewState,
  Project,
  ProjectStatus,
  RequirementData,
  RequirementField,
  RequirementResponse,
} from '@/types'

import { apiFetch } from './httpClient'

export function listProjects(): Promise<Project[]> {
  return apiFetch<Project[]>('/projects')
}

export function getProject(id: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${id}`)
}

export function createProject(idea: string): Promise<Project> {
  return apiFetch<Project>('/projects', { method: 'POST', body: { idea } })
}

export function finalizeRequirements(id: string): Promise<FinalizeResult> {
  return apiFetch<FinalizeResult>(`/projects/${id}/requirements/finalize`, {
    method: 'POST',
  })
}

export function autofillRequirements(id: string): Promise<RequirementResponse> {
  return apiFetch<RequirementResponse>(`/projects/${id}/requirements/autofill`, {
    method: 'POST',
  })
}

export function startGeneration(id: string): Promise<void> {
  return apiFetch<void>(`/projects/${id}/generate`, { method: 'POST' })
}

export function getProjectStatus(id: string): Promise<ProjectStatus> {
  return apiFetch<ProjectStatus>(`/projects/${id}/status`)
}

export function getPreview(id: string): Promise<PreviewState> {
  return apiFetch<PreviewState>(`/projects/${id}/preview`)
}

export function startPreview(id: string): Promise<PreviewState> {
  return apiFetch<PreviewState>(`/projects/${id}/preview`, { method: 'POST' })
}

export function stopPreview(id: string): Promise<PreviewState> {
  return apiFetch<PreviewState>(`/projects/${id}/preview`, { method: 'DELETE' })
}

export interface RequirementsSummary {
  requirements: RequirementData
  completion: number
  missingFields: RequirementField[]
}

export function getRequirements(id: string): Promise<RequirementsSummary> {
  return apiFetch<RequirementsSummary>(`/projects/${id}/requirements`)
}
