import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { MaterialIcon } from '@/components/ui/MaterialIcon'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { cn } from '@/lib/cn'
import {
  GENERATION_STEPS,
  resolveStepState,
  statusMeta,
} from '@/lib/status'
import { timeAgo } from '@/lib/format'
import { useProjectQuery } from '@/hooks/useProject'
import { useProjectStatusQuery, useStartGeneration } from '@/hooks/useProjectStatus'
import type { StepState } from '@/types'

const STEP_ICON: Record<StepState, { icon: string; className: string }> = {
  COMPLETED: { icon: 'check_circle', className: 'text-primary' },
  RUNNING: { icon: 'progress_activity', className: 'text-secondary animate-spin' },
  PENDING: { icon: 'radio_button_unchecked', className: 'text-outline-variant' },
  FAILED: { icon: 'cancel', className: 'text-error' },
}

export function GenerationPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const projectQuery = useProjectQuery(id)
  const statusQuery = useProjectStatusQuery(id, { poll: true })
  const startGeneration = useStartGeneration(id ?? '')

  const status = statusQuery.data

  useEffect(() => {
    if (status?.status === 'READY' && id) {
      navigate(`/projects/${id}/result`, { replace: true })
    }
  }, [status?.status, id, navigate])

  const retry = () => {
    startGeneration.mutate(undefined, {
      onSuccess: () => void statusQuery.refetch(),
    })
  }

  if (projectQuery.isError || statusQuery.isError) {
    return (
      <AppLayout>
        <div className="mx-auto max-w-2xl px-4 py-20">
          <ErrorState
            title="Build unavailable"
            message="We could not load the build status for this project."
            onRetry={() => void statusQuery.refetch()}
          />
        </div>
      </AppLayout>
    )
  }

  if (projectQuery.isPending || statusQuery.isPending || !status) {
    return (
      <AppLayout>
        <LoadingState label="Checking build status…" />
      </AppLayout>
    )
  }

  const project = projectQuery.data
  const meta = statusMeta(status.status)
  const failed = status.status === 'FAILED'
  const isBuilding = !failed

  return (
    <AppLayout>
      <div className="mx-auto flex w-full max-w-3xl flex-col px-4 py-12 sm:px-6 lg:px-8">
        <div className="mb-8 flex items-center justify-between border-b border-outline-variant/40 py-2">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-1 text-sm text-on-surface-variant transition-colors hover:text-primary"
          >
            <MaterialIcon name="arrow_back" size={16} />
            Projects
            <span className="text-outline-variant">/</span>
            <span className="font-medium text-on-surface">{project.name}</span>
          </button>
          <div className="flex items-center gap-2.5">
            <StatusBadge label={meta.label} tone={meta.tone} pulse={isBuilding} />
            <span className="hidden text-xs text-on-surface-variant sm:inline">
              Updated {timeAgo(project.updatedAt)}
            </span>
          </div>
        </div>

        <div className="mb-8">
          <h1 className="mb-2 flex items-center gap-2 text-3xl font-bold tracking-tight text-on-surface drop-shadow-[0_2px_12px_rgba(71,219,207,0.15)] sm:text-[34px]">
            <span>{meta.headline}</span>
            <MaterialIcon
              name={failed ? 'error' : 'sparkles'}
              size={24}
              className={failed ? 'text-error' : 'animate-pulse text-secondary'}
            />
          </h1>
          <p className="text-base leading-relaxed text-on-surface-variant">
            {meta.description}
          </p>
        </div>

        <div className="relative flex w-full flex-col gap-6 overflow-hidden rounded-2xl border border-tertiary-container/30 bg-gradient-to-b from-surface-container to-surface-container-low p-6 shadow-high ring-1 ring-secondary/20 sm:p-8">
          <div className="gold-hairline absolute left-0 right-0 top-0 h-[2px]" />

          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/40 bg-gradient-to-br from-surface-container-highest to-surface-container text-primary shadow-glow-primary">
              <MaterialIcon name="receipt_long" size={20} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-on-surface">{project.name}</h2>
              <span className="text-xs text-on-surface-variant">
                Autonomous prototype synthesis
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-on-surface">
                {failed ? 'Build stopped' : `Build ${status.completion}% complete`}
              </span>
              <span
                className={cn(
                  'text-sm font-extrabold',
                  failed ? 'text-error' : 'text-primary',
                )}
              >
                {status.completion}%
              </span>
            </div>
            <ProgressBar value={status.completion} gradient={failed ? 'gold' : 'primary'} />
          </div>

          <div className="flex flex-col gap-2.5">
            {GENERATION_STEPS.map((step) => {
              const state = resolveStepState(status.steps, step.key)
              const visual = STEP_ICON[state]
              return (
                <div
                  key={step.key}
                  className={cn(
                    'flex items-center justify-between rounded-xl border p-3.5 transition-all',
                    state === 'RUNNING' &&
                      'border-secondary/40 bg-surface-container-lowest/80 shadow-glow-gold',
                    state === 'COMPLETED' && 'border-primary/25 bg-surface-container-lowest/70',
                    state === 'FAILED' && 'border-error/40 bg-error-container/10',
                    state === 'PENDING' &&
                      'border-outline-variant/40 bg-surface-container-lowest/40',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-outline-variant/50 bg-surface-container-lowest text-primary">
                      <MaterialIcon name={step.icon} size={18} />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-on-surface">{step.label}</p>
                      <p className="text-[11px] text-on-surface-variant">{step.description}</p>
                    </div>
                  </div>
                  <MaterialIcon
                    name={visual.icon}
                    size={20}
                    className={visual.className}
                  />
                </div>
              )
            })}
          </div>

          {failed ? (
            <div className="flex flex-col gap-3 rounded-xl border border-error/30 bg-error-container/10 p-4">
              <p className="text-sm text-on-error-container">
                {status.message ??
                  'The generation pipeline failed. You can retry the build.'}
              </p>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="secondary"
                  icon="refresh"
                  onClick={retry}
                  loading={startGeneration.isPending}
                  className="px-4 py-2 text-xs"
                >
                  Retry build
                </Button>
                <Button
                  variant="ghost"
                  icon="arrow_back"
                  onClick={() => navigate(`/projects/${project.id}/chat`)}
                  className="px-4 py-2 text-xs"
                >
                  Back to requirements
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-3 border-t border-outline-variant/30 pt-4 text-xs text-on-surface-variant">
              <div className="flex items-center justify-between">
                <span>Reserved sandbox endpoint</span>
                <span className="inline-flex items-center gap-1.5 rounded-md border border-secondary/40 bg-secondary/10 px-2.5 py-1 font-mono text-[11px] font-medium text-secondary">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary" />
                  Provisioning
                </span>
              </div>
              <span className="font-mono text-[11px] text-outline">
                /projects/{project.id}/result
              </span>
            </div>
          )}
        </div>

        {!failed && (
          <div className="mt-6 flex items-center justify-between px-1">
            <span className="flex items-center gap-1.5 text-xs text-on-surface-variant">
              <MaterialIcon name="notifications" size={15} className="text-primary" />
              You will be redirected automatically when ready
            </span>
            <Button
              variant="ghost"
              icon="arrow_back"
              onClick={() => navigate('/')}
              className="text-xs"
            >
              Back to Projects
            </Button>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
