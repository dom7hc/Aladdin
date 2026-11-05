// Mock of /api/content (backend app/api/content.py): business cases and home
// page texts, persisted in localStorage with the rest of the mock state.
//
// One deliberate difference: the browser holds no secret to compare against,
// so any non-empty admin key is accepted. An empty one is refused like the
// real backend refuses a wrong one, so the editor's key prompt still shows.

import { ApiError } from '@/api/errors'
import type { HomeContent, Scenario, ScenarioInput } from '@/types'

import { HOME_DEFAULTS, SEED_SCENARIOS } from './seedContent'
import { getState, persist } from './store'

const LAYOUTS = new Set(['kpi-overview', 'analytics-breakdown', 'records-workspace'])

function scenarios(): Scenario[] {
  const state = getState()
  if (!state.scenarios) {
    state.scenarios = SEED_SCENARIOS.map((s) => ({ ...s, highlights: [...s.highlights] }))
    persist()
  }
  return state.scenarios
}

function ordered(list: Scenario[]): Scenario[] {
  return [...list].sort((a, b) => a.order - b.order || a.title.localeCompare(b.title))
}

function slug(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'case'
  )
}

function validInput(body: unknown): ScenarioInput {
  const input = (body ?? {}) as Partial<ScenarioInput>
  for (const field of ['title', 'audience', 'problem', 'prompt'] as const) {
    if (typeof input[field] !== 'string' || !input[field]!.trim()) {
      throw new ApiError(422, `${field} must not be blank`)
    }
  }
  const layout = input.layout ?? 'kpi-overview'
  if (!LAYOUTS.has(layout)) throw new ApiError(422, `Unknown layout: ${layout}`)
  return {
    title: input.title!.trim(),
    audience: input.audience!.trim(),
    problem: input.problem!.trim(),
    layout,
    highlights: (input.highlights ?? []).map((h) => h.trim()).filter(Boolean),
    prompt: input.prompt!.trim(),
    enabled: input.enabled ?? true,
  }
}

function requireAdmin(headers?: Record<string, string>): void {
  if (!headers?.['X-Admin-Key']) throw new ApiError(401, 'Wrong or missing admin key.')
}

function homeContent(): HomeContent {
  const stored = getState().home ?? {}
  const merged = { ...HOME_DEFAULTS }
  for (const key of Object.keys(HOME_DEFAULTS) as (keyof HomeContent)[]) {
    const value = stored[key]
    if (typeof value === 'string' && value.trim()) merged[key] = value
  }
  return merged
}

export function handleContentRequest(
  method: string,
  path: string,
  body: unknown,
  headers?: Record<string, string>,
): unknown {
  const [pathname, query = ''] = path.split('?')
  const segments = pathname.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean)
  const [, resource, id, action] = segments
  const state = getState()

  if (resource === 'home') {
    if (method === 'GET') return homeContent()
    requireAdmin(headers)
    if (method === 'PUT') {
      const values = (body ?? {}) as Partial<HomeContent>
      state.home = Object.fromEntries(
        Object.entries(values).filter(([, v]) => typeof v === 'string' && v.trim()),
      )
      persist()
      return homeContent()
    }
    if (method === 'DELETE') {
      state.home = {}
      persist()
      return homeContent()
    }
    throw new ApiError(405, 'Method not allowed')
  }

  if (resource === 'scenario-order') {
    requireAdmin(headers)
    const ids = ((body ?? {}) as { ids?: string[] }).ids ?? []
    const list = scenarios()
    const unknown = ids.filter((i) => !list.some((s) => s.id === i))
    if (unknown.length) throw new ApiError(404, `Business case not found: ${unknown.join(', ')}`)
    const order = [...new Set([...ids, ...ordered(list).map((s) => s.id)])]
    for (const scenario of list) scenario.order = order.indexOf(scenario.id)
    persist()
    return ordered(list)
  }

  if (resource !== 'scenarios') throw new ApiError(404, `Unknown mock endpoint: ${method} ${path}`)

  if (id === 'reset' && method === 'POST') {
    requireAdmin(headers)
    state.scenarios = undefined
    return ordered(scenarios())
  }

  const list = scenarios()
  if (!id) {
    if (method === 'GET') {
      const all = new URLSearchParams(query).get('all') === 'true'
      return ordered(all ? list : list.filter((s) => s.enabled))
    }
    if (method === 'POST') {
      requireAdmin(headers)
      const input = validInput(body)
      let newId = slug(input.title)
      for (let n = 2; list.some((s) => s.id === newId); n++) newId = `${slug(input.title)}-${n}`
      const created: Scenario = {
        ...input,
        id: newId,
        order: Math.max(-1, ...list.map((s) => s.order)) + 1,
        builtin: false,
      }
      list.push(created)
      persist()
      return created
    }
    throw new ApiError(405, 'Method not allowed')
  }

  if (action) throw new ApiError(404, `Unknown mock endpoint: ${method} ${path}`)
  const index = list.findIndex((s) => s.id === id)
  if (index === -1) throw new ApiError(404, `Business case not found: ${id}`)
  requireAdmin(headers)
  if (method === 'PUT') {
    list[index] = { ...list[index], ...validInput(body) }
    persist()
    return list[index]
  }
  if (method === 'DELETE') {
    list.splice(index, 1)
    persist()
    return undefined
  }
  throw new ApiError(405, 'Method not allowed')
}
