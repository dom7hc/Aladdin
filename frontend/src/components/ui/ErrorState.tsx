import { Button } from './Button'
import { MaterialIcon } from './MaterialIcon'

interface ErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
  className?: string
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'Alladin could not complete your request. Please try again.',
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 rounded-2xl border border-error/30 bg-error-container/10 px-6 py-14 text-center ${className ?? ''}`}
    >
      <MaterialIcon name="error" className="text-error" size={34} />
      <h2 className="text-headline-sm text-on-surface">{title}</h2>
      <p className="max-w-md text-sm text-on-surface-variant">{message}</p>
      {onRetry && (
        <Button variant="secondary" icon="refresh" onClick={onRetry} className="mt-2">
          Try again
        </Button>
      )}
    </div>
  )
}
