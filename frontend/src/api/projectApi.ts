import type {
  Project,
  ProjectStatus,
  RequirementData,
  RequirementField,
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

export function finalizeRequirements(id: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${id}/requirements/finalize`, {
    method: 'POST',
  })
}

export function startGeneration(id: string): Promise<ProjectStatus> {
  return apiFetch<ProjectStatus>(`/projects/${id}/generate`, { method: 'POST' })
}

export function getProjectStatus(id: string): Promise<ProjectStatus> {
  return apiFetch<ProjectStatus>(`/projects/${id}/status`)
}

export interface RequirementsSummary {
  requirements: RequirementData
  completion: number
  missingFields: RequirementField[]
}

export function getRequirements(id: string): Promise<RequirementsSummary> {
  return apiFetch<RequirementsSummary>(`/projects/${id}/requirements`)
}
