import { cn } from '@/lib/cn'

import { MaterialIcon } from './MaterialIcon'

const STEPS = ['Chat', 'Review', 'Build', 'Working PoC']

interface WizardStepperProps {
  current: number
  className?: string
}

export function WizardStepper({ current, className }: WizardStepperProps) {
  return (
    <nav
      aria-label="Progress"
      className={cn('flex items-center gap-1.5 overflow-x-auto py-1 sm:gap-2', className)}
    >
      {STEPS.map((label, index) => {
        const isActive = index === current
        const isComplete = index < current
        return (
          <div key={label} className="flex flex-shrink-0 items-center gap-1.5 sm:gap-2">
            <div
              className={cn(
                'flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs font-semibold transition-colors',
                isActive &&
                  'bg-gradient-to-r from-primary-container to-primary text-on-primary shadow-glow-primary',
                isComplete &&
                  'border border-primary/40 bg-surface-container-low text-primary',
                !isActive &&
                  !isComplete &&
                  'border border-outline-variant/60 bg-surface-container-lowest text-on-surface-variant',
              )}
            >
              <span
                className={cn(
                  'flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-extrabold',
                  isActive
                    ? 'bg-on-primary/20 text-on-primary'
                    : isComplete
                      ? 'bg-primary/20 text-primary'
                      : 'bg-surface-container-high text-on-surface-variant',
                )}
              >
                {isComplete ? <MaterialIcon name="check" size={12} /> : index + 1}
              </span>
              <span>{label}</span>
            </div>
            {index < STEPS.length - 1 && (
              <MaterialIcon
                name="chevron_right"
                size={16}
                className={isComplete ? 'text-primary' : 'text-outline-variant'}
              />
            )}
          </div>
        )
      })}
    </nav>
  )
}
