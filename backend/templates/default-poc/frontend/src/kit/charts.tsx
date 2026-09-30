// Hand-authored SVG charts. No charting dependency: it keeps npm install small
// and removes a build failure mode from generated projects.
//
// Every plot carries a legend when it has two or more series and direct labels
// on the last point, because three of the light series hues sit below 3:1
// against white — the contrast relief is required, not optional.
//
// One y-axis only, always. Two measures of different scale belong in two
// charts, never a second axis.

import { useState } from "react";

const SERIES = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
  "var(--series-7)",
  "var(--series-8)",
];

/** Fixed order, never cycled: past eight series the caller must fold the rest. */
export function seriesColor(index: number): string {
  return SERIES[Math.min(index, SERIES.length - 1)];
}

export function formatNumber(value: number): string {
  if (!isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return abs < 10 && !Number.isInteger(value) ? value.toFixed(1) : String(Math.round(value));
}

function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) return [min];
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10;
  const start = Math.floor(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step / 2; v += step) ticks.push(Number(v.toFixed(10)));
  return ticks;
}

interface Tip {
  x: number;
  y: number;
  rows: { label: string; value: string; color?: string }[];
}

function Tooltip({ tip }: { tip: Tip | null }) {
  if (!tip) return null;
  return (
    <div className="tooltip" style={{ left: tip.x + 12, top: tip.y + 12 }} role="presentation">
      {tip.rows.map((row) => (
        <div className="tooltip-row" key={row.label}>
          {row.color ? (
            <span className="legend-mark" style={{ background: row.color }} />
          ) : null}
          <strong>{row.label}</strong>
          <span>{row.value}</span>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  if (items.length < 2) return null; // one series is named by the title
  return (
    <div className="legend">
      {items.map((item) => (
        <span className="legend-item" key={item.label}>
          <span className="legend-mark" style={{ background: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

/** A trend shape with no axes, for use inside a stat tile. */
export function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const w = 96;
  const h = 26;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / span) * (h - 4) - 2}`)
    .join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" focusable="false">
      <polyline className="chart-line" points={points} stroke="var(--accent)" />
    </svg>
  );
}

interface LineProps {
  rows: Record<string, unknown>[];
  xField: string;
  series: { label: string; field: string }[];
}

export function LineChart({ rows, xField, series }: LineProps) {
  const [tip, setTip] = useState<Tip | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!rows.length) return <p className="empty">No data yet.</p>;

  const W = 720;
  const H = 260;
  const pad = { top: 14, right: 54, bottom: 30, left: 48 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const nums = series.flatMap((s) => rows.map((r) => Number(r[s.field]) || 0));
  const ticks = niceTicks(Math.min(0, ...nums), Math.max(...nums));
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];
  const ySpan = yMax - yMin || 1;

  const xAt = (i: number) => pad.left + (rows.length === 1 ? plotW / 2 : (i / (rows.length - 1)) * plotW);
  const yAt = (v: number) => pad.top + plotH - ((v - yMin) / ySpan) * plotH;

  const legend = series.map((s, i) => ({ label: s.label, color: seriesColor(i) }));
  const labelEvery = Math.ceil(rows.length / 6);

  return (
    <>
      <svg
        className="chart"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Line chart of ${series.map((s) => s.label).join(", ")} over ${xField}`}
        onMouseLeave={() => {
          setTip(null);
          setHoverIndex(null);
        }}
        onMouseMove={(event) => {
          const box = event.currentTarget.getBoundingClientRect();
          const local = ((event.clientX - box.left) / box.width) * W;
          const i = Math.round(((local - pad.left) / plotW) * (rows.length - 1));
          const index = Math.max(0, Math.min(rows.length - 1, i));
          setHoverIndex(index);
          setTip({
            x: event.clientX,
            y: event.clientY,
            rows: [
              { label: String(rows[index][xField] ?? ""), value: "" },
              ...series.map((s, si) => ({
                label: s.label,
                value: formatNumber(Number(rows[index][s.field]) || 0),
                color: seriesColor(si),
              })),
            ],
          });
        }}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className="chart-grid" x1={pad.left} x2={W - pad.right} y1={yAt(t)} y2={yAt(t)} />
            <text className="chart-axis" x={pad.left - 8} y={yAt(t) + 4} textAnchor="end">
              {formatNumber(t)}
            </text>
          </g>
        ))}

        {rows.map((row, i) =>
          i % labelEvery === 0 ? (
            <text
              className="chart-axis"
              key={i}
              x={xAt(i)}
              y={H - 10}
              textAnchor="middle"
            >
              {String(row[xField] ?? "")}
            </text>
          ) : null,
        )}

        {hoverIndex !== null ? (
          <line
            className="chart-grid"
            x1={xAt(hoverIndex)}
            x2={xAt(hoverIndex)}
            y1={pad.top}
            y2={pad.top + plotH}
            stroke="var(--ink-3)"
          />
        ) : null}

        {series.map((s, si) => {
          const pts = rows.map((r, i) => `${xAt(i)},${yAt(Number(r[s.field]) || 0)}`).join(" ");
          const last = rows[rows.length - 1];
          return (
            <g key={s.field}>
              <polyline className="chart-line" points={pts} stroke={seriesColor(si)} />
              {/* Direct label on the final point: identity without relying on colour. */}
              <text
                className="chart-label"
                x={W - pad.right + 6}
                y={yAt(Number(last[s.field]) || 0) + 4}
                fill={seriesColor(si)}
              >
                {formatNumber(Number(last[s.field]) || 0)}
              </text>
              {hoverIndex !== null ? (
                <circle
                  cx={xAt(hoverIndex)}
                  cy={yAt(Number(rows[hoverIndex][s.field]) || 0)}
                  r={5}
                  fill={seriesColor(si)}
                  stroke="var(--surface-0)"
                  strokeWidth={2}
                />
              ) : null}
            </g>
          );
        })}
      </svg>
      <Legend items={legend} />
      <Tooltip tip={tip} />
    </>
  );
}

interface BarProps {
  rows: Record<string, unknown>[];
  categoryField: string;
  series: { label: string; field: string }[];
}

export function BarChart({ rows, categoryField, series }: BarProps) {
  const [tip, setTip] = useState<Tip | null>(null);
  if (!rows.length) return <p className="empty">No data yet.</p>;

  const W = 720;
  const H = 260;
  const pad = { top: 14, right: 16, bottom: 34, left: 48 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const nums = series.flatMap((s) => rows.map((r) => Number(r[s.field]) || 0));
  const ticks = niceTicks(0, Math.max(...nums));
  const yMax = ticks[ticks.length - 1] || 1;

  const groupW = plotW / rows.length;
  const barW = Math.max(6, (groupW - 12) / series.length - 2); // 2px surface gap
  const yAt = (v: number) => pad.top + plotH - (v / yMax) * plotH;

  return (
    <>
      <svg
        className="chart"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Bar chart of ${series.map((s) => s.label).join(", ")} by ${categoryField}`}
        onMouseLeave={() => setTip(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className="chart-grid" x1={pad.left} x2={W - pad.right} y1={yAt(t)} y2={yAt(t)} />
            <text className="chart-axis" x={pad.left - 8} y={yAt(t) + 4} textAnchor="end">
              {formatNumber(t)}
            </text>
          </g>
        ))}

        {rows.map((row, ri) => (
          <g key={ri}>
            <text
              className="chart-axis"
              x={pad.left + groupW * ri + groupW / 2}
              y={H - 12}
              textAnchor="middle"
            >
              {String(row[categoryField] ?? "")}
            </text>
            {series.map((s, si) => {
              const value = Number(row[s.field]) || 0;
              const x = pad.left + groupW * ri + 6 + si * (barW + 2);
              const y = yAt(value);
              return (
                <rect
                  key={s.field}
                  x={x}
                  y={y}
                  width={barW}
                  height={Math.max(0, pad.top + plotH - y)}
                  rx={4}
                  fill={seriesColor(si)}
                  onMouseMove={(event) =>
                    setTip({
                      x: event.clientX,
                      y: event.clientY,
                      rows: [
                        { label: String(row[categoryField] ?? ""), value: "" },
                        { label: s.label, value: formatNumber(value), color: seriesColor(si) },
                      ],
                    })
                  }
                />
              );
            })}
          </g>
        ))}
      </svg>
      <Legend items={series.map((s, i) => ({ label: s.label, color: seriesColor(i) }))} />
      <Tooltip tip={tip} />
    </>
  );
}
