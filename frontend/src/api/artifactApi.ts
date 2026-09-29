import type { Artifact } from '@/types'

import { apiDownload, apiFetch } from './httpClient'

export function getArtifacts(id: string): Promise<Artifact[]> {
  return apiFetch<Artifact[]>(`/projects/${id}/artifacts`)
}

export function fetchSourceBundle(id: string): Promise<{ blob: Blob; filename: string }> {
  return apiDownload(`/projects/${id}/source`)
}
