import type { HomeContent, Scenario, ScenarioInput } from '@/types'

import { apiFetch } from './httpClient'

const KEY_STORAGE = 'aladdin.adminKey'

/** The shared admin key, remembered in this browser only. */
export function getAdminKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? ''
  } catch {
    return ''
  }
}

export function setAdminKey(key: string): void {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key)
    else localStorage.removeItem(KEY_STORAGE)
  } catch {
    // Storage refused (private mode): the key lasts for this page only.
  }
}

function admin(): Record<string, string> {
  return { 'X-Admin-Key': getAdminKey() }
}

/** Every case, hidden ones included, for the editor. */
export function listAllScenarios(): Promise<Scenario[]> {
  return apiFetch<Scenario[]>('/content/scenarios?all=true')
}

export function createScenario(input: ScenarioInput): Promise<Scenario> {
  return apiFetch<Scenario>('/content/scenarios', { method: 'POST', body: input, headers: admin() })
}

export function updateScenario(id: string, input: ScenarioInput): Promise<Scenario> {
  return apiFetch<Scenario>(`/content/scenarios/${id}`, {
    method: 'PUT',
    body: input,
    headers: admin(),
  })
}

export function deleteScenario(id: string): Promise<void> {
  return apiFetch<void>(`/content/scenarios/${id}`, { method: 'DELETE', headers: admin() })
}

export function reorderScenarios(ids: string[]): Promise<Scenario[]> {
  return apiFetch<Scenario[]>('/content/scenario-order', {
    method: 'PUT',
    body: { ids },
    headers: admin(),
  })
}

export function resetScenarios(): Promise<Scenario[]> {
  return apiFetch<Scenario[]>('/content/scenarios/reset', { method: 'POST', headers: admin() })
}

export function getHomeContent(): Promise<HomeContent> {
  return apiFetch<HomeContent>('/content/home')
}

export function saveHomeContent(content: HomeContent): Promise<HomeContent> {
  return apiFetch<HomeContent>('/content/home', { method: 'PUT', body: content, headers: admin() })
}

export function resetHomeContent(): Promise<HomeContent> {
  return apiFetch<HomeContent>('/content/home', { method: 'DELETE', headers: admin() })
}
