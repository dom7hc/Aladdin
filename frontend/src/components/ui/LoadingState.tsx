import { MaterialIcon } from './MaterialIcon'

interface LoadingStateProps {
  label?: string
  className?: string
}

export function LoadingState({ label = 'Summoning data…', className }: LoadingStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-16 ${className ?? ''}`}>
      <MaterialIcon name="progress_activity" className="animate-spin text-primary" size={32} />
      <p className="text-sm text-on-surface-variant">{label}</p>
    </div>
  )
}
