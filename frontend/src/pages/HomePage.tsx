import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { ProjectCard } from '@/components/projects/ProjectCard'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { MaterialIcon } from '@/components/ui/MaterialIcon'
import { useCreateProject, useProjectsQuery } from '@/hooks/useProjects'

const SUGGESTIONS = [
  'An AI app that analyzes PDF invoices, extracts line items, and flags anomalies.',
  'A support assistant that answers HR policy questions from internal documents.',
  'A dashboard that clusters customer feedback and summarizes sentiment trends.',
]

export function HomePage() {
  const navigate = useNavigate()
  const [idea, setIdea] = useState('')
  const [search, setSearch] = useState('')
  const createProject = useCreateProject()

  const projectsQuery = useProjectsQuery()

  const projects = useMemo(() => {
    const list = projectsQuery.data ?? []
    const term = search.trim().toLowerCase()
    if (!term) return list
    return list.filter(
      (project) =>
        project.name.toLowerCase().includes(term) ||
        project.description.toLowerCase().includes(term),
    )
  }, [projectsQuery.data, search])

  const activeCount = (projectsQuery.data ?? []).filter(
    (project) => !['READY', 'FAILED'].includes(project.status),
  ).length

  const submit = () => {
    const trimmed = idea.trim()
    if (!trimmed) return
    createProject.mutate(trimmed, {
      onSuccess: (project) => navigate(`/projects/${project.id}/chat`),
    })
  }

  return (
    <AppLayout>
      <div className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <section className="mx-auto flex w-full max-w-3xl flex-col items-center pb-8 pt-6">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-secondary/30 bg-surface-container-high/80 px-3 py-1 text-[11px] text-secondary backdrop-blur-sm">
            <MaterialIcon name="stars" size={14} />
            <span>Your wish is our command</span>
          </div>

          <h1 className="mb-3 text-center text-display-lg-mobile font-extrabold tracking-tight text-on-surface sm:text-display-lg">
            Turn your idea into a{' '}
            <span className="text-gradient-primary drop-shadow-[0_0_20px_rgba(71,219,207,0.35)]">
              working PoC
            </span>
          </h1>
          <p className="mb-8 max-w-lg text-center text-body-lg text-on-surface-variant">
            Describe what you want to build. AI turns your requirements into interactive
            prototypes in seconds.
          </p>

          <div className="group relative w-full">
            <div className="absolute -inset-0.5 -z-10 rounded-2xl bg-gradient-to-r from-primary/20 via-tertiary/10 to-secondary/20 blur-sm transition-opacity duration-300 group-focus-within:opacity-100 sm:opacity-40" />
            <div className="glass-card flex flex-col p-4 focus-within:border-primary/70 focus-within:ring-2 focus-within:ring-primary/30">
              <textarea
                value={idea}
                onChange={(event) => setIdea(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    submit()
                  }
                }}
                rows={3}
                placeholder="Describe the application, data inputs, and desired workflow..."
                className="w-full resize-none border-none bg-transparent p-2 text-body-md text-on-surface outline-none placeholder:text-outline/70"
              />
              <div className="mt-2 flex items-center justify-between border-t border-outline-variant/40 pt-3">
                <button
                  type="button"
                  disabled={createProject.isPending}
                  onClick={() => {
                    const next = idea.trim()
                    if (!next) {
                      setIdea(SUGGESTIONS[0])
                      return
                    }
                    setIdea(
                      `${next} Include role-based access, automated alerts for risk triggers, and synthetic mock datasets.`,
                    )
                  }}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-label-md text-on-surface-variant transition-colors hover:bg-surface-container hover:text-secondary disabled:opacity-60"
                >
                  <MaterialIcon name="auto_awesome" size={18} />
                  <span className="hidden sm:inline">Enhance prompt</span>
                </button>
                <Button
                  onClick={submit}
                  loading={createProject.isPending}
                  trailingIcon={createProject.isPending ? undefined : 'arrow_forward'}
                  className="px-4 py-2 text-xs"
                >
                  {createProject.isPending ? 'Synthesizing…' : 'Start Building'}
                </Button>
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => setIdea(suggestion)}
                className="max-w-full truncate rounded-full border border-outline-variant/60 bg-surface-container-lowest px-3 py-1.5 text-[11px] text-on-surface-variant transition-colors hover:border-primary/50 hover:text-primary"
              >
                {suggestion}
              </button>
            ))}
          </div>

          {createProject.isError && (
            <p className="mt-4 text-sm text-error">
              Could not create the project. Please try again.
            </p>
          )}
        </section>

        <section className="mt-12 w-full border-t border-outline-variant/30 pt-8">
          <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <div className="mb-1 flex items-center gap-2">
                <h2 className="text-headline-lg tracking-tight text-on-surface">
                  Recent Projects
                </h2>
                <span className="rounded-full border border-outline-variant/50 bg-surface-container-high px-2.5 py-0.5 text-[11px] font-semibold text-primary-fixed">
                  {activeCount} active
                </span>
              </div>
              <p className="text-body-sm text-on-surface-variant">
                Review specs, resume sessions, or launch live prototypes.
              </p>
            </div>
            <div className="relative flex items-center">
              <MaterialIcon
                name="search"
                size={18}
                className="absolute left-3 text-outline"
              />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search PoCs..."
                className="h-10 w-full rounded-lg border border-outline-variant/80 bg-surface-container-lowest pl-9 pr-3 text-body-sm text-on-surface outline-none transition-all placeholder:text-outline focus:border-primary focus:ring-1 focus:ring-primary/40 sm:w-64"
              />
            </div>
          </div>

          {projectsQuery.isError ? (
            <ErrorState
              title="Could not load projects"
              message="The project list is unavailable right now."
              onRetry={() => void projectsQuery.refetch()}
            />
          ) : projectsQuery.isPending ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {[0, 1, 2].map((key) => (
                <div
                  key={key}
                  className="h-40 animate-pulse rounded-2xl border border-outline-variant/40 bg-surface-container-low/60"
                />
              ))}
            </div>
          ) : projects.length === 0 ? (
            <div className="glass-card flex flex-col items-center gap-2 px-6 py-12 text-center">
              <MaterialIcon name="auto_awesome" size={30} className="text-secondary" />
              <p className="text-on-surface">No PoCs yet</p>
              <p className="text-sm text-on-surface-variant">
                Describe an idea above and the Genie will start building.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {projects.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          )}
        </section>
      </div>
    </AppLayout>
  )
}
