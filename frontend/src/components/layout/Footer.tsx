export function Footer() {
  return (
    <footer className="relative z-10 w-full border-t border-outline-variant/40 bg-surface-container-lowest py-6">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 px-4 text-xs text-on-surface-variant sm:flex-row sm:px-6 lg:px-8">
        <span>© BD/SWD Hackathon - Need4Sleep - 2026</span>
        <div className="flex items-center gap-5">
          <span className="transition-colors hover:text-primary">Documentation</span>
          <span className="transition-colors hover:text-primary">Changelog</span>
          <span className="text-outline-variant">•</span>
          <span className="text-[11px] font-bold uppercase tracking-wider text-secondary">
            v1.0
          </span>
        </div>
      </div>
    </footer>
  )
}
