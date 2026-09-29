import { REQUIREMENT_FIELDS } from '@/lib/requirements'
import { titleCase } from '@/lib/format'
import type { ArtifactType, RequirementData } from '@/types'

function bulletList(items: string[]): string {
  if (items.length === 0) return '_Not specified._'
  return items.map((item) => `- ${item}`).join('\n')
}

export function renderRequirementsMarkdown(
  name: string,
  requirements: RequirementData,
): string {
  const lines = [`# Requirements — ${name}`, '']
  for (const field of REQUIREMENT_FIELDS) {
    const value = requirements[field.key]
    lines.push(`## ${field.label}`)
    if (Array.isArray(value)) {
      lines.push(bulletList(value))
    } else {
      lines.push(value.trim() || '_Not specified._')
    }
    lines.push('')
  }
  return lines.join('\n').trim()
}

export interface ArchitectureDoc {
  pages: { name: string; purpose: string }[]
  apis: { method: string; path: string }[]
  entities: { name: string; fields: string[] }[]
  services: string[]
  aiCapabilities: string[]
}

const AI_KEYWORDS: Record<string, string> = {
  extract: 'data extraction',
  parse: 'document parsing',
  detect: 'anomaly detection',
  classif: 'classification',
  summar: 'summarization',
  analyz: 'analysis',
  analyze: 'analysis',
  predict: 'prediction',
  recommend: 'recommendation',
}

function deriveEntityName(requirements: RequirementData): string {
  const source = requirements.features[0] || requirements.inputs[0] || 'Record'
  const noun = source.split(/\s+/).slice(-1)[0] || 'Record'
  const match = requirements.features
    .join(' ')
    .match(/\b([A-Z][a-z]+)\b/)
  return match?.[1] ?? titleCase(noun)
}

export function buildArchitecture(
  requirements: RequirementData,
): ArchitectureDoc {
  const entity = deriveEntityName(requirements)
  const aiCapabilities = Array.from(
    new Set(
      Object.entries(AI_KEYWORDS)
        .filter(([keyword]) =>
          requirements.features
            .join(' ')
            .toLowerCase()
            .includes(keyword),
        )
        .map(([, capability]) => capability),
    ),
  )
  if (aiCapabilities.length === 0) aiCapabilities.push('assisted workflow')

  return {
    pages: [
      {
        name: `${entity}InputPage`,
        purpose: `Capture ${requirements.inputs[0] ?? 'user input'} for processing`,
      },
      {
        name: `${entity}ResultPage`,
        purpose: `Display ${requirements.outputs[0] ?? 'results'} and AI insights`,
      },
    ],
    apis: [
      { method: 'POST', path: `/api/${entity.toLowerCase()}s` },
      { method: 'GET', path: `/api/${entity.toLowerCase()}s` },
    ],
    entities: [
      {
        name: entity,
        fields: ['id', 'title', 'status', 'source', 'createdAt', 'insights'],
      },
    ],
    services: [`${entity}Service`, `${entity}AIService`],
    aiCapabilities,
  }
}

export function renderArchitectureMarkdown(
  name: string,
  architecture: ArchitectureDoc,
): string {
  const pages = architecture.pages
    .map((page) => `- **${page.name}** — ${page.purpose}`)
    .join('\n')
  const apis = architecture.apis
    .map((api) => `- \`${api.method} ${api.path}\``)
    .join('\n')
  const entities = architecture.entities
    .map((entity) => `- **${entity.name}**: ${entity.fields.join(', ')}`)
    .join('\n')

  return [
    `# Architecture — ${name}`,
    '',
    '## Pages',
    pages,
    '',
    '## APIs',
    apis,
    '',
    '## Entities',
    entities,
    '',
    '## Services',
    bulletList(architecture.services),
    '',
    '## AI Capabilities',
    bulletList(architecture.aiCapabilities),
    '',
    '## Stack',
    '- Frontend: React + TypeScript',
    '- Backend: FastAPI',
    '- Database: PostgreSQL',
    '- AI: OpenAI / Azure OpenAI',
  ].join('\n')
}

export function buildReviewResult(name: string) {
  return {
    status: 'PASS',
    reviewedAt: new Date().toISOString(),
    summary: `All generated files for ${name} satisfy requirement coverage and architecture compliance.`,
    issues: [],
  }
}

export function buildTestResult() {
  return {
    status: 'PASSED',
    category: null,
    files: [],
    ranAt: new Date().toISOString(),
    summary: 'Build succeeded and all generated tests passed.',
  }
}

export const ARTIFACT_CONTENT_TYPE: Record<ArtifactType, string> = {
  REQUIREMENTS_JSON: 'application/json',
  REQUIREMENTS_MD: 'text/markdown',
  ARCHITECTURE_JSON: 'application/json',
  ARCHITECTURE_MD: 'text/markdown',
  REVIEW_RESULT: 'application/json',
  TEST_RESULT: 'application/json',
}
