// Non-chart widgets, plus the theme switcher.

import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { Sparkline, formatNumber } from "./charts";

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

export function StatTile({
  label,
  value,
  unit,
  delta,
  trend,
}: {
  label: string;
  value: number | string;
  unit?: string;
  delta?: number;
  trend?: number[];
}) {
  const direction = delta === undefined ? "flat" : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const arrow = direction === "up" ? "▲" : direction === "down" ? "▼" : "■";
  return (
    <section className="card">
      <div className="tile-label">{label}</div>
      <div className="tile-value">
        {typeof value === "number" ? formatNumber(value) : value}
        {unit ? <span style={{ fontSize: "0.6em", color: "var(--ink-3)" }}> {unit}</span> : null}
      </div>
      <div className="tile-foot">
        {delta !== undefined ? (
          // Arrow plus sign, so direction is never carried by colour alone.
          <span className={`delta delta-${direction}`}>
            {arrow} {Math.abs(delta).toFixed(1)}%
          </span>
        ) : null}
        <span className="shell-spacer" />
        {trend && trend.length > 1 ? <Sparkline values={trend} /> : null}
      </div>
    </section>
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
                  style={{ textAlign: col.align ?? "left" }}
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
                <td key={col.field} style={{ textAlign: col.align ?? "left" }}>
                  {typeof row[col.field] === "number"
                    ? formatNumber(row[col.field] as number)
                    : String(row[col.field] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
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

const THEMES = ["indigo", "teal", "amber", "rose", "violet", "graphite"] as const;
const SWATCH: Record<string, string> = {
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
  const [theme, setTheme] = useState(() => stored("poc-theme", initialTheme ?? "indigo"));
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
