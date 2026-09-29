import { cn } from '@/lib/cn'
import type { StatusTone } from '@/lib/status'

interface StatusBadgeProps {
  label: string
  tone?: StatusTone
  pulse?: boolean
  className?: string
}

const TONE_CLASSES: Record<StatusTone, string> = {
  primary: 'bg-primary/12 border-primary/40 text-primary',
  secondary: 'bg-secondary/12 border-secondary/40 text-secondary',
  tertiary: 'bg-tertiary/12 border-tertiary/40 text-tertiary',
  error: 'bg-error/12 border-error/40 text-error',
  muted: 'bg-surface-container-high/70 border-outline-variant/60 text-on-surface-variant',
}

const DOT_CLASSES: Record<StatusTone, string> = {
  primary: 'bg-primary',
  secondary: 'bg-secondary',
  tertiary: 'bg-tertiary',
  error: 'bg-error',
  muted: 'bg-outline',
}

export function StatusBadge({
  label,
  tone = 'primary',
  pulse = false,
  className,
}: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-wider',
        TONE_CLASSES[tone],
        className,
      )}
    >
      <span className="relative flex h-1.5 w-1.5">
        {pulse && (
          <span
            className={cn(
              'absolute inline-flex h-full w-full animate-ping rounded-full opacity-75',
              DOT_CLASSES[tone],
            )}
          />
        )}
        <span className={cn('relative inline-flex h-1.5 w-1.5 rounded-full', DOT_CLASSES[tone])} />
      </span>
      {label}
    </span>
  )
}
