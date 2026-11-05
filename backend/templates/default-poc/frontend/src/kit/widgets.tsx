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
}: {
  label: string;
  value: number | string;
  unit?: string;
  delta?: number;
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
          <span className="tile-note">vs previous period</span>
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

export function DataTable({
  rows,
  columns,
}: {
  rows: Record<string, unknown>[];
  columns: { label: string; field: string; align?: "left" | "right" }[];
}) {
  const [sort, setSort] = useState<{ field: string; dir: 1 | -1 } | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => {
      const x = a[sort.field];
      const y = b[sort.field];
      if (typeof x === "number" && typeof y === "number") return (x - y) * sort.dir;
      return String(x ?? "").localeCompare(String(y ?? "")) * sort.dir;
    });
  }, [rows, sort]);

  if (!rows.length) return <p className="empty">No records yet.</p>;

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map((col) => {
              const active = sort?.field === col.field;
              return (
                <th
                  key={col.field}
                  aria-sort={active ? (sort!.dir === 1 ? "ascending" : "descending") : undefined}
                  onClick={() =>
                    setSort(
                      active && sort!.dir === 1
                        ? { field: col.field, dir: -1 }
                        : { field: col.field, dir: 1 },
                    )
                  }
                  style={{ textAlign: alignFor(col, rows) }}
                >
                  {col.label}
                  {active ? (sort!.dir === 1 ? " ↑" : " ↓") : ""}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td key={col.field} style={{ textAlign: alignFor(col, rows) }}>
                  <Cell field={col.field} value={row[col.field]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type TableColumn = { label: string; field: string; align?: "left" | "right" };

/**
 * A table whose rows users can create, edit and delete. The backend contract
 * comes from the spec: POST <endpoint> creates, PUT/DELETE <endpoint>/{id}
 * update and remove, and every row carries an "id" (validated by
 * app/generation/spec.py).
 */
export function EditableDataTable({
  endpoint,
  rows,
  columns,
  onMutate,
}: {
  endpoint: string;
  rows: Record<string, unknown>[];
  columns: TableColumn[];
  onMutate: () => void;
}) {
  const fields = columns.filter((col) => col.field !== "id");
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "The change could not be saved");
    } finally {
      setBusy(false);
    }
  }

  const addDisabled = busy || fields.some((col) => !draft[col.field]?.trim());

  return (
    <div>
      <div className="add-row">
        {fields.map((col) => (
          <input
            key={col.field}
            aria-label={col.label}
            placeholder={col.label}
            value={draft[col.field] ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, [col.field]: e.target.value }))}
          />
        ))}
        <button
          type="button"
          className="btn btn-accent"
          disabled={addDisabled}
          onClick={() => {
            mutate(endpoint, "POST", { ...draft });
            setDraft({});
          }}
        >
          Add
        </button>
      </div>

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}

      {rows.length === 0 ? <p className="empty">No records yet — add the first one.</p> : null}

      {rows.length > 0 ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col.field} style={{ textAlign: alignFor(col, rows) }}>
                    {col.label}
                  </th>
                ))}
                <th className="cell-actions">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) =>
                editingId !== null && row.id === editingId ? (
                  <tr key={String(row.id)}>
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
                        onClick={() => {
                          mutate(`${endpoint}/${row.id}`, "PUT", { ...editDraft });
                          setEditingId(null);
                        }}
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => setEditingId(null)}
                      >
                        Cancel
                      </button>
                    </td>
                  </tr>
                ) : (
                  <tr key={String(row.id)}>
                    {columns.map((col) => (
                      <td key={col.field} style={{ textAlign: alignFor(col, rows) }}>
                        <Cell field={col.field} value={row[col.field]} />
                      </td>
                    ))}
                    <td className="cell-actions">
                      <button
                        type="button"
                        className="btn"
                        disabled={busy}
                        onClick={() => {
                          setEditingId(row.id);
                          setEditDraft(
                            Object.fromEntries(fields.map((col) => [col.field, String(row[col.field] ?? "")])),
                          );
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        disabled={busy}
                        onClick={() => mutate(`${endpoint}/${row.id}`, "DELETE")}
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
