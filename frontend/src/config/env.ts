const rawUseMock = import.meta.env.VITE_USE_MOCK

export const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  useMock: rawUseMock === undefined ? true : rawUseMock !== 'false',
  mockLatencyMs: 350,
} as const
