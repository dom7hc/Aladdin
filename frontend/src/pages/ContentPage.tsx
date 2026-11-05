import { useState } from 'react'

import { getAdminKey, setAdminKey } from '@/api/contentApi'
import { ApiError } from '@/api/errors'
import { AppLayout } from '@/components/layout/AppLayout'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { MaterialIcon } from '@/components/ui/MaterialIcon'
import {
  useAllScenarios,
  useCreateScenario,
  useDeleteScenario,
  useHomeContent,
  useReorderScenarios,
  useResetHomeContent,
  useResetScenarios,
  useSaveHomeContent,
  useUpdateScenario,
} from '@/hooks/useContent'
import { cn } from '@/lib/cn'
import { HOME_DEFAULTS } from '@/mocks/seedContent'
import type { HomeContent, Scenario, ScenarioInput, ScenarioLayout } from '@/types'

const LAYOUTS: { value: ScenarioLayout; label: string; hint: string }[] = [
  { value: 'kpi-overview', label: 'Headline KPIs', hint: 'A few numbers and how they move over time' },
  {
    value: 'analytics-breakdown',
    label: 'Trend and breakdown',
    hint: 'A trend compared across categories',
  },
  { value: 'records-workspace', label: 'Records with filters', hint: 'Browse and filter a list' },
]

const LABEL = 'mb-1.5 block text-xs font-semibold uppercase tracking-wider text-on-surface-variant'
const INPUT = 'input-field py-2.5 text-sm'

/** Turns an API failure into a sentence an editor can act on. */
function problem(error: unknown): string | null {
  if (!error) return null
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return `${error.message} Enter the admin key at the top of the page.`
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

function AdminKeyBar() {
  const [value, setValue] = useState(getAdminKey)
  const [saved, setSaved] = useState(Boolean(getAdminKey()))
  return (
    <div className="glass-card flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
      <div className="flex items-center gap-2 text-sm text-on-surface">
        <MaterialIcon name="key" size={18} className="text-secondary" />
        <span className="font-semibold">Admin key</span>
      </div>
      <input
        type="password"
        value={value}
        onChange={(event) => {
          setValue(event.target.value)
          setSaved(false)
        }}
        placeholder="Needed to save changes; remembered in this browser"
        className={cn(INPUT, 'sm:max-w-sm')}
        aria-label="Admin key"
      />
      <Button
        variant="secondary"
        className="px-4 py-2 text-xs"
        onClick={() => {
          setAdminKey(value.trim())
          setSaved(true)
        }}
      >
        {saved ? 'Saved' : 'Use this key'}
      </Button>
      <p className="text-xs text-on-surface-variant sm:ml-auto">
        Anyone can read this page; only the key can change it.
      </p>
    </div>
  )
}

const EMPTY: ScenarioInput = {
  title: '',
  audience: '',
  problem: '',
  layout: 'kpi-overview',
  highlights: [],
  prompt: '',
  enabled: true,
}

function ScenarioEditor({
  initial,
  saving,
  error,
  onSave,
  onCancel,
}: {
  initial: ScenarioInput
  saving: boolean
  error: string | null
  onSave: (input: ScenarioInput) => void
  onCancel: () => void
}) {
  const [draft, setDraft] = useState(initial)
  const [highlights, setHighlights] = useState(initial.highlights.join('\n'))
  const set = <K extends keyof ScenarioInput>(key: K, value: ScenarioInput[K]) =>
    setDraft((d) => ({ ...d, [key]: value }))
  const complete = ['title', 'audience', 'problem', 'prompt'].every((k) =>
    String(draft[k as keyof ScenarioInput]).trim(),
  )

  return (
    <form
      className="glass-card flex flex-col gap-4 border-primary/40 p-5"
      onSubmit={(event) => {
        event.preventDefault()
        onSave({
          ...draft,
          highlights: highlights
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean),
        })
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <label>
          <span className={LABEL}>Business case</span>
          <input
            className={INPUT}
            value={draft.title}
            maxLength={120}
            onChange={(e) => set('title', e.target.value)}
            placeholder="e.g. Plant OEE watch"
            required
          />
        </label>
        <label>
          <span className={LABEL}>Target users</span>
          <input
            className={INPUT}
            value={draft.audience}
            maxLength={120}
            onChange={(e) => set('audience', e.target.value)}
            placeholder="e.g. Plant manager or shift lead"
            required
          />
        </label>
      </div>
      <label>
        <span className={LABEL}>Their problem today</span>
        <textarea
          className={cn(INPUT, 'resize-y')}
          rows={2}
          value={draft.problem}
          maxLength={600}
          onChange={(e) => set('problem', e.target.value)}
          placeholder="What is hard for them now, in their words"
          required
        />
      </label>
      <div className="grid gap-4 md:grid-cols-2">
        <label>
          <span className={LABEL}>What the dashboard shows · one per line</span>
          <textarea
            className={cn(INPUT, 'resize-y')}
            rows={4}
            value={highlights}
            onChange={(e) => setHighlights(e.target.value)}
            placeholder={'OEE per line, every shift\nTop downtime reasons'}
          />
        </label>
        <fieldset>
          <legend className={LABEL}>Layout</legend>
          <div className="flex flex-col gap-2">
            {LAYOUTS.map((layout) => (
              <label
                key={layout.value}
                className={cn(
                  'flex cursor-pointer items-start gap-2 rounded-xl border px-3 py-2 text-sm transition-colors',
                  draft.layout === layout.value
                    ? 'border-primary/60 bg-primary/10 text-on-surface'
                    : 'border-outline-variant/50 text-on-surface-variant hover:border-primary/40',
                )}
              >
                <input
                  type="radio"
                  name="layout"
                  className="mt-1 accent-[#47dbcf]"
                  checked={draft.layout === layout.value}
                  onChange={() => set('layout', layout.value)}
                />
                <span>
                  <span className="font-semibold">{layout.label}</span>
                  <span className="block text-xs text-on-surface-variant">{layout.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      </div>
      <label>
        <span className={LABEL}>Starting message · filled in when a user picks this case</span>
        <textarea
          className={cn(INPUT, 'resize-y')}
          rows={3}
          value={draft.prompt}
          maxLength={1200}
          onChange={(e) => set('prompt', e.target.value)}
          placeholder="An OEE dashboard for plant managers: availability, performance and quality per line…"
          required
        />
      </label>
      <label className="flex items-center gap-2 text-sm text-on-surface">
        <input
          type="checkbox"
          className="h-4 w-4 accent-[#47dbcf]"
          checked={draft.enabled}
          onChange={(e) => set('enabled', e.target.checked)}
        />
        Show on the home page
      </label>
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" icon="check" loading={saving} disabled={!complete}>
          Save
        </Button>
      </div>
    </form>
  )
}

function ScenarioRow({
  scenario,
  first,
  last,
  busy,
  onEdit,
  onMove,
  onToggle,
  onDelete,
}: {
  scenario: Scenario
  first: boolean
  last: boolean
  busy: boolean
  onEdit: () => void
  onMove: (delta: -1 | 1) => void
  onToggle: () => void
  onDelete: () => void
}) {
  const layout = LAYOUTS.find((l) => l.value === scenario.layout)?.label ?? scenario.layout
  return (
    <li
      className={cn(
        'glass-card flex flex-col gap-3 p-4 sm:flex-row sm:items-center',
        !scenario.enabled && 'opacity-60',
      )}
    >
      <div className="flex flex-col gap-1 sm:pr-2">
        <button
          type="button"
          className="btn-ghost p-1"
          disabled={first || busy}
          onClick={() => onMove(-1)}
          aria-label={`Move ${scenario.title} up`}
        >
          <MaterialIcon name="keyboard_arrow_up" size={18} />
        </button>
        <button
          type="button"
          className="btn-ghost p-1"
          disabled={last || busy}
          onClick={() => onMove(1)}
          aria-label={`Move ${scenario.title} down`}
        >
          <MaterialIcon name="keyboard_arrow_down" size={18} />
        </button>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-on-surface">{scenario.title}</span>
          <span className="inline-flex items-center gap-1 rounded-full bg-surface-container-high px-2 py-0.5 text-[11px] text-secondary-fixed">
            <MaterialIcon name="group" size={13} />
            {scenario.audience}
          </span>
          <span className="rounded-full border border-outline-variant/50 px-2 py-0.5 text-[11px] text-on-surface-variant">
            {layout}
          </span>
          {!scenario.enabled && (
            <span className="rounded-full border border-outline-variant/50 px-2 py-0.5 text-[11px] text-outline">
              Hidden
            </span>
          )}
          {!scenario.builtin && (
            <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[11px] text-primary">
              Added
            </span>
          )}
        </div>
        <p className="mt-1 line-clamp-2 text-sm text-on-surface-variant">{scenario.problem}</p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          className="btn-ghost p-2"
          disabled={busy}
          onClick={onToggle}
          title={scenario.enabled ? 'Hide from the home page' : 'Show on the home page'}
          aria-label={scenario.enabled ? `Hide ${scenario.title}` : `Show ${scenario.title}`}
        >
          <MaterialIcon name={scenario.enabled ? 'visibility' : 'visibility_off'} size={18} />
        </button>
        <button
          type="button"
          className="btn-ghost p-2"
          onClick={onEdit}
          aria-label={`Edit ${scenario.title}`}
        >
          <MaterialIcon name="edit" size={18} />
        </button>
        <button
          type="button"
          className="btn-ghost p-2 hover:text-error"
          disabled={busy}
          onClick={onDelete}
          aria-label={`Delete ${scenario.title}`}
        >
          <MaterialIcon name="delete" size={18} />
        </button>
      </div>
    </li>
  )
}

function inputOf(scenario: Scenario): ScenarioInput {
  const { title, audience, problem: text, layout, highlights, prompt, enabled } = scenario
  return { title, audience, problem: text, layout, highlights, prompt, enabled }
}

function ScenariosTab() {
  const query = useAllScenarios()
  const create = useCreateScenario()
  const update = useUpdateScenario()
  const remove = useDeleteScenario()
  const reorder = useReorderScenarios()
  const reset = useResetScenarios()
  // null: no editor open; 'new': adding; otherwise the id being edited.
  const [editing, setEditing] = useState<string | null>(null)

  const list = query.data ?? []
  const busy = update.isPending || remove.isPending || reorder.isPending || reset.isPending
  const listError = problem(update.error ?? remove.error ?? reorder.error ?? reset.error)

  if (query.isError) {
    return (
      <ErrorState
        title="Could not load the business cases"
        message={problem(query.error) ?? ''}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const move = (index: number, delta: -1 | 1) => {
    const ids = list.map((s) => s.id)
    const [moved] = ids.splice(index, 1)
    ids.splice(index + delta, 0, moved)
    reorder.mutate(ids)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-on-surface-variant">
          {list.filter((s) => s.enabled).length} of {list.length} shown on the home page, in this
          order. The requirement chat also steers users toward them.
        </p>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            className="text-xs"
            icon="restart_alt"
            loading={reset.isPending}
            onClick={() => {
              if (window.confirm('Restore the 20 built-in cases? Added and edited cases are lost.')) {
                reset.mutate()
              }
            }}
          >
            Restore built-ins
          </Button>
          <Button
            className="px-4 py-2 text-xs"
            icon="add"
            disabled={editing === 'new'}
            onClick={() => {
              create.reset()
              setEditing('new')
            }}
          >
            Add business case
          </Button>
        </div>
      </div>

      {listError && (
        <p role="alert" className="text-sm text-error">
          {listError}
        </p>
      )}

      {editing === 'new' && (
        <ScenarioEditor
          initial={EMPTY}
          saving={create.isPending}
          error={problem(create.error)}
          onCancel={() => setEditing(null)}
          onSave={(input) => create.mutate(input, { onSuccess: () => setEditing(null) })}
        />
      )}

      {query.isPending ? (
        <div className="h-40 animate-pulse rounded-2xl bg-surface-container-low/60" />
      ) : list.length === 0 ? (
        <div className="glass-card p-8 text-center text-sm text-on-surface-variant">
          No business cases yet. Add one, or restore the built-in set.
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {list.map((scenario, index) =>
            editing === scenario.id ? (
              <li key={scenario.id}>
                <ScenarioEditor
                  initial={inputOf(scenario)}
                  saving={update.isPending}
                  error={problem(update.error)}
                  onCancel={() => setEditing(null)}
                  onSave={(input) =>
                    update.mutate(
                      { id: scenario.id, input },
                      { onSuccess: () => setEditing(null) },
                    )
                  }
                />
              </li>
            ) : (
              <ScenarioRow
                key={scenario.id}
                scenario={scenario}
                first={index === 0}
                last={index === list.length - 1}
                busy={busy}
                onEdit={() => {
                  update.reset()
                  setEditing(scenario.id)
                }}
                onMove={(delta) => move(index, delta)}
                onToggle={() =>
                  update.mutate({
                    id: scenario.id,
                    input: { ...inputOf(scenario), enabled: !scenario.enabled },
                  })
                }
                onDelete={() => {
                  if (window.confirm(`Delete "${scenario.title}"?`)) remove.mutate(scenario.id)
                }}
              />
            ),
          )}
        </ul>
      )}
    </div>
  )
}

const HOME_FIELDS: { key: keyof HomeContent; label: string; long?: boolean }[] = [
  { key: 'badge', label: 'Badge above the title' },
  { key: 'title', label: 'Title' },
  { key: 'titleHighlight', label: 'Title, highlighted part' },
  { key: 'subtitle', label: 'Subtitle', long: true },
  { key: 'placeholder', label: 'Idea box placeholder' },
  { key: 'scenariosLabel', label: 'Label above the business cases' },
  { key: 'projectsTitle', label: 'Projects heading' },
  { key: 'projectsSubtitle', label: 'Projects subheading' },
]

function HomeTab() {
  const query = useHomeContent()
  // The form starts from the stored texts, so it mounts once they are here
  // (the query shows the defaults as placeholder data until then).
  if (query.isPlaceholderData || !query.data) {
    return <div className="h-96 animate-pulse rounded-2xl bg-surface-container-low/60" />
  }
  return <HomeForm initial={query.data} />
}

function HomeForm({ initial }: { initial: HomeContent }) {
  const save = useSaveHomeContent()
  const reset = useResetHomeContent()
  const [draft, setDraft] = useState<HomeContent>(initial)

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_minmax(0,420px)]">
      <form
        className="glass-card flex flex-col gap-4 p-5"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(draft)
        }}
      >
        {HOME_FIELDS.map((field) => (
          <label key={field.key}>
            <span className={LABEL}>{field.label}</span>
            {field.long ? (
              <textarea
                className={cn(INPUT, 'resize-y')}
                rows={2}
                value={draft[field.key]}
                placeholder={HOME_DEFAULTS[field.key]}
                onChange={(e) => setDraft((d) => ({ ...d, [field.key]: e.target.value }))}
              />
            ) : (
              <input
                className={INPUT}
                value={draft[field.key]}
                placeholder={HOME_DEFAULTS[field.key]}
                onChange={(e) => setDraft((d) => ({ ...d, [field.key]: e.target.value }))}
              />
            )}
          </label>
        ))}
        <p className="text-xs text-on-surface-variant">Leave a field empty to use its default.</p>
        {(save.error || reset.error) && (
          <p role="alert" className="text-sm text-error">
            {problem(save.error ?? reset.error)}
          </p>
        )}
        {save.isSuccess && !save.isPending && (
          <p className="text-sm text-primary">Saved. The home page shows it now.</p>
        )}
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            icon="restart_alt"
            loading={reset.isPending}
            onClick={() => {
              if (window.confirm('Put every home page text back to its default?')) {
                reset.mutate(undefined, { onSuccess: (defaults) => setDraft(defaults) })
              }
            }}
          >
            Reset to defaults
          </Button>
          <Button type="submit" icon="check" loading={save.isPending}>
            Save
          </Button>
        </div>
      </form>

      <div className="flex flex-col gap-2">
        <span className={LABEL}>Preview</span>
        <div className="glass-card flex flex-col items-center gap-3 p-6 text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-secondary/30 bg-surface-container-high/80 px-3 py-1 text-[11px] text-secondary">
            <MaterialIcon name="stars" size={13} />
            {draft.badge || HOME_DEFAULTS.badge}
          </span>
          <p className="text-2xl font-extrabold tracking-tight text-on-surface">
            {draft.title || HOME_DEFAULTS.title}{' '}
            <span className="text-gradient-primary">
              {draft.titleHighlight || HOME_DEFAULTS.titleHighlight}
            </span>
          </p>
          <p className="text-sm text-on-surface-variant">
            {draft.subtitle || HOME_DEFAULTS.subtitle}
          </p>
          <div className="w-full rounded-xl border border-outline-variant/50 px-3 py-4 text-left text-xs text-outline">
            {draft.placeholder || HOME_DEFAULTS.placeholder}
          </div>
          <p className="text-[10px] uppercase tracking-wider text-on-surface-variant/80">
            {draft.scenariosLabel || HOME_DEFAULTS.scenariosLabel}
          </p>
        </div>
      </div>
    </div>
  )
}

type Tab = 'cases' | 'home'

/** Edit the business cases and the home page texts, stored in the database. */
export function ContentPage() {
  const [tab, setTab] = useState<Tab>('cases')
  return (
    <AppLayout>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-10 sm:px-6 lg:px-8">
        <div>
          <h1 className="text-headline-lg tracking-tight text-on-surface">Site content</h1>
          <p className="text-body-sm text-on-surface-variant">
            The business cases users start from, and the words on the home page. Changes show
            immediately, without a redeploy.
          </p>
        </div>

        <AdminKeyBar />

        <div role="tablist" className="flex gap-1 border-b border-outline-variant/40">
          {(
            [
              ['cases', 'Business cases', 'cases'],
              ['home', 'Home page', 'home'],
            ] as const
          ).map(([value, label, icon]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => setTab(value)}
              className={cn(
                '-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors',
                tab === value
                  ? 'border-primary text-primary'
                  : 'border-transparent text-on-surface-variant hover:text-on-surface',
              )}
            >
              <MaterialIcon name={icon === 'cases' ? 'work' : 'home'} size={18} />
              {label}
            </button>
          ))}
        </div>

        {tab === 'cases' ? <ScenariosTab /> : <HomeTab />}
      </div>
    </AppLayout>
  )
}
