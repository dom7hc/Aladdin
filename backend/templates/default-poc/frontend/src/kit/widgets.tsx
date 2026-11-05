// Non-chart widgets, plus the theme switcher.

import type { CSSProperties, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { Sparkline, formatNumber } from "./charts";
import { Icon } from "./icons";

export function Card({
  title,
  note,
  children,
}: {
  title?: string;
  note?: string;
  children: ReactNode;
}) {
  return (
    <section className="card">
      {title ? (
        <div className="card-head">
          <h2 className="card-title">{title}</h2>
          {note ? <span className="card-note">{note}</span> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

// Measures where a rise is bad news, for specs that do not say.
const LOWER_IS_BETTER =
  /attrition|churn|turnover|leaver|defect|scrap|overdue|late|delay|incident|complaint|error|fail|downtime|backlog|cost|spend|expense|risk|absence|sick|waste|emission|lead time|time to/i;

export function StatTile({
  label,
  value,
  unit,
  delta,
  trend,
  icon,
  lowerIsBetter,
  deltaLabel,
}: {
  label: string;
  value: number | string;
  unit?: string;
  delta?: number;
  deltaLabel?: string;
  trend?: number[];
  icon?: string;
  lowerIsBetter?: boolean;
}) {
  const direction = delta === undefined ? "flat" : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const arrow = direction === "up" ? "▲" : direction === "down" ? "▼" : "■";
  // Rising attrition is bad news: the tint follows whether the change is good,
  // the arrow follows the number.
  const inverted = lowerIsBetter ?? LOWER_IS_BETTER.test(label);
  const tone =
    direction === "flat" ? "flat" : (direction === "up") !== inverted ? "good" : "bad";
  return (
    <section className="card tile">
      <div className="tile-head">
        <span className="tile-icon">
          <Icon name={icon} label={label} />
        </span>
        <div className="tile-label">{label}</div>
      </div>
      <div className="tile-body">
        <div className="tile-value">
          {typeof value === "number" ? formatNumber(value) : value}
          {unit ? <span className="tile-unit"> {unit}</span> : null}
        </div>
        {trend && trend.length > 1 ? <Sparkline values={trend} /> : null}
      </div>
      {delta !== undefined ? (
        <div className="tile-foot">
          {/* Arrow plus sign, so direction is never carried by colour alone. */}
          <span className={`delta delta-${tone}`}>
            {arrow} {Math.abs(delta).toFixed(1)}%
          </span>
          <span className="tile-note">{deltaLabel || "vs previous period"}</span>
        </div>
      ) : null}
    </section>
  );
}

/**
 * Each row a measure against its target: bars to the target, the share as
 * text. A met target is marked with a tick as well as colour.
 */
export function ProgressList({
  rows,
  labelField,
  valueField,
  targetField,
  unit,
}: {
  rows: Record<string, unknown>[];
  labelField: string;
  valueField: string;
  targetField: string;
  unit?: string;
}) {
  if (!rows.length) return <p className="empty">No data yet.</p>;
  return (
    <ul className="progress-list">
      {rows.slice(0, 8).map((row, i) => {
        const value = Number(row[valueField]) || 0;
        const target = Number(row[targetField]) || 0;
        const share = target > 0 ? value / target : 0;
        const met = target > 0 && value >= target;
        return (
          <li key={i}>
            <div className="progress-head">
              <span className="progress-label">{String(row[labelField] ?? "")}</span>
              <span className="progress-figures">
                {formatNumber(value)}
                <span className="progress-target">
                  {" "}
                  / {formatNumber(target)}
                  {unit ? ` ${unit}` : ""}
                </span>
              </span>
            </div>
            <div
              className="progress-track"
              role="progressbar"
              aria-label={String(row[labelField] ?? "")}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(share * 100)}
            >
              <div
                className={`progress-fill${met ? " is-met" : ""}`}
                style={{ width: `${Math.min(100, share * 100)}%` }}
              />
            </div>
            <div className={`progress-share${met ? " is-met" : ""}`}>
              {met ? "✓ " : ""}
              {Math.round(share * 100)}% of target
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Top entries by value, largest first, each with a bar scaled to the leader. */
export function RankingList({
  rows,
  labelField,
  valueField,
  unit,
}: {
  rows: Record<string, unknown>[];
  labelField: string;
  valueField: string;
  unit?: string;
}) {
  const ranked = [...rows]
    .map((row) => ({ label: String(row[labelField] ?? ""), value: Number(row[valueField]) || 0 }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);
  if (!ranked.length) return <p className="empty">No data yet.</p>;
  const top = Math.max(...ranked.map((r) => Math.abs(r.value))) || 1;
  return (
    <ol className="ranking">
      {ranked.map((entry, i) => (
        <li key={`${entry.label}-${i}`}>
          <span className={`rank${i < 3 ? " rank-top" : ""}`}>{i + 1}</span>
          <div className="rank-body">
            <div className="rank-head">
              <span className="rank-label">{entry.label}</span>
              <span className="rank-value">
                {formatNumber(entry.value)}
                {unit ? <span className="progress-target"> {unit}</span> : null}
              </span>
            </div>
            <div className="rank-track">
              <div className="rank-fill" style={{ width: `${(Math.abs(entry.value) / top) * 100}%` }} />
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

// Columns whose values are a state, shown as a chip. The word is always
// printed, so the tone is a cue, never the only signal.
const STATUS_FIELD = /status|state|stage|priority|risk|health/i;
const TONES: [RegExp, string][] = [
  [/late|overdue|fail|block|critical|high|risk|reject|lost|churn|breach|down|off.?track/i, "critical"],
  [/pending|progress|review|medium|wait|hold|open|new|draft|warn/i, "warning"],
  [/done|complete|active|paid|won|ok|on.?track|resolved|closed|approved|pass|low|healthy|up/i, "good"],
];

function toneOf(value: string): string {
  return TONES.find(([pattern]) => pattern.test(value))?.[1] ?? "neutral";
}

function Cell({ field, value }: { field: string; value: unknown }) {
  if (typeof value === "number") return <>{formatNumber(value)}</>;
  const text = String(value ?? "");
  if (text && STATUS_FIELD.test(field)) {
    return <span className={`chip chip-${toneOf(text)}`}>{text}</span>;
  }
  return <>{text}</>;
}

/** Numbers line up on the right unless the spec says otherwise. */
function alignFor(
  col: { field: string; align?: "left" | "right" },
  rows: Record<string, unknown>[],
): "left" | "right" {
  if (col.align) return col.align;
  return rows.length && typeof rows[0][col.field] === "number" ? "right" : "left";
}

/** Placeholder cards while the first data loads, shaped like the dashboard. */
export function Skeleton() {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading">
      <div className="row row-4">
        {[0, 1, 2, 3].map((i) => (
          <div className="card skeleton-card skeleton-short" key={i} />
        ))}
      </div>
      <div className="row row-split" style={{ "--cols": "2fr 1fr" } as CSSProperties}>
        <div className="card skeleton-card" />
        <div className="card skeleton-card" />
      </div>
    </div>
  );
}

type TableColumn = { label: string; field: string; align?: "left" | "right" };
type Row = Record<string, unknown>;

const PAGE_SIZE = 25;

/** A records table shows exact values: 12,400 rather than the charts' 12.4k. */
function exact(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function TableCell({ field, value }: { field: string; value: unknown }) {
  if (typeof value === "number") return <>{exact(value)}</>;
  return <Cell field={field} value={value} />;
}

/** The full text as a tooltip when the cell is cut short with an ellipsis. */
function longText(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 36 ? value : undefined;
}

function matches(row: Row, term: string): boolean {
  return Object.values(row).some((value) =>
    String(value ?? "")
      .toLowerCase()
      .includes(term),
  );
}

function csvField(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/**
 * Every row as a CSV the user can open in Excel or upload again: the table's
 * columns first under their labels, then any other field the API returned.
 * The platform's own row id is left out of editable tables, since the file
 * the user uploaded never had it.
 */
function downloadCsv(rows: Row[], columns: TableColumn[], name: string, dropId: boolean) {
  const known = columns.map((c) => c.field);
  const extra = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).filter(
    (key) => !known.includes(key),
  );
  const fields = [...known, ...extra].filter((field) => !(dropId && field === "id"));
  const label = (field: string) => columns.find((c) => c.field === field)?.label ?? field;
  const lines = [
    fields.map((field) => csvField(label(field))).join(","),
    ...rows.map((row) => fields.map((field) => csvField(row[field])).join(",")),
  ];
  // BOM: without it Excel reads UTF-8 as ANSI and mangles umlauts and euros.
  const blob = new Blob(["﻿" + lines.join("\r\n") + "\r\n"], {
    type: "text/csv;charset=utf-8",
  });
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "table";
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${slug}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

/** Search, sort and page a list of rows; shared by both table kinds. */
function useTableView(rows: Row[]) {
  const [term, setTerm] = useState("");
  const [sort, setSort] = useState<{ field: string; dir: 1 | -1 } | null>(null);
  const [page, setPage] = useState(0);

  const shown = useMemo(() => {
    const needle = term.trim().toLowerCase();
    const found = needle ? rows.filter((row) => matches(row, needle)) : rows;
    if (!sort) return found;
    return [...found].sort((a, b) => {
      const x = a[sort.field];
      const y = b[sort.field];
      if (typeof x === "number" && typeof y === "number") return (x - y) * sort.dir;
      return String(x ?? "").localeCompare(String(y ?? ""), undefined, { numeric: true }) * sort.dir;
    });
  }, [rows, term, sort]);

  const pages = Math.max(1, Math.ceil(shown.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  return {
    term,
    search: (value: string) => {
      setTerm(value);
      setPage(0);
    },
    sort,
    toggleSort: (field: string) =>
      setSort((s) => (s?.field === field && s.dir === 1 ? { field, dir: -1 } : { field, dir: 1 })),
    shown,
    pageRows: shown.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE),
    page: current,
    pages,
    setPage,
  };
}

type TableView = ReturnType<typeof useTableView>;

function Toolbar({
  view,
  total,
  onDownload,
  children,
}: {
  view: TableView;
  total: number;
  onDownload: () => void;
  children?: ReactNode;
}) {
  const filtered = view.shown.length !== total;
  return (
    <div className="table-toolbar">
      <input
        type="search"
        className="table-search"
        placeholder="Search…"
        aria-label="Search rows"
        value={view.term}
        onChange={(e) => view.search(e.target.value)}
      />
      <span className="table-count">
        {filtered ? `${exact(view.shown.length)} of ${exact(total)}` : exact(total)} rows
      </span>
      <span className="shell-spacer" />
      {children}
      <button
        type="button"
        className="btn"
        onClick={onDownload}
        disabled={!view.shown.length}
        title={filtered ? "Download the rows that match the search" : "Download every row"}
      >
        ⤓ Download CSV
      </button>
    </div>
  );
}

function Pager({ view }: { view: TableView }) {
  if (view.pages <= 1) return null;
  const first = view.page * PAGE_SIZE + 1;
  const last = Math.min(view.shown.length, first + PAGE_SIZE - 1);
  return (
    <div className="table-pager">
      <button
        type="button"
        className="btn"
        disabled={view.page === 0}
        onClick={() => view.setPage(view.page - 1)}
        aria-label="Previous page"
      >
        ‹
      </button>
      <span>
        {exact(first)}–{exact(last)} of {exact(view.shown.length)}
      </span>
      <button
        type="button"
        className="btn"
        disabled={view.page >= view.pages - 1}
        onClick={() => view.setPage(view.page + 1)}
        aria-label="Next page"
      >
        ›
      </button>
    </div>
  );
}

function SortableHead({
  view,
  columns,
  rows,
  actions,
}: {
  view: TableView;
  columns: TableColumn[];
  rows: Row[];
  actions?: boolean;
}) {
  return (
    <thead>
      <tr>
        {columns.map((col) => {
          const active = view.sort?.field === col.field;
          return (
            <th
              key={col.field}
              aria-sort={active ? (view.sort!.dir === 1 ? "ascending" : "descending") : undefined}
              onClick={() => view.toggleSort(col.field)}
              style={{ textAlign: alignFor(col, rows) }}
            >
              {col.label}
              {active ? (view.sort!.dir === 1 ? " ↑" : " ↓") : ""}
            </th>
          );
        })}
        {actions ? (
          <th className="cell-actions">
            <span className="visually-hidden">Actions</span>
          </th>
        ) : null}
      </tr>
    </thead>
  );
}

export function DataTable({
  rows,
  columns,
  title,
}: {
  rows: Row[];
  columns: TableColumn[];
  title: string;
}) {
  const view = useTableView(rows);
  if (!rows.length) return <p className="empty">No records yet.</p>;
  return (
    <div>
      <Toolbar view={view} total={rows.length} onDownload={() => downloadCsv(view.shown, columns, title, false)} />
      <div className="table-scroll">
        <table>
          <SortableHead view={view} columns={columns} rows={rows} />
          <tbody>
            {view.pageRows.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td
                    key={col.field}
                    style={{ textAlign: alignFor(col, rows) }}
                    title={longText(row[col.field])}
                  >
                    <TableCell field={col.field} value={row[col.field]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!view.shown.length ? <p className="empty">No rows match “{view.term}”.</p> : null}
      <Pager view={view} />
    </div>
  );
}

/**
 * A table whose rows users can create, edit and delete. The backend contract
 * comes from the spec: POST <endpoint> creates, PUT/DELETE <endpoint>/{id}
 * update and remove, and every row carries an "id" (validated by
 * app/generation/spec.py). Download CSV saves the table as it stands, edits
 * included.
 */
export function EditableDataTable({
  endpoint,
  rows,
  columns,
  title,
  onMutate,
}: {
  endpoint: string;
  rows: Row[];
  columns: TableColumn[];
  title: string;
  onMutate: () => void;
}) {
  const fields = columns.filter((col) => col.field !== "id");
  const view = useTableView(rows);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<unknown>(null);
  const [editDraft, setEditDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function mutate(path: string, method: string, body?: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      // method first: the api-contract check pairs this literal with the path.
      const response = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!response.ok) throw new Error(`${method} ${path} returned ${response.status}`);
      onMutate();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "The change could not be saved");
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Toolbar view={view} total={rows.length} onDownload={() => downloadCsv(view.shown, columns, title, true)}>
        <button
          type="button"
          className="btn btn-accent"
          onClick={() => setAdding((a) => !a)}
          aria-expanded={adding}
        >
          {adding ? "Close" : "+ Add row"}
        </button>
      </Toolbar>

      {adding ? (
        <form
          className="add-panel"
          onSubmit={async (event) => {
            event.preventDefault();
            if (await mutate(endpoint, "POST", { ...draft })) {
              setDraft({});
              setAdding(false);
            }
          }}
        >
          {fields.map((col) => (
            <label key={col.field}>
              <span>{col.label}</span>
              <input
                value={draft[col.field] ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, [col.field]: e.target.value }))}
              />
            </label>
          ))}
          <div className="add-actions">
            <button type="button" className="btn" onClick={() => setAdding(false)}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-accent"
              disabled={busy || fields.every((col) => !draft[col.field]?.trim())}
            >
              Save row
            </button>
          </div>
        </form>
      ) : null}

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}

      {rows.length === 0 ? <p className="empty">No records yet — add the first one.</p> : null}

      {rows.length > 0 ? (
        <div className="table-scroll">
          <table>
            <SortableHead view={view} columns={columns} rows={rows} actions />
            <tbody>
              {view.pageRows.map((row) =>
                editingId !== null && row.id === editingId ? (
                  <tr key={String(row.id)} className="row-editing">
                    {columns.map((col) => (
                      <td key={col.field}>
                        {col.field === "id" ? (
                          String(row.id)
                        ) : (
                          <input
                            aria-label={col.label}
                            value={editDraft[col.field] ?? ""}
                            onChange={(e) =>
                              setEditDraft((d) => ({ ...d, [col.field]: e.target.value }))
                            }
                          />
                        )}
                      </td>
                    ))}
                    <td className="cell-actions">
                      <button
                        type="button"
                        className="btn btn-accent"
                        disabled={busy}
                        onClick={async () => {
                          if (await mutate(`${endpoint}/${row.id}`, "PUT", { ...editDraft })) {
                            setEditingId(null);
                          }
                        }}
                      >
                        Save
                      </button>
                      <button type="button" className="btn" onClick={() => setEditingId(null)}>
                        Cancel
                      </button>
                    </td>
                  </tr>
                ) : (
                  <tr key={String(row.id)}>
                    {columns.map((col) => (
                      <td
                        key={col.field}
                        style={{ textAlign: alignFor(col, rows) }}
                        title={longText(row[col.field])}
                      >
                        <TableCell field={col.field} value={row[col.field]} />
                      </td>
                    ))}
                    <td className="cell-actions">
                      <button
                        type="button"
                        className="btn btn-quiet"
                        disabled={busy}
                        onClick={() => {
                          setEditingId(row.id);
                          setEditDraft(
                            Object.fromEntries(
                              fields.map((col) => [col.field, String(row[col.field] ?? "")]),
                            ),
                          );
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-quiet btn-danger"
                        disabled={busy}
                        onClick={() => {
                          // A misclick here loses a record; ask once.
                          if (window.confirm("Delete this row?")) {
                            void mutate(`${endpoint}/${row.id}`, "DELETE");
                          }
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      ) : null}
      {rows.length > 0 && !view.shown.length ? (
        <p className="empty">No rows match “{view.term}”.</p>
      ) : null}
      <Pager view={view} />
    </div>
  );
}

export function FilterRail({
  filters,
  value,
  onChange,
}: {
  filters: { label: string; field: string; options: string[] }[];
  value: Record<string, string>;
  onChange: (field: string, option: string) => void;
}) {
  return (
    <section className="card rail">
      {filters.map((filter) => (
        <div key={filter.field}>
          <div className="rail-group">{filter.label}</div>
          <div className="rail">
            {filter.options.map((option) => (
              <button
                type="button"
                key={option}
                className={`btn${value[filter.field] === option ? " btn-accent" : ""}`}
                onClick={() => onChange(filter.field, option)}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

// "design" is this project's own palette from design.css, so it leads and is
// the default; the fixed accents remain as alternatives.
const THEMES = ["design", "indigo", "teal", "amber", "rose", "violet", "graphite"] as const;
const SWATCH: Record<string, string> = {
  // Its own token, which no theme repoints, so the swatch keeps the palette's
  // colour while another theme is active.
  design: "var(--design-accent)",
  indigo: "#4338ca",
  teal: "#0f766e",
  amber: "#b45309",
  rose: "#be123c",
  violet: "#6d28d9",
  graphite: "#334155",
};

/** Reading storage can throw outright in private browsing, not just return null. */
function stored(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

/** Theme and light/dark, both persisted so a demo survives a reload. */
export function ThemeSwitcher({ initialTheme }: { initialTheme?: string }) {
  const [theme, setTheme] = useState(() => stored("poc-theme", initialTheme ?? "design"));
  const [mode, setMode] = useState(() => stored("poc-mode", "auto"));

  // useEffect, not useMemo: this mutates the document, and a render-phase
  // side effect misbehaves under StrictMode's double render.
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    if (mode === "auto") root.removeAttribute("data-mode");
    else root.setAttribute("data-mode", mode);
    try {
      localStorage.setItem("poc-theme", theme);
      localStorage.setItem("poc-mode", mode);
    } catch {
      // Storage refused; the theme still applies for this visit.
    }
  }, [theme, mode]);

  return (
    <>
      <div className="swatches" role="group" aria-label="Colour theme">
        {THEMES.map((name) => (
          <button
            type="button"
            key={name}
            className="swatch"
            style={{ background: SWATCH[name] }}
            aria-label={name}
            aria-pressed={theme === name}
            onClick={() => setTheme(name)}
          />
        ))}
      </div>
      <button
        type="button"
        className="btn"
        onClick={() => setMode(mode === "dark" ? "light" : "dark")}
      >
        {mode === "dark" ? "Light" : "Dark"}
      </button>
    </>
  );
}
