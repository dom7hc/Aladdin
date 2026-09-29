import type { ProjectStatusValue, StepState } from '@/types'

export type StatusTone = 'primary' | 'secondary' | 'tertiary' | 'error' | 'muted'

export interface StatusMeta {
  label: string
  tone: StatusTone
  headline: string
  description: string
}

export const STATUS_META: Record<ProjectStatusValue, StatusMeta> = {
  CREATED: {
    label: 'Draft',
    tone: 'muted',
    headline: 'Preparing your workspace',
    description: 'Your project has been created and is ready for requirements.',
  },
  REQUIREMENT_COLLECTION: {
    label: 'Gathering Requirements',
    tone: 'secondary',
    headline: 'Gathering requirements',
    description: 'Chat with the Genie Architect to shape your PoC spec.',
  },
  REQUIREMENT_READY: {
    label: 'Ready to Build',
    tone: 'secondary',
    headline: 'Requirements captured',
    description: 'Review the blueprint, then confirm to start the build.',
  },
  ARCHITECTING: {
    label: 'Architecting',
    tone: 'primary',
    headline: 'Building your PoC',
    description: 'The Architect agent is drafting the blueprint for your idea.',
  },
  ARCHITECTURE_READY: {
    label: 'Architecture Ready',
    tone: 'primary',
    headline: 'Architecture ready',
    description: 'The blueprint is approved — assembling the source now.',
  },
  GENERATING: {
    label: 'Generating',
    tone: 'primary',
    headline: 'Building your PoC',
    description: 'The Developer agent is conjuring source files into the workspace.',
  },
  REVIEWING: {
    label: 'Reviewing',
    tone: 'primary',
    headline: 'Reviewing the build',
    description: 'The Reviewer agent is auditing generated files for issues.',
  },
  TESTING: {
    label: 'Testing',
    tone: 'primary',
    headline: 'Testing your PoC',
    description: 'The Tester agent is running the build and test pipeline.',
  },
  READY: {
    label: 'Ready',
    tone: 'primary',
    headline: 'Your PoC is ready!',
    description: 'Your working prototype is live and ready to explore.',
  },
  FAILED: {
    label: 'Failed',
    tone: 'error',
    headline: 'The build hit a snag',
    description: 'Generation stopped before completion. Review the log and retry.',
  },
}

export function statusMeta(status: ProjectStatusValue): StatusMeta {
  return STATUS_META[status] ?? STATUS_META.CREATED
}

export interface GenerationStepMeta {
  key: string
  label: string
  description: string
  icon: string
}

export const GENERATION_STEPS: GenerationStepMeta[] = [
  {
    key: 'requirements',
    label: 'Requirements',
    description: 'Structured spec and success criteria',
    icon: 'description',
  },
  {
    key: 'architect',
    label: 'Architect Agent',
    description: 'Blueprint, APIs and data model',
    icon: 'account_tree',
  },
  {
    key: 'developer',
    label: 'Developer Agent',
    description: 'Source files generated in workspace',
    icon: 'code_blocks',
  },
  {
    key: 'reviewer',
    label: 'Reviewer Agent',
    description: 'Requirement and quality review',
    icon: 'fact_check',
  },
  {
    key: 'tester',
    label: 'Tester Agent',
    description: 'Build, tests and diagnosis',
    icon: 'bug_report',
  },
]

export function resolveStepState(
  steps: Record<string, StepState> | undefined,
  key: string,
): StepState {
  return steps?.[key] ?? 'PENDING'
}

export const TERMINAL_STATUSES: ProjectStatusValue[] = ['READY', 'FAILED']
