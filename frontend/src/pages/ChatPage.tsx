import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { RequirementSummaryPanel } from '@/components/requirements/RequirementSummaryPanel'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { MaterialIcon } from '@/components/ui/MaterialIcon'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { WizardStepper } from '@/components/ui/WizardStepper'
import { EMPTY_REQUIREMENTS } from '@/lib/requirements'
import { formatClockTime } from '@/lib/format'
import { statusMeta } from '@/lib/status'
import { useProjectQuery } from '@/hooks/useProject'
import {
  useChatMessagesQuery,
  useFinalizeRequirements,
  useRequirementsQuery,
  useSendMessage,
} from '@/hooks/useRequirements'
import type { RequirementData } from '@/types'

const AUTOFILL_MESSAGE =
  "Let's export the results to CSV and show a searchable web dashboard. Success means reducing manual review time by 75%."

export function ChatPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [draft, setDraft] = useState('')
  const threadRef = useRef<HTMLDivElement>(null)

  const projectQuery = useProjectQuery(id)
  const messagesQuery = useChatMessagesQuery(id)
  const requirementsQuery = useRequirementsQuery(id)
  const sendMessage = useSendMessage(id ?? '')
  const finalize = useFinalizeRequirements(id ?? '')

  const messages = messagesQuery.data ?? []
  const requirements: RequirementData =
    requirementsQuery.data?.requirements ?? EMPTY_REQUIREMENTS
  const completion = requirementsQuery.data?.completion ?? 0
  const ready =
    requirementsQuery.data !== undefined &&
    requirementsQuery.data.missingFields.length === 0

  useEffect(() => {
    const node = threadRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages.length, sendMessage.isPending])

  const status = useMemo(() => {
    if (ready) return statusMeta('REQUIREMENT_READY')
    return statusMeta('REQUIREMENT_COLLECTION')
  }, [ready])

  const send = () => {
    const message = draft.trim()
    if (!message || sendMessage.isPending) return
    setDraft('')
    sendMessage.mutate(message)
  }

  const handleReview = () => {
    if (!id) return
    finalize.mutate(undefined, {
      onSuccess: () => navigate(`/projects/${id}/review`),
    })
  }

  if (projectQuery.isError || messagesQuery.isError) {
    return (
      <AppLayout>
        <div className="mx-auto max-w-2xl px-4 py-20">
          <ErrorState
            title="Project not found"
            message="We could not load this project. It may have been removed."
            onRetry={() => navigate('/')}
          />
        </div>
      </AppLayout>
    )
  }

  if (projectQuery.isPending || messagesQuery.isPending) {
    return (
      <AppLayout>
        <LoadingState label="Summoning Alladin…" />
      </AppLayout>
    )
  }

  const project = projectQuery.data

  return (
    <AppLayout>
      <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-col gap-4 rounded-2xl border border-outline-variant/50 bg-surface-container-low/90 p-4 shadow-high backdrop-blur-md sm:p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-3 sm:gap-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-secondary/30 bg-gradient-to-br from-surface-container to-surface-container-high text-secondary shadow-glow-gold">
                <MaterialIcon name="magic_button" size={20} />
              </div>
              <span className="text-lg font-bold tracking-wide text-on-surface">
                {project.name}
              </span>
            </div>
            <StatusBadge label={status.label.toUpperCase()} tone={status.tone} pulse />
          </div>
          <WizardStepper current={0} />
        </div>

        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
          <div className="flex flex-col gap-4 lg:col-span-7 xl:col-span-8">
            <div className="glass-card relative flex min-h-[580px] max-h-[720px] flex-col overflow-hidden p-4 sm:p-6">
              <div
                ref={threadRef}
                className="no-scrollbar flex-1 space-y-5 overflow-y-auto pr-2"
              >
                {messages.map((message) =>
                  message.role === 'assistant' ? (
                    <AssistantMessage
                      key={message.id}
                      content={message.content}
                      time={formatClockTime(message.createdAt)}
                    />
                  ) : (
                    <UserMessage
                      key={message.id}
                      content={message.content}
                      time={formatClockTime(message.createdAt)}
                    />
                  ),
                )}
                {sendMessage.isPending && <TypingIndicator />}
              </div>

              <div className="mt-4 pt-2">
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    send()
                  }}
                  className="flex flex-col rounded-2xl border border-outline-variant/60 bg-surface-container-lowest p-3 shadow-high transition-all focus-within:border-primary/70 focus-within:ring-2 focus-within:ring-primary/20"
                >
                  <textarea
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault()
                        send()
                      }
                    }}
                    rows={2}
                    disabled={sendMessage.isPending}
                    placeholder="Tell Alladin your specs or answer the questions…"
                    className="w-full resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed text-on-surface outline-none placeholder:text-outline disabled:opacity-60"
                  />
                  <div className="mt-1 flex items-center justify-end border-t border-outline-variant/40 pt-2">
                    <div className="flex items-center gap-2">
                      <span className="hidden text-[11px] text-outline md:inline">
                        Press ↵
                      </span>
                      <Button
                        type="submit"
                        loading={sendMessage.isPending}
                        disabled={!draft.trim()}
                        trailingIcon={sendMessage.isPending ? undefined : 'arrow_upward'}
                        className="px-4 py-2 text-xs"
                      >
                        Send
                      </Button>
                    </div>
                  </div>
                </form>
              </div>
            </div>

            {sendMessage.isError && (
              <p className="text-sm text-error">
                Alladin could not respond. Please resend your message.
              </p>
            )}
          </div>

          <div className="flex flex-col gap-4 lg:sticky lg:top-20 lg:col-span-5 xl:col-span-4">
            <RequirementSummaryPanel
              projectName={project.name}
              requirements={requirements}
              completion={completion}
              onReview={handleReview}
              onAutofill={() => setDraft(AUTOFILL_MESSAGE)}
              finalizing={finalize.isPending}
            />
            {finalize.isError && (
              <p className="text-sm text-error">
                Could not finalize requirements. Ensure all required fields are filled.
              </p>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  )
}

function AssistantMessage({ content, time }: { content: string; time: string }) {
  return (
    <div className="flex max-w-2xl items-start gap-3">
      <div className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl border border-primary-fixed/40 bg-gradient-to-tr from-[#00504a] via-[#0dbeb2] to-[#6af8eb] text-[#00201d] shadow-glow-primary">
        <MaterialIcon name="auto_fix_high" size={19} className="font-bold" />
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-xs font-bold tracking-wide text-primary">
            Alladin <span className="text-secondary">✦</span>
          </span>
          <span className="text-[11px] text-outline">{time}</span>
        </div>
        <div className="rounded-2xl rounded-tl-sm border border-outline-variant/60 bg-surface-container-lowest p-4 text-sm leading-relaxed text-on-surface shadow-low">
          {content}
        </div>
      </div>
    </div>
  )
}

function UserMessage({ content, time }: { content: string; time: string }) {
  return (
    <div className="ml-auto flex max-w-2xl items-start justify-end gap-3">
      <div className="flex flex-col items-end gap-1.5">
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-outline">{time}</span>
          <span className="text-xs font-semibold text-tertiary">You</span>
        </div>
        <div className="rounded-2xl rounded-tr-sm border border-tertiary/30 bg-gradient-to-br from-[#3f008e] via-[#5a00c6] to-[#25005a] p-4 text-sm leading-relaxed text-white shadow-glow-violet">
          {content}
        </div>
      </div>
      <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-tr from-secondary to-tertiary-container text-[#251a00] ring-1 ring-secondary/40">
        <MaterialIcon name="person" filled size={16} />
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex max-w-md items-center gap-3 rounded-xl border border-primary/30 bg-surface-container-lowest/80 px-4 py-2.5 shadow-glow-primary">
      <div className="flex items-center gap-1.5">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="h-2 w-2 animate-bounce rounded-full"
            style={{
              backgroundColor: ['#47dbcf', '#ffca45', '#ba98ff'][index],
              animationDelay: `${index * 0.15}s`,
            }}
          />
        ))}
      </div>
      <span className="text-xs font-medium italic text-on-surface-variant">
        Alladin is weaving requirements into PoC schema…
      </span>
    </div>
  )
}
