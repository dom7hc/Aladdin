import { EMPTY_REQUIREMENTS } from '@/lib/requirements'
import { titleCase } from '@/lib/format'
import type { RequirementData } from '@/types'

const STOP_WORDS = new Set([
  'i',
  'a',
  'an',
  'the',
  'want',
  'need',
  'build',
  'create',
  'make',
  'me',
  'my',
  'to',
  'that',
  'which',
  'will',
  'can',
  'for',
  'with',
  'app',
  'application',
  'tool',
  'system',
  'please',
  'help',
  'using',
])

export function deriveProjectName(idea: string): string {
  const words = idea
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .filter((word) => word && !STOP_WORDS.has(word.toLowerCase()))
    .slice(0, 3)

  if (words.length === 0) return 'Untitled PoC'
  return titleCase(words.join(' '))
}

export function splitItems(text: string): string[] {
  const cleaned = text.replace(/^[\s\-*•]+/, '').trim()
  if (!cleaned) return []
  const items = cleaned
    .split(/\s*(?:,|;|\n|\band\b|\bplus\b)\s*/i)
    .map((item) => item.replace(/^[\s\-*•]+/, '').trim())
    .filter((item) => item.length > 1)
  return items.length > 0 ? items : [cleaned]
}

interface FlowStep {
  apply: (requirements: RequirementData, message: string) => RequirementData
  reply: (message: string) => string
}

const FLOW: FlowStep[] = [
  {
    apply: (requirements, message) => ({
      ...requirements,
      problem: message.trim(),
    }),
    reply: () =>
      'Got it — I locked that in as the Goal. Who will primarily use this application, and in what context?',
  },
  {
    apply: (requirements, message) => ({
      ...requirements,
      targetUsers: splitItems(message),
    }),
    reply: () =>
      'Perfect, Target Users captured. Walk me through the main workflow — what happens step by step when someone uses it?',
  },
  {
    apply: (requirements, message) => ({
      ...requirements,
      mainWorkflow: splitItems(message),
    }),
    reply: () =>
      'The workflow is clear. What core features should the PoC include to support it?',
  },
  {
    apply: (requirements, message) => ({
      ...requirements,
      features: splitItems(message),
    }),
    reply: () =>
      'Excellent. What inputs does the system receive — files, forms, API payloads, or documents?',
  },
  {
    apply: (requirements, message) => ({
      ...requirements,
      inputs: splitItems(message),
    }),
    reply: () =>
      'Noted. What should the system produce as outputs — screens, reports, exports, or alerts?',
  },
  {
    apply: (requirements, message) => ({
      ...requirements,
      outputs: splitItems(message),
    }),
    reply: () =>
      'Almost there. How will you know the PoC succeeded? Describe the success criteria.',
  },
  {
    apply: (requirements, message) => ({
      ...requirements,
      successCriteria: splitItems(message),
    }),
    reply: () =>
      'Your blueprint is complete! I captured the goal, users, workflow, features, inputs, outputs and success criteria. Review the summary and confirm whenever you are ready to build. ✦',
  },
]

export const GREETING =
  'Welcome! Let us shape your PoC. To begin, what problem should this application solve, and what outcome are you hoping for?'

// Mirrors AUTOFILL_DEFAULTS in backend/app/agents/stubs.py — keep both in step.
// constraints stays unset: it is optional and never blocks readiness.
export const AUTOFILL_DEFAULTS: Partial<
  Record<Exclude<keyof RequirementData, 'problem'>, string[]>
> = {
  targetUsers: ['Team leads and managers', 'Operations staff', 'Business stakeholders'],
  mainWorkflow: [
    'Open the dashboard',
    'Filter and explore the latest data',
    'Act on the reported results',
  ],
  features: ['KPI overview with charts', 'Filterable record tables', 'Realistic seeded sample data'],
  inputs: ['Records entered through forms', 'Uploaded or imported data'],
  outputs: [
    'Interactive dashboard with KPIs, trends and breakdowns',
    'Exportable reports',
  ],
  successCriteria: [
    'The dashboard loads populated with sample data',
    'Every widget renders from a working API endpoint',
  ],
}

export function autofillMissing(current: RequirementData): {
  requirements: RequirementData
  filledCount: number
} {
  const next = { ...current }
  let filledCount = 0
  for (const field of Object.keys(AUTOFILL_DEFAULTS) as Exclude<
    keyof RequirementData,
    'problem'
  >[]) {
    const value = AUTOFILL_DEFAULTS[field]
    if (!value) continue
    if (Array.isArray(next[field]) && next[field].length === 0) {
      next[field] = [...value]
      filledCount += 1
    }
  }
  return { requirements: next, filledCount }
}

export interface AdvanceResult {
  requirements: RequirementData
  message: string
}

export function advanceRequirements(
  current: RequirementData | undefined,
  userMessage: string,
  userTurnIndex: number,
): AdvanceResult {
  const base = current ?? { ...EMPTY_REQUIREMENTS }
  const step = FLOW[Math.min(userTurnIndex, FLOW.length - 1)]

  if (userTurnIndex >= FLOW.length) {
    return {
      requirements: base,
      message:
        'All required modules are captured. Confirm the blueprint to start building your PoC.',
    }
  }

  return {
    requirements: step.apply(base, userMessage),
    message: step.reply(userMessage),
  }
}
