import { useRef } from 'react'

import { Button } from '@/components/ui/Button'
import { MaterialIcon } from '@/components/ui/MaterialIcon'
import { useDatasetQuery, useDeleteDataset, useUploadDataset } from '@/hooks/useDataset'
import type { DatasetColumnType, DatasetInfo } from '@/types'

const TYPE_ICON: Record<DatasetColumnType, string> = {
  integer: 'tag',
  number: 'calculate',
  date: 'calendar_month',
  boolean: 'toggle_on',
  text: 'notes',
}

/**
 * The user's own CSV/Excel file. Shows back what was detected — every column
 * with its type — so a wrong file is obvious before anything is generated.
 */
export function DataSourcePanel({ projectId }: { projectId: string }) {
  const input = useRef<HTMLInputElement>(null)
  const datasetQuery = useDatasetQuery(projectId)
  const upload = useUploadDataset(projectId)
  const remove = useDeleteDataset(projectId)
  const dataset = datasetQuery.data ?? null

  const pick = () => input.current?.click()
  const onFile = (file: File | undefined) => {
    if (file) upload.mutate(file)
    if (input.current) input.current.value = ''
  }

  return (
    <div className="glass-card flex flex-col gap-3 p-5 sm:p-6">
      <div className="flex items-center justify-between border-b border-outline-variant/40 pb-2">
        <span className="text-base font-bold tracking-wide text-on-surface">Your data</span>
        <span className="text-[11px] text-outline">CSV, Excel or PDF · up to 5 MB</span>
      </div>

      <input
        ref={input}
        type="file"
        accept=".csv,.xlsx,.pdf,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className="hidden"
        onChange={(event) => onFile(event.target.files?.[0])}
      />

      {dataset ? (
        <>
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <MaterialIcon name="table_view" size={18} className="text-primary" />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-on-surface">{dataset.filename}</p>
                <p className="text-xs text-on-surface-variant">
                  {dataset.usedRows.toLocaleString()} rows · {dataset.columns.length} columns
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              icon="delete"
              className="px-2 py-1 text-xs"
              loading={remove.isPending}
              onClick={() => remove.mutate()}
              aria-label="Remove file"
            />
          </div>
          <ul className="flex flex-wrap gap-1.5">
            {dataset.columns.map((column) => (
              <li
                key={column.key}
                title={`${column.label} — ${column.type}`}
                className="flex items-center gap-1 rounded-full border border-outline-variant/60 bg-surface-container-lowest px-2 py-0.5 text-[11px] text-on-surface"
              >
                <MaterialIcon name={TYPE_ICON[column.type]} size={13} className="text-outline" />
                {column.label}
              </li>
            ))}
          </ul>
          {dataset.notes.map((note) => (
            <p key={note} className="text-xs text-secondary">
              {note}
            </p>
          ))}
          <PreviewRows dataset={dataset} />
          <p className="text-xs leading-relaxed text-on-surface-variant">
            The dashboard will be built on these columns and rows.
          </p>
          <Button variant="secondary" icon="upload_file" className="text-xs" onClick={pick} loading={upload.isPending}>
            Replace file
          </Button>
        </>
      ) : (
        <>
          <p className="text-xs leading-relaxed text-on-surface-variant">
            Upload a spreadsheet or a PDF report and the dashboard is built on your real numbers
            instead of sample data.
          </p>
          <Button
            variant="secondary"
            icon="upload_file"
            className="text-xs"
            onClick={pick}
            loading={upload.isPending || datasetQuery.isPending}
          >
            Upload a file
          </Button>
        </>
      )}

      {upload.isError && (
        <p className="text-xs text-error">{(upload.error as Error).message}</p>
      )}
      {remove.isError && <p className="text-xs text-error">Could not remove the file.</p>}
    </div>
  )
}

/** The first rows as read, so the user can confirm them, a PDF's above all. */
function PreviewRows({ dataset }: { dataset: DatasetInfo }) {
  const rows = dataset.preview.slice(0, 3)
  if (rows.length === 0) return null
  return (
    <div className="overflow-x-auto rounded-lg border border-outline-variant/50">
      <table className="w-full text-left text-[11px]">
        <thead className="bg-surface-container text-outline">
          <tr>
            {dataset.columns.map((column) => (
              <th key={column.key} className="whitespace-nowrap px-2 py-1 font-semibold">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-t border-outline-variant/40 text-on-surface">
              {dataset.columns.map((column) => (
                <td key={column.key} className="whitespace-nowrap px-2 py-1">
                  {formatCell(row[column.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  return String(value)
}
