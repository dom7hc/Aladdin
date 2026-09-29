import type { ReactNode } from 'react'

import { AmbientBackground } from './AmbientBackground'
import { Footer } from './Footer'
import { Header } from './Header'

interface AppLayoutProps {
  children: ReactNode
  footer?: boolean
}

export function AppLayout({ children, footer = true }: AppLayoutProps) {
  return (
    <div className="relative flex min-h-screen flex-col">
      <AmbientBackground />
      <Header />
      <main className="relative z-10 flex-1 pt-16">{children}</main>
      {footer && <Footer />}
    </div>
  )
}
