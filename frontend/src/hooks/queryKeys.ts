export const queryKeys = {
  projects: ['projects'] as const,
  project: (id: string) => ['projects', id] as const,
  messages: (id: string) => ['projects', id, 'messages'] as const,
  requirements: (id: string) => ['projects', id, 'requirements'] as const,
  status: (id: string) => ['projects', id, 'status'] as const,
  artifacts: (id: string) => ['projects', id, 'artifacts'] as const,
  preview: (id: string) => ['projects', id, 'preview'] as const,
  scenarios: ['scenarios'] as const,
}
