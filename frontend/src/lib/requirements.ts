import type { RequirementData, RequirementField } from '@/types'

export interface RequirementFieldMeta {
  key: RequirementField
  label: string
  icon: string
  optional?: boolean
}

export const REQUIREMENT_FIELDS: RequirementFieldMeta[] = [
  { key: 'problem', label: 'Goal', icon: 'flag' },
  { key: 'targetUsers', label: 'Target Users', icon: 'group' },
  { key: 'mainWorkflow', label: 'Main Workflow', icon: 'route' },
  { key: 'features', label: 'Core Features', icon: 'checklist' },
  { key: 'inputs', label: 'Inputs', icon: 'file_open' },
  { key: 'outputs', label: 'Outputs', icon: 'output' },
  { key: 'constraints', label: 'Constraints', icon: 'gavel', optional: true },
  { key: 'successCriteria', label: 'Success Criteria', icon: 'verified' },
]

export const REQUIRED_FIELD_KEYS: RequirementField[] = REQUIREMENT_FIELDS.filter(
  (field) => !field.optional,
).map((field) => field.key)

export const EMPTY_REQUIREMENTS: RequirementData = {
  problem: '',
  targetUsers: [],
  mainWorkflow: [],
  features: [],
  inputs: [],
  outputs: [],
  constraints: [],
  successCriteria: [],
}

export function isFieldFilled(
  requirements: RequirementData,
  key: RequirementField,
): boolean {
  const value = requirements[key]
  if (Array.isArray(value)) return value.length > 0
  return value.trim().length > 0
}

export function requirementCompletion(requirements: RequirementData): number {
  const filled = REQUIRED_FIELD_KEYS.filter((key) =>
    isFieldFilled(requirements, key),
  ).length
  return Math.round((filled / REQUIRED_FIELD_KEYS.length) * 100)
}

export function missingRequirementFields(
  requirements: RequirementData,
): RequirementField[] {
  return REQUIRED_FIELD_KEYS.filter((key) => !isFieldFilled(requirements, key))
}

export function labelForRequirementField(key: RequirementField): string {
  return REQUIREMENT_FIELDS.find((field) => field.key === key)?.label ?? key
}
