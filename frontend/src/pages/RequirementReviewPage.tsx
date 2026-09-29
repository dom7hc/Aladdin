import { useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { MaterialIcon } from '@/components/ui/MaterialIcon'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { WizardStepper } from '@/components/ui/WizardStepper'
import { EMPTY_REQUIREMENTS } from '@/lib/requirements'
import { useProjectQuery } from '@/hooks/useProject'
import { useStartGeneration } from '@/hooks/useProjectStatus'
import { useRequirementsQuery } from '@/hooks/useRequirements'

function Card({
  icon,
  eyebrow,
  title,
  children,
  aside,
}: {
  icon: string
  eyebrow: string
  title: string
  children: React.ReactNode
  aside?: React.ReactNode
}) {
  return (
    <article className="relative overflow-hidden rounded-2xl border border-tertiary-container/25 bg-surface-container-low/85 p-6 shadow-high backdrop-blur-md transition-all hover:border-primary/40">
      <div className="absolute -right-10 -top-10 h-44 w-44 rounded-full bg-gradient-to-bl from-primary/10 via-secondary/5 to-transparent blur-3xl" />
      <div className="mb-4 flex items-center justify-between border-b border-outline-variant/40 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-primary/30 bg-surface-container-low text-primary shadow-glow-primary">
            <MaterialIcon name={icon} size={20} />
          </div>
          <div>
            <span className="text-[11px] font-bold uppercase tracking-widest text-secondary">
              {eyebrow}
            </span>
            <h2 className="text-lg font-bold text-on-surface">{title}</h2>
          </div>
        </div>
        {aside}
      </div>
      {children}
    </article>
  )
}

function ListBlock({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) {
    return <p className="text-sm italic text-on-surface-variant/80">{empty}</p>
  }
  return (
    <ul className="space-y-1.5 text-sm text-on-surface-variant">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-1.5">
          <span className="font-bold text-secondary">•</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

export function RequirementReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const projectQuery = useProjectQuery(id)
  const requirementsQuery = useRequirementsQuery(id)
  const startGeneration = useStartGeneration(id ?? '')

  const requirements = requirementsQuery.data?.requirements ?? EMPTY_REQUIREMENTS

  const architectureHint = useMemo(
    () => ({
      pages: [`${requirements.features[0] ?? 'Input'} page`, 'Results dashboard'],
      apis: ['POST /api/records', 'GET /api/records'],
    }),
    [requirements.features],
  )

  const handleBuild = () => {
    if (!id) return
    startGeneration.mutate(undefined, {
      onSuccess: () => navigate(`/projects/${id}/generate`),
    })
  }

  if (projectQuery.isError) {
    return (
      <AppLayout>
        <div className="mx-auto max-w-2xl px-4 py-20">
          <ErrorState
            title="Project not found"
            message="We could not load this project."
            onRetry={() => navigate('/')}
          />
        </div>
      </AppLayout>
    )
  }

  if (projectQuery.isPending || requirementsQuery.isPending) {
    return (
      <AppLayout>
        <LoadingState label="Loading your blueprint…" />
      </AppLayout>
    )
  }

  const project = projectQuery.data

  return (
    <AppLayout footer={false}>
      <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mx-auto w-full max-w-4xl pb-32">
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
            <WizardStepper current={1} />
            <StatusBadge label="Ready to Build" tone="secondary" pulse />
          </div>

          <header className="mb-8">
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-surface-container-low px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary">
              <MaterialIcon name="auto_awesome" size={15} filled />
              Specification Verification
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight text-on-surface sm:text-4xl">
              Review your <span className="text-gradient-primary">PoC Blueprint</span>
            </h1>
            <p className="mt-2 max-w-2xl text-base leading-relaxed text-on-surface-variant">
              Make sure everything looks right before we start building. Our AI agents will
              use this exact blueprint to construct your PoC.
            </p>
          </header>

          <div className="flex flex-col gap-6">
            <Card icon="description" eyebrow="Core Spec" title="Architectural Overview">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div className="flex flex-col justify-between rounded-lg border border-outline-variant/50 bg-surface-container-lowest p-4">
                  <div>
                    <span className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-secondary">
                      Target Application
                    </span>
                    <p className="flex items-center gap-2 text-lg font-bold text-on-surface">
                      {project.name}
                      <span className="rounded border border-primary/30 bg-primary/15 px-2 py-0.5 text-xs text-primary">
                        PoC Scope
                      </span>
                    </p>
                  </div>
                  <div className="mt-4 border-t border-outline-variant/30 pt-3">
                    <span className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-on-surface-variant">
                      Target Persona
                    </span>
                    <ListBlock
                      items={requirements.targetUsers}
                      empty="No target users captured yet."
                    />
                  </div>
                </div>
                <div className="flex flex-col gap-4">
                  <div>
                    <span className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-secondary">
                      Identified Problem
                    </span>
                    <p className="rounded-lg border border-outline-variant/50 bg-surface-container-lowest p-3 text-sm leading-relaxed text-on-surface">
                      {requirements.problem || 'No problem statement captured yet.'}
                    </p>
                  </div>
                  <div>
                    <span className="mb-1 block text-[11px] font-bold uppercase tracking-wider text-primary">
                      Target Outcome
                    </span>
                    <div className="flex items-start gap-2.5 rounded-lg border border-primary/30 bg-gradient-to-r from-surface-container-low to-surface-container p-3 text-sm text-on-surface shadow-glow-primary">
                      <MaterialIcon name="verified" size={20} filled className="mt-0.5 text-primary" />
                      <span>{requirements.successCriteria[0] ?? 'Define success criteria in chat.'}</span>
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            <Card
              icon="checklist_rtl"
              eyebrow="Functional Capabilities"
              title="Validated Scope Matrix"
              aside={
                <span className="rounded-full border border-primary/30 bg-surface-container-low px-3 py-1 text-xs font-semibold text-primary">
                  {requirements.features.length} Capabilities Defined
                </span>
              }
            >
              {requirements.features.length === 0 ? (
                <p className="text-sm italic text-on-surface-variant/80">
                  No features captured yet.
                </p>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {requirements.features.map((feature) => (
                    <div
                      key={feature}
                      className="flex items-start gap-3 rounded-lg border border-outline-variant/50 bg-surface-container-lowest p-4 transition-colors hover:border-primary/30"
                    >
                      <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border border-primary/40 bg-primary/15 text-primary shadow-glow-primary">
                        <MaterialIcon name="check" size={15} className="font-bold" />
                      </div>
                      <p className="text-sm font-medium text-on-surface">{feature}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card icon="sync_alt" eyebrow="I/O Specification" title="Data Contracts & Acceptance Criteria">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div className="flex flex-col justify-between rounded-lg border border-outline-variant/50 bg-surface-container-lowest p-4">
                  <div>
                    <div className="mb-2 flex items-center gap-1.5 text-secondary">
                      <MaterialIcon name="file_open" size={17} />
                      <span className="text-[11px] font-bold uppercase tracking-wider">
                        System Inputs
                      </span>
                    </div>
                    <ListBlock items={requirements.inputs} empty="No inputs captured yet." />
                  </div>
                </div>
                <div className="flex flex-col justify-between rounded-lg border border-outline-variant/50 bg-surface-container-lowest p-4">
                  <div>
                    <div className="mb-2 flex items-center gap-1.5 text-secondary">
                      <MaterialIcon name="output" size={17} />
                      <span className="text-[11px] font-bold uppercase tracking-wider">
                        System Outputs
                      </span>
                    </div>
                    <ListBlock items={requirements.outputs} empty="No outputs captured yet." />
                  </div>
                </div>
                <div className="flex flex-col justify-between rounded-lg border border-primary/30 bg-gradient-to-b from-surface-container-low to-surface-container-lowest p-4 shadow-glow-primary">
                  <div>
                    <div className="mb-2 flex items-center gap-1.5 text-primary">
                      <MaterialIcon name="timer" size={17} filled />
                      <span className="text-[11px] font-bold uppercase tracking-wider">
                        Success Criteria
                      </span>
                    </div>
                    <ListBlock
                      items={requirements.successCriteria}
                      empty="No success criteria captured yet."
                    />
                  </div>
                </div>
              </div>
            </Card>

            <Card icon="smart_toy" eyebrow="Architecture Hint" title="Planned Pages & APIs">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-lg border border-outline-variant/50 bg-surface-container-lowest p-4">
                  <span className="mb-2 block text-[11px] font-bold uppercase tracking-wider text-secondary">
                    Pages
                  </span>
                  <ListBlock items={architectureHint.pages} empty="—" />
                </div>
                <div className="rounded-lg border border-outline-variant/50 bg-surface-container-lowest p-4">
                  <span className="mb-2 block text-[11px] font-bold uppercase tracking-wider text-secondary">
                    APIs
                  </span>
                  <ListBlock items={architectureHint.apis} empty="—" />
                </div>
              </div>
            </Card>
          </div>
        </section>

        <aside className="fixed bottom-0 left-0 right-0 z-40 border-t border-outline-variant/50 bg-surface-container-lowest/90 px-4 py-3 shadow-high backdrop-blur-xl">
          <div className="mx-auto flex max-w-4xl items-center justify-between gap-4">
            <Button
              variant="secondary"
              icon="arrow_back"
              onClick={() => navigate(`/projects/${project.id}/chat`)}
            >
              Back to Chat
            </Button>
            <div className="flex items-center gap-4">
              <span className="hidden items-center gap-1.5 text-xs text-on-surface-variant sm:flex">
                <MaterialIcon name="auto_awesome" size={15} filled className="text-secondary" />
                No engineering needed
              </span>
              <button
                type="button"
                onClick={handleBuild}
                disabled={startGeneration.isPending}
                className="group relative inline-flex items-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-[#f59e0b] via-[#ffca45] to-[#d97706] px-6 py-3 text-sm font-extrabold text-[#251a00] shadow-glow-gold transition-all hover:brightness-105 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-70 sm:text-base"
              >
                <span className="relative z-10 flex items-center gap-2">
                  <span>
                    {startGeneration.isPending
                      ? 'Conjuring Alladin Agents…'
                      : 'Confirm & Build PoC'}
                  </span>
                  <MaterialIcon
                    name={startGeneration.isPending ? 'progress_activity' : 'bolt'}
                    size={20}
                    filled
                    className={startGeneration.isPending ? 'animate-spin' : 'group-hover:rotate-12'}
                  />
                </span>
              </button>
            </div>
          </div>
        </aside>
      </div>
    </AppLayout>
  )
}
