import { Link } from 'react-router-dom'

import { MaterialIcon } from '@/components/ui/MaterialIcon'

function Logo() {
  return (
    <Link to="/" className="group flex items-center gap-2.5">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-[#00504a] via-[#0dbeb2] to-[#6af8eb] text-[#00201d] shadow-glow-primary transition-transform group-hover:scale-105">
        <MaterialIcon name="magic_button" className="text-[20px] font-bold" />
      </div>
      <span className="bg-gradient-to-r from-on-surface via-primary-fixed to-secondary bg-clip-text text-xl font-extrabold tracking-tight text-transparent">
        Aladdin
      </span>
    </Link>
  )
}

export function Header() {
  return (
    <header className="fixed left-0 right-0 top-0 z-50 h-16 border-b border-outline-variant/40 bg-surface/85 backdrop-blur-xl">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-6">
          <Logo />
          <nav className="hidden items-center gap-6 md:flex">
            <Link
              to="/"
              className="text-sm font-semibold text-primary transition-colors hover:text-primary-fixed"
            >
              Projects
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/" className="btn-primary px-3.5 py-2 text-xs">
            <MaterialIcon name="auto_awesome" size={17} />
            <span className="hidden sm:inline">New PoC</span>
          </Link>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-tr from-secondary to-tertiary-container text-[#251a00] ring-2 ring-secondary/40">
            <MaterialIcon name="person" filled size={18} />
          </div>
        </div>
      </div>
    </header>
  )
}
