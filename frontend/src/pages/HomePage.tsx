import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { ProjectCard } from '@/components/projects/ProjectCard'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { MaterialIcon } from '@/components/ui/MaterialIcon'
import { useCreateProject, useProjectsQuery, useScenariosQuery } from '@/hooks/useProjects'
import type { ProjectStatusValue } from '@/types'

const STATUS_ORDER: ProjectStatusValue[] = [
  'CREATED',
  'REQUIREMENT_COLLECTION',
  'REQUIREMENT_READY',
  'ARCHITECTING',
  'ARCHITECTURE_READY',
  'GENERATING',
  'REVIEWING',
  'TESTING',
  'READY',
  'FAILED',
]

type StatusGroup = 'IN_PROGRESS' | 'READY' | 'FAILED'

const STATUS_GROUPS: { value: StatusGroup; label: string }[] = [
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'READY', label: 'Ready' },
  { value: 'FAILED', label: 'Failed' },
]

function statusGroupOf(status: ProjectStatusValue): StatusGroup {
  if (status === 'READY') return 'READY'
  if (status === 'FAILED') return 'FAILED'
  return 'IN_PROGRESS'
}

type SortKey = 'status' | 'name' | 'createdAt'

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'status', label: 'Sort: Status' },
  { value: 'name', label: 'Sort: Name' },
  { value: 'createdAt', label: 'Sort: Newest' },
]

const SELECT_CLASS =
  'h-10 w-full appearance-none rounded-lg border border-outline-variant/80 bg-surface-container-lowest pl-9 pr-8 text-body-sm text-on-surface outline-none transition-all focus:border-primary focus:ring-1 focus:ring-primary/40'

export function HomePage() {
  const navigate = useNavigate()
  const [idea, setIdea] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusGroup | 'ALL'>('ALL')
  const [sortKey, setSortKey] = useState<SortKey>('createdAt')
  const createProject = useCreateProject()
  const scenariosQuery = useScenariosQuery()

  const projectsQuery = useProjectsQuery()

  const readyCount = (projectsQuery.data ?? []).filter(
    (project) => project.status === 'READY',
  ).length

  const projects = useMemo(() => {
    const list = projectsQuery.data ?? []
    const term = search.trim().toLowerCase()
    const filtered = list.filter((project) => {
      const matchesTerm =
        !term ||
        project.name.toLowerCase().includes(term) ||
        project.description.toLowerCase().includes(term)
      const matchesStatus =
        statusFilter === 'ALL' || statusGroupOf(project.status) === statusFilter
      return matchesTerm && matchesStatus
    })
    return [...filtered].sort((a, b) => {
      if (sortKey === 'name') return a.name.localeCompare(b.name)
      if (sortKey === 'createdAt') return b.createdAt.localeCompare(a.createdAt)
      return STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status)
    })
  }, [projectsQuery.data, search, statusFilter, sortKey])

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
            <span>Make your wish come true</span>
          </div>

          <h1 className="mb-3 text-center text-display-lg-mobile font-extrabold tracking-tight text-on-surface sm:text-display-lg">
            Turn your idea into a{' '}
            <span className="text-gradient-primary drop-shadow-[0_0_20px_rgba(71,219,207,0.35)]">
              working dashboard
            </span>
          </h1>
          <p className="mb-8 max-w-lg text-center text-body-lg text-on-surface-variant">
            Describe the decision you need to make. You get a working dashboard and a slide
            deck to present it.
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
                placeholder="Which numbers do you need to see, and who needs to see them?"
                className="w-full resize-none border-none bg-transparent p-2 text-body-md text-on-surface outline-none placeholder:text-outline/70"
              />
              <div className="mt-2 flex items-center justify-end border-t border-outline-variant/40 pt-3">
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

          <div className="mt-5 w-full">
            <p className="mb-2 text-center text-[11px] uppercase tracking-wider text-on-surface-variant/80">
              Or start from one of these
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {(scenariosQuery.data ?? []).map((scenario) => (
                <button
                  key={scenario.id}
                  type="button"
                  title={scenario.problem}
                  onClick={() => setIdea(scenario.prompt)}
                  className="max-w-full rounded-full border border-outline-variant/60 bg-surface-container-lowest px-3 py-1.5 text-[11px] text-on-surface-variant transition-colors hover:border-primary/50 hover:text-primary"
                >
                  {scenario.title}
                  <span className="ml-1.5 text-outline/80">{scenario.audience}</span>
                </button>
              ))}
            </div>
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
                  {readyCount} ready
                </span>
              </div>
              <p className="text-body-sm text-on-surface-variant">
                Review specs, resume sessions, or launch live prototypes.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="relative flex items-center">
                <MaterialIcon
                  name="filter_list"
                  size={16}
                  className="pointer-events-none absolute left-3 text-outline"
                />
                <select
                  value={statusFilter}
                  onChange={(event) =>
                    setStatusFilter(event.target.value as StatusGroup | 'ALL')
                  }
                  className={`${SELECT_CLASS} sm:w-44`}
                >
                  <option value="ALL">All statuses</option>
                  {STATUS_GROUPS.map((group) => (
                    <option key={group.value} value={group.value}>
                      {group.label}
                    </option>
                  ))}
                </select>
                <MaterialIcon
                  name="expand_more"
                  size={16}
                  className="pointer-events-none absolute right-3 text-outline"
                />
              </div>
              <div className="relative flex items-center">
                <MaterialIcon
                  name="sort"
                  size={16}
                  className="pointer-events-none absolute left-3 text-outline"
                />
                <select
                  value={sortKey}
                  onChange={(event) => setSortKey(event.target.value as SortKey)}
                  className={`${SELECT_CLASS} sm:w-40`}
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <MaterialIcon
                  name="expand_more"
                  size={16}
                  className="pointer-events-none absolute right-3 text-outline"
                />
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
              <p className="text-on-surface">
                {(projectsQuery.data ?? []).length === 0 ? 'No PoCs yet' : 'No matching PoCs'}
              </p>
              <p className="text-sm text-on-surface-variant">
                {(projectsQuery.data ?? []).length === 0
                  ? 'Describe an idea above and Aladdin will start building.'
                  : 'Try a different search term or status filter.'}
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
