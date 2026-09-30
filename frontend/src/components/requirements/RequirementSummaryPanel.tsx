import { MaterialIcon } from '@/components/ui/MaterialIcon'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { cn } from '@/lib/cn'
import {
  REQUIREMENT_FIELDS,
  isFieldFilled,
  missingRequirementFields,
} from '@/lib/requirements'
import type { RequirementData } from '@/types'

interface RequirementSummaryPanelProps {
  projectName: string
  requirements: RequirementData
  completion: number
  onAutofill?: () => void
  autofilling?: boolean
  onReview?: () => void
  finalizing?: boolean
}

function FieldValue({ value }: { value: string | string[] }) {
  if (Array.isArray(value)) {
    return (
      <ul className="space-y-1 pl-6 text-xs leading-relaxed text-on-surface-variant">
        {value.map((item) => (
          <li key={item} className="flex items-start gap-1.5">
            <span className="font-bold text-secondary">•</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    )
  }
  return <p className="pl-6 text-xs leading-relaxed text-on-surface-variant">{value}</p>
}

export function RequirementSummaryPanel({
  projectName,
  requirements,
  completion,
  onAutofill,
  autofilling = false,
  onReview,
  finalizing = false,
}: RequirementSummaryPanelProps) {
  const missing = missingRequirementFields(requirements)
  const ready = missing.length === 0

  return (
    <div className="glass-card flex flex-col gap-4 p-5 sm:p-6">
      <div className="flex items-center justify-between border-b border-outline-variant/40 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-base font-bold tracking-wide text-on-surface">
            {projectName}
          </span>
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-outline-variant/40 bg-surface-container-lowest p-3.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-on-surface">
            Requirements {completion}% complete
          </span>
          <span className="text-sm font-extrabold text-primary drop-shadow-[0_0_6px_rgba(71,219,207,0.5)]">
            {completion}%
          </span>
        </div>
        <ProgressBar value={completion} />
      </div>

      <div className="no-scrollbar flex max-h-[440px] flex-col gap-2.5 overflow-y-auto pr-1">
        {REQUIREMENT_FIELDS.map((field) => {
          const filled = isFieldFilled(requirements, field.key)
          const value = requirements[field.key]
          return (
            <div
              key={field.key}
              className={cn(
                'flex flex-col gap-1 rounded-xl border p-3.5 transition-all',
                filled
                  ? 'border-primary/30 bg-surface-container-lowest/80 hover:border-primary/60'
                  : 'border-outline-variant/50 bg-surface-container-lowest/40',
              )}
            >
              <div className="flex items-center justify-between">
                <div
                  className={cn(
                    'flex items-center gap-1.5 text-xs font-bold',
                    filled
                      ? 'text-primary'
                      : field.optional
                        ? 'text-white'
                        : 'text-secondary',
                  )}
                >
                  <MaterialIcon
                    name={filled ? 'check_circle' : 'radio_button_unchecked'}
                    size={17}
                  />
                  <span>{field.label}</span>
                </div>
                <span
                  className={cn(
                    'rounded-full border px-2 py-0.5 text-[11px] font-semibold',
                    filled
                      ? 'border-primary/30 bg-primary/10 text-primary'
                      : field.optional
                        ? 'border-white/30 bg-white/15 text-white'
                        : 'border-secondary/30 bg-secondary/15 text-secondary',
                  )}
                >
                  {filled ? 'Captured' : field.optional ? 'Optional' : 'Waiting'}
                </span>
              </div>
              {filled ? (
                <FieldValue value={value} />
              ) : (
                <p className="pl-6 text-xs italic text-on-surface-variant/80">
                  Not specified yet
                </p>
              )}
            </div>
          )
        })}
      </div>

      <div className="flex flex-col gap-3 pt-2">
        <button
          type="button"
          disabled={!ready || finalizing}
          onClick={onReview}
          className={cn(
            'flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition-all',
            ready
              ? 'bg-gradient-to-r from-secondary via-secondary-fixed to-[#d97706] text-[#251a00] shadow-glow-gold hover:brightness-105 active:scale-95'
              : 'cursor-not-allowed border border-outline-variant/60 bg-surface-container text-outline',
          )}
        >
          <MaterialIcon name={ready ? 'bolt' : 'lock'} size={17} filled={ready} />
          {finalizing
            ? 'Finalizing…'
            : ready
              ? 'Review Requirements'
              : `Review Requirements (${missing.length} remaining)`}
        </button>

        {!ready && onAutofill && (
          <button
            type="button"
            disabled={autofilling}
            onClick={onAutofill}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-tertiary/40 bg-gradient-to-r from-tertiary/20 via-tertiary/10 to-secondary/20 px-4 py-2.5 text-xs font-semibold text-tertiary-fixed transition-all hover:from-tertiary/30 hover:to-secondary/30 active:scale-95 disabled:cursor-wait disabled:opacity-70"
          >
            <MaterialIcon name="magic_button" size={17} className="text-secondary" />
            {autofilling ? 'Filling…' : 'Autofill remaining with Aladdin best practices'}
          </button>
        )}
      </div>
    </div>
  )
}
