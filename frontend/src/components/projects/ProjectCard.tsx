import { Link } from 'react-router-dom'

import { MaterialIcon } from '@/components/ui/MaterialIcon'
import { useDeleteProject } from '@/hooks/useProjects'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { statusMeta } from '@/lib/status'
import { timeAgo } from '@/lib/format'
import type { Project } from '@/types'

function routeForStatus(project: Project): string {
  const id = project.id
  switch (project.status) {
    case 'READY':
      return `/projects/${id}/result`
    case 'REQUIREMENT_READY':
      return `/projects/${id}/review`
    case 'ARCHITECTING':
    case 'ARCHITECTURE_READY':
    case 'GENERATING':
    case 'REVIEWING':
    case 'TESTING':
    case 'FAILED':
      return `/projects/${id}/generate`
    default:
      return `/projects/${id}/chat`
  }
}

export function ProjectCard({ project }: { project: Project }) {
  const meta = statusMeta(project.status)
  const isLive =
    ['ARCHITECTING', 'GENERATING', 'REVIEWING', 'TESTING'].includes(project.status)

  const remove = useDeleteProject()
  const onDelete = (event: React.MouseEvent) => {
    // The whole card is a link; deleting must not open the project.
    event.preventDefault()
    event.stopPropagation()
    if (window.confirm(`Delete "${project.name}"? This removes its chat, data and generated app.`)) {
      remove.mutate(project.id, {
        onError: (error) => window.alert(`Could not delete the project: ${error.message}`),
      })
    }
  }

  return (
    <Link
      to={routeForStatus(project)}
      className="glass-card group flex flex-col justify-between p-5 transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-glow-primary"
    >
      <div className="mb-4">
        <div className="mb-2 flex items-center justify-between">
          <StatusBadge label={meta.label} tone={meta.tone} pulse={isLive} />
          <div className="flex items-center gap-1">
            <span className="text-[11px] text-outline">{timeAgo(project.updatedAt)}</span>
            {!isLive && (
              <button
                type="button"
                onClick={onDelete}
                disabled={remove.isPending}
                aria-label={`Delete ${project.name}`}
                title="Delete project"
                className="flex rounded-full p-1 text-outline transition-colors hover:bg-error/10 hover:text-error disabled:opacity-50"
              >
                <MaterialIcon name="delete" size={16} />
              </button>
            )}
          </div>
        </div>
        <h3 className="mb-1 text-headline-sm text-on-surface transition-colors group-hover:text-primary">
          {project.name}
        </h3>
        <p className="line-clamp-2 text-body-sm text-on-surface-variant">
          {project.description}
        </p>
      </div>
      <div className="flex items-center justify-between border-t border-outline-variant/40 pt-3">
        <span className="text-[11px] text-on-surface-variant">
          {project.completion}% complete
        </span>
        <span className="flex items-center gap-1 text-label-md font-semibold text-primary">
          Open
          <MaterialIcon
            name="arrow_forward"
            size={16}
            className="transition-transform group-hover:translate-x-1"
          />
        </span>
      </div>
    </Link>
  )
}
