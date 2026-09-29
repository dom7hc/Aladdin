import { cn } from '@/lib/cn'

interface MaterialIconProps {
  name: string
  className?: string
  filled?: boolean
  size?: number
}

export function MaterialIcon({
  name,
  className,
  filled = false,
  size,
}: MaterialIconProps) {
  return (
    <span
      aria-hidden="true"
      className={cn('material-symbols-outlined', filled && 'fill', className)}
      style={size ? { fontSize: `${size}px` } : undefined}
    >
      {name}
    </span>
  )
}
