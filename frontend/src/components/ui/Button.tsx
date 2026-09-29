import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cn } from '@/lib/cn'

import { MaterialIcon } from './MaterialIcon'

type ButtonVariant = 'primary' | 'secondary' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  block?: boolean
  loading?: boolean
  icon?: string
  iconFilled?: boolean
  trailingIcon?: string
  children?: ReactNode
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
}

export function Button({
  variant = 'primary',
  block = false,
  loading = false,
  icon,
  iconFilled,
  trailingIcon,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={cn(VARIANT_CLASSES[variant], block && 'w-full', className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <MaterialIcon name="progress_activity" className="animate-spin" size={18} />
      ) : (
        icon && <MaterialIcon name={icon} filled={iconFilled} size={18} />
      )}
      {children}
      {trailingIcon && <MaterialIcon name={trailingIcon} size={18} />}
    </button>
  )
}
