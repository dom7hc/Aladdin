import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { MaterialIcon } from '@/components/ui/MaterialIcon'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { WizardStepper } from '@/components/ui/WizardStepper'
import { cn } from '@/lib/cn'
import { formatClockTime } from '@/lib/format'
import { useProjectQuery } from '@/hooks/useProject'
import { useArtifactsQuery, useDownloadSource } from '@/hooks/useArtifacts'
import type { Artifact, ArtifactType } from '@/types'

const ARTIFACT_META: Record<ArtifactType, { label: string; icon: string; group: string }> = {
  REQUIREMENTS_JSON: { label: 'Requirements (JSON)', icon: 'data_object', group: 'Requirements' },
  REQUIREMENTS_MD: { label: 'requirements.md', icon: 'description', group: 'Requirements' },
  ARCHITECTURE_JSON: { label: 'Architecture (JSON)', icon: 'account_tree', group: 'Architecture' },
  ARCHITECTURE_MD: { label: 'architecture.md', icon: 'architecture', group: 'Architecture' },
  REVIEW_RESULT: { label: 'Review Result', icon: 'fact_check', group: 'Review' },
  TEST_RESULT: { label: 'Test Result', icon: 'bug_report', group: 'Tests' },
}

const GROUP_ORDER = ['Requirements', 'Architecture', 'Review', 'Tests']

function artifactKey(artifact: Artifact): string {
  return `${artifact.type}-${artifact.version}`
}

function groupScore(artifacts: Artifact[], types: ArtifactType[]): 'pass' | 'pending' {
  return types.every((type) => artifacts.some((artifact) => artifact.type === type))
    ? 'pass'
    : 'pending'
}

export function ResultPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [activeArtifactKey, setActiveArtifactKey] = useState<string | null>(null)

  const projectQuery = useProjectQuery(id)
  const artifactsQuery = useArtifactsQuery(id)
  const download = useDownloadSource(id ?? '')

  const artifacts = useMemo(() => artifactsQuery.data ?? [], [artifactsQuery.data])

  const groups = useMemo(
    () =>
      GROUP_ORDER.map((group) => ({
        group,
        types: (Object.keys(ARTIFACT_META) as ArtifactType[]).filter(
          (type) => ARTIFACT_META[type].group === group,
        ),
        items: artifacts.filter((artifact) => ARTIFACT_META[artifact.type].group === group),
      })),
    [artifacts],
  )

  const activeArtifact =
    artifacts.find((artifact) => artifactKey(artifact) === activeArtifactKey) ?? artifacts[0]

  if (projectQuery.isError || artifactsQuery.isError) {
    return (
      <AppLayout>
        <div className="mx-auto max-w-2xl px-4 py-20">
          <ErrorState
            title="Result unavailable"
            message="We could not load the generated artifacts."
            onRetry={() => void artifactsQuery.refetch()}
          />
        </div>
      </AppLayout>
    )
  }

  if (projectQuery.isPending || artifactsQuery.isPending) {
    return (
      <AppLayout>
        <LoadingState label="Unrolling your PoC artifacts…" />
      </AppLayout>
    )
  }

  const project = projectQuery.data
  const sandboxUrl = `https://poc.example.com/${project.name
    .toLowerCase()
    .replace(/\s+/g, '-')}`

  return (
    <AppLayout>
      <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <div className="mb-6 flex flex-col justify-between gap-4 rounded-xl border border-outline-variant/50 bg-surface-container-low/90 p-4 shadow-high backdrop-blur-md md:flex-row md:items-center">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
                Project:
              </span>
              <span className="flex items-center gap-2 text-base font-bold text-on-surface">
                <span className="h-2 w-2 rounded-full bg-primary shadow-glow-primary" />
                {project.name}
              </span>
            </div>
            <WizardStepper current={3} />
            <StatusBadge label="Ready" tone="primary" pulse />
          </div>

          <div className="mb-8">
            <h1 className="mb-2 text-3xl font-bold tracking-tight text-gradient-magic sm:text-4xl">
              Your PoC is ready!
            </h1>
            <p className="text-base leading-relaxed text-on-surface-variant">
              Your working prototype has been generated, reviewed and tested. Inspect each
              artifact or download the project source.
            </p>
          </div>

          <div className="relative mb-8 flex w-full flex-col gap-6 overflow-hidden rounded-2xl border border-primary/20 bg-surface-container-low p-6 shadow-high sm:p-8">
            <div className="pointer-events-none absolute -right-24 -top-24 h-52 w-52 rounded-full bg-primary/10 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-24 -left-24 h-52 w-52 rounded-full bg-secondary/10 blur-3xl" />

            <div className="relative z-10 flex items-center justify-between">
              <div className="flex items-center gap-3.5">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/30 bg-primary/15 text-primary">
                  <MaterialIcon name="receipt_long" size={20} />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-on-surface">{project.name}</h2>
                  <span className="text-xs text-on-surface-variant">
                    React + FastAPI + PostgreSQL sandbox
                  </span>
                </div>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-outline-variant/60 bg-surface-container-highest/80 px-2.5 py-1 font-mono text-xs font-medium text-on-surface-variant">
                <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                v1.0 • Active Sandbox
              </span>
            </div>

            <div className="relative z-10 flex flex-col gap-2">
              <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-secondary">
                <MaterialIcon name="sparkles" size={13} />
                Live Sandbox Endpoint
              </span>
              <div className="flex flex-col items-stretch justify-between gap-3 rounded-xl border border-outline-variant/60 bg-surface-container-lowest p-2 sm:flex-row sm:items-center sm:pl-3.5">
                <div className="flex min-w-0 flex-1 items-center gap-2.5">
                  <MaterialIcon name="captive_portal" size={18} className="text-primary" />
                  <span className="truncate font-mono text-sm font-medium text-primary-fixed select-all">
                    {sandboxUrl}
                  </span>
                </div>
                <div className="flex flex-shrink-0 items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void navigator.clipboard.writeText(sandboxUrl)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant/60 bg-surface-container-high px-3 py-1.5 text-xs font-medium text-on-surface transition-all hover:bg-surface-bright"
                  >
                    <MaterialIcon name="content_copy" size={15} />
                    Copy Link
                  </button>
                  <a
                    href={sandboxUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-xs font-semibold text-on-primary shadow-glow-primary transition-all hover:bg-primary-fixed active:scale-95"
                  >
                    Open PoC
                    <MaterialIcon name="open_in_new" size={15} />
                  </a>
                </div>
              </div>
            </div>

            <div className="relative z-10 flex flex-wrap items-center gap-3 border-t border-outline-variant/40 pt-4">
              <Button
                variant="secondary"
                icon="download"
                onClick={() => download.mutate()}
                loading={download.isPending}
                className="px-4 py-2 text-xs"
              >
                Download Project
              </Button>
              <Button
                variant="ghost"
                icon="refresh"
                onClick={() => navigate(`/projects/${project.id}/generate`)}
                className="px-4 py-2 text-xs"
              >
                View build log
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="flex flex-col gap-4 lg:col-span-5">
              {groups.map(({ group, types, items }) => {
                const score = groupScore(artifacts, types)
                return (
                  <div key={group} className="glass-card p-5">
                    <div className="mb-3 flex items-center justify-between border-b border-outline-variant/40 pb-3">
                      <h3 className="text-sm font-bold text-on-surface">{group}</h3>
                      <span
                        className={cn(
                          'flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold',
                          score === 'pass'
                            ? 'border-primary/30 bg-primary/10 text-primary'
                            : 'border-secondary/30 bg-secondary/15 text-secondary',
                        )}
                      >
                        <MaterialIcon
                          name={score === 'pass' ? 'check_circle' : 'hourglass'}
                          size={13}
                        />
                        {score === 'pass' ? 'Passed' : 'Pending'}
                      </span>
                    </div>
                    <div className="flex flex-col gap-2">
                      {items.length === 0 ? (
                        <p className="text-xs italic text-on-surface-variant/80">
                          No artifact yet.
                        </p>
                      ) : (
                        items.map((artifact) => {
                          const meta = ARTIFACT_META[artifact.type]
                          const isActive =
                            activeArtifact !== undefined &&
                            artifactKey(activeArtifact) === artifactKey(artifact)
                          return (
                            <button
                              key={artifactKey(artifact)}
                              type="button"
                              onClick={() => setActiveArtifactKey(artifactKey(artifact))}
                              className={cn(
                                'flex items-center justify-between rounded-lg border px-3 py-2.5 text-left text-xs transition-all',
                                isActive
                                  ? 'border-primary/50 bg-primary/10 text-primary'
                                  : 'border-outline-variant/50 bg-surface-container-lowest text-on-surface-variant hover:border-primary/30',
                              )}
                            >
                              <span className="flex items-center gap-2">
                                <MaterialIcon name={meta.icon} size={16} />
                                {meta.label}
                              </span>
                              <span className="font-mono text-[10px] text-outline">
                                v{artifact.version}
                              </span>
                            </button>
                          )
                        })
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="lg:col-span-7">
              <div className="glass-card flex h-full min-h-[420px] flex-col p-5">
                <div className="mb-3 flex items-center justify-between border-b border-outline-variant/40 pb-3">
                  <h3 className="flex items-center gap-2 text-sm font-bold text-on-surface">
                    <MaterialIcon
                      name={activeArtifact ? ARTIFACT_META[activeArtifact.type].icon : 'draft'}
                      size={17}
                      className="text-primary"
                    />
                    {activeArtifact ? ARTIFACT_META[activeArtifact.type].label : 'Artifact Viewer'}
                  </h3>
                  {activeArtifact && (
                    <span className="font-mono text-[11px] text-outline">
                      {formatClockTime(activeArtifact.createdAt)}
                    </span>
                  )}
                </div>
                <pre className="no-scrollbar flex-1 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-outline-variant/40 bg-surface-container-lowest p-4 font-mono text-xs leading-relaxed text-on-surface-variant">
                  {activeArtifact?.content ?? 'Select an artifact to preview its contents.'}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
