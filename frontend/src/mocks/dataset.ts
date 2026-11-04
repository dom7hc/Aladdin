// Mock of backend/app/ingest/spreadsheet.py for the default demo path. Same
// limits, key rules and type inference, so a CSV that works here works there.
// The gaps: .xlsx needs a library the mock does not ship and .pdf needs Claude,
// so both are refused with a message pointing at the real backend.
import { ApiError } from '@/api/errors'
import type { DatasetColumn, DatasetColumnType, DatasetInfo } from '@/types'

const MAX_BYTES = 5 * 1024 * 1024
const MAX_ROWS = 5000
const MAX_COLUMNS = 40
const MAX_CELL_CHARS = 500
const TYPES: DatasetColumnType[] = ['integer', 'number', 'date', 'boolean']
const BOOLEANS: Record<string, boolean> = { true: true, false: false, yes: true, no: false }

export function parseMockDataset(filename: string, size: number, text: string): DatasetInfo {
  if (size > MAX_BYTES) throw new ApiError(413, 'File is larger than 5 MB.')
  const lower = filename.toLowerCase()
  if (lower.endsWith('.xlsx') || lower.endsWith('.pdf')) {
    throw new ApiError(415, 'Excel and PDF files need the real backend; in the demo, upload a CSV.')
  }
  if (!lower.endsWith('.csv')) throw new ApiError(415, 'Upload a CSV, Excel (.xlsx) or PDF file.')
  if (text.slice(0, 4096).includes('\u0000')) {
    throw new ApiError(415, 'This does not look like a CSV text file.')
  }
  if (!text.trim()) throw new ApiError(422, 'File is empty.')

  const rows = parseCsv(text.replace(/^﻿/, '')).filter((row) =>
    row.some((cell) => cell.trim() !== ''),
  )
  if (rows.length === 0) throw new ApiError(422, 'No data found in the file.')
  const width = Math.max(...rows.map((row) => row.length))
  if (width > MAX_COLUMNS) {
    throw new ApiError(422, `The file has ${width} columns; the limit is ${MAX_COLUMNS}.`)
  }
  const [header, ...allBody] = rows
  if (allBody.length === 0) throw new ApiError(422, 'The file has a header row but no data rows.')

  const labels = Array.from({ length: width }, (_, i) => header[i]?.trim().slice(0, 80) || `Column ${i + 1}`)
  const keys = uniqueKeys(labels)
  const body = allBody.slice(0, MAX_ROWS)
  const columns: DatasetColumn[] = keys.map((key, i) => ({
    key,
    label: labels[i],
    type: infer(body.map((row) => row[i] ?? '')),
  }))
  const records = body.map((row) =>
    Object.fromEntries(columns.map((column, i) => [column.key, convert(row[i] ?? '', column.type)])),
  )
  const truncated = allBody.length > MAX_ROWS
  return {
    filename,
    rowCount: allBody.length,
    usedRows: records.length,
    truncated,
    notes: truncated ? [`Only the first ${MAX_ROWS} of ${allBody.length} rows are used.`] : [],
    columns,
    // Only the preview is kept: the mock persists to localStorage.
    preview: records.slice(0, 5),
  }
}

function parseCsv(text: string): string[][] {
  const firstLine = text.split(/\r?\n/, 1)[0] ?? ''
  const delimiter = [',', ';', '\t', '|'].reduce((best, candidate) =>
    firstLine.split(candidate).length > firstLine.split(best).length ? candidate : best,
  )
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') {
        cell += '"'
        i += 1
      } else if (char === '"') {
        quoted = false
      } else {
        cell += char
      }
    } else if (char === '"') {
      quoted = true
    } else if (char === delimiter) {
      row.push(cell)
      cell = ''
    } else if (char === '\n' || char === '\r') {
      if (char === '\r' && text[i + 1] === '\n') i += 1
      row.push(cell)
      rows.push(row)
      row = []
      cell = ''
    } else {
      cell += char
    }
  }
  if (cell !== '' || row.length > 0) {
    row.push(cell)
    rows.push(row)
  }
  return rows
}

function uniqueKeys(labels: string[]): string[] {
  const keys: string[] = []
  labels.forEach((label, index) => {
    let key = label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || `column_${index + 1}`
    if (/^\d/.test(key)) key = `c_${key}`
    let candidate = key
    for (let n = 2; keys.includes(candidate); n += 1) candidate = `${key}_${n}`
    keys.push(candidate)
  })
  return keys
}

const NO = Symbol('no')

function tryConvert(raw: string, type: DatasetColumnType): unknown {
  const text = raw.trim()
  switch (type) {
    case 'integer': {
      const plain = text.replace(/,/g, '')
      return /^[-+]?\d{1,15}$/.test(plain) ? Number(plain) : NO
    }
    case 'number': {
      const plain = text.replace(/,/g, '').replace(/%$/, '')
      return plain !== '' && Number.isFinite(Number(plain)) ? Number(plain) : NO
    }
    case 'date':
      return parseDate(text) ?? NO
    case 'boolean':
      return text.toLowerCase() in BOOLEANS ? BOOLEANS[text.toLowerCase()] : NO
    default:
      return text.slice(0, MAX_CELL_CHARS)
  }
}

function parseDate(text: string): string | null {
  const iso = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/)
  const dmy = text.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/)
  const [y, m, d] = iso ? [iso[1], iso[2], iso[3]] : dmy ? [dmy[3], dmy[2], dmy[1]] : []
  if (!y) return null
  const date = new Date(Date.UTC(Number(y), Number(m) - 1, Number(d)))
  return date.getUTCMonth() === Number(m) - 1 ? date.toISOString().slice(0, 10) : null
}

function infer(values: string[]): DatasetColumnType {
  const present = values.filter((value) => value.trim() !== '')
  if (present.length === 0) return 'text'
  return TYPES.find((type) => present.every((value) => tryConvert(value, type) !== NO)) ?? 'text'
}

function convert(raw: string, type: DatasetColumnType): unknown {
  if (raw.trim() === '') return null
  const value = tryConvert(raw, type)
  return value === NO ? null : value
}
