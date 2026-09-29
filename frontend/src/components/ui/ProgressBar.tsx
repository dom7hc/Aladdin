import { cn } from '@/lib/cn'

interface ProgressBarProps {
  value: number
  className?: string
  gradient?: 'primary' | 'gold'
}

export function ProgressBar({
  value,
  className,
  gradient = 'primary',
}: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value))
  return (
    <div
      className={cn(
        'h-2.5 w-full overflow-hidden rounded-full border border-outline-variant/50 bg-surface-container-lowest p-0.5',
        className,
      )}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn(
          'h-full rounded-full transition-all duration-500',
          gradient === 'primary'
            ? 'bg-gradient-to-r from-primary-container via-primary to-secondary shadow-glow-primary'
            : 'bg-gradient-to-r from-secondary via-secondary-fixed to-primary shadow-glow-gold',
        )}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}
