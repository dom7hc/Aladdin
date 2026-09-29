const rawUseMock = import.meta.env.VITE_USE_MOCK

function parseFlag(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined || value.trim() === '') return fallback
  return !['false', '0', 'no', 'off'].includes(value.trim().toLowerCase())
}

export const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  useMock: parseFlag(rawUseMock, true),
  mockLatencyMs: 350,
} as const
