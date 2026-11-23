import type { PresentationInput } from '@/dashboard-kit/presentation'
import type { Artifact } from '@/types'

import { apiDownload, apiFetch } from './httpClient'

export function getArtifacts(id: string): Promise<Artifact[]> {
  return apiFetch<Artifact[]>(`/projects/${id}/artifacts`)
}

export function fetchSourceBundle(id: string): Promise<{ blob: Blob; filename: string }> {
  return apiDownload(`/projects/${id}/source`)
}

/** The stored snapshot the presentation is built from; 409 with a reason when unavailable. */
export function getPresentationInput(id: string): Promise<PresentationInput> {
  return apiFetch<PresentationInput>(`/projects/${id}/presentation-input`)
}
