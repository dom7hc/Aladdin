import { env } from '@/config/env'
import { buildSourceBundle, handleMockRequest } from '@/mocks/handlers'
import { findProject } from '@/mocks/store'

import { ApiError } from './errors'

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  headers?: Record<string, string>
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function toApiError(response: Response): Promise<ApiError> {
  let message = `Request failed with status ${response.status}`
  try {
    const data = (await response.json()) as { detail?: string; message?: string }
    message = data.detail || data.message || message
  } catch {
    // response had no JSON body
  }
  return new ApiError(response.status, message)
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'

  if (env.useMock) {
    await delay(env.mockLatencyMs)
    try {
      return handleMockRequest({
        method,
        path,
        body: options.body,
        headers: options.headers,
      }) as T
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(500, (error as Error).message)
    }
  }

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    method,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })

  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** POST one file as multipart/form-data under the field name "file". */
export async function apiUpload<T>(path: string, file: File): Promise<T> {
  if (env.useMock) {
    await delay(env.mockLatencyMs)
    // The mock parses CSV text in the browser; it gets the name and size too
    // so it can refuse the same files the backend refuses.
    const text = file.name.toLowerCase().endsWith('.csv') ? await file.text() : ''
    try {
      return handleMockRequest({
        method: 'POST',
        path,
        body: { filename: file.name, size: file.size, text },
      }) as T
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(500, (error as Error).message)
    }
  }

  const form = new FormData()
  form.append('file', file)
  // No Content-Type header: the browser sets it with the multipart boundary.
  const response = await fetch(`${env.apiBaseUrl}${path}`, { method: 'POST', body: form })
  if (!response.ok) throw await toApiError(response)
  return (await response.json()) as T
}

export async function apiDownload(
  path: string,
): Promise<{ blob: Blob; filename: string }> {
  if (env.useMock) {
    await delay(env.mockLatencyMs)
    const projectId = path.split('/')[2] ?? ''
    const project = findProject(projectId)
    if (!project) throw new ApiError(404, `Project ${projectId} not found`)
    const { filename, content } = buildSourceBundle(project)
    return { blob: new Blob([content], { type: 'text/plain' }), filename }
  }

  const response = await fetch(`${env.apiBaseUrl}${path}`)
  if (!response.ok) throw await toApiError(response)
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match?.[1] ?? 'poc-source.zip'
  return { blob: await response.blob(), filename }
}
