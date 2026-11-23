// Hand-authored SVG charts. No charting dependency: it keeps npm install small
// and removes a build failure mode from generated projects.
//
// Every plot carries a legend when it has two or more series and direct labels
// on the last point, because three of the light series hues sit below 3:1
// against white — the contrast relief is required, not optional.
//
// One y-axis only, always. Two measures of different scale belong in two
// charts, never a second axis.
//
// Line series after the first are also dashed or dotted (ui-ux-pro-max's chart
// rule: never tell series apart by hue alone), so a chart still reads in
// greyscale and for colour-blind viewers.

import { useEffect, useId, useState } from "react";
import { finite, monthLabel } from "./insights";
import type { Annotation } from "./insights";

interface ChartComparison { kind: "target" | "prior"; label: string; field: string }
interface StoryProps { comparison?: ChartComparison; annotation?: Annotation | null; lowerIsBetter?: boolean | null }
const axisLabel = (value: unknown, limit = 12) => {
  const text = monthLabel(value, true) ?? String(value ?? "");
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
};

function PointNote({ annotation, x, y, width }: {
  annotation?: Annotation | null; x: number; y: number; width: number;
}) {
  if (!annotation) return null;
  const labelX = Math.max(80, Math.min(width - 80, x));
  return <g data-annotation={annotation.label}>
    <title>{`${annotation.label}: ${annotation.value}`}</title>
    <circle cx={x} cy={y} r={4} fill="var(--accent)" stroke="var(--surface-0)" strokeWidth={2} />
    <line x1={x} x2={labelX} y1={y - 6} y2={42} stroke="var(--ink-3)" strokeDasharray="2 3" />
    <text x={labelX} y={35} textAnchor="middle" className="chart-label">{annotation.text}</text>
  </g>;
}

/** Dedicated top lane, separate from the annotation lane and all data marks. */
function TargetLabel({ comparison, refs, width }: {
  comparison?: ChartComparison; refs: number[]; width: number;
}) {
  if (comparison?.kind !== "target" || !refs.length) return null;
  const constant = refs.every(v => v === refs[0]);
  return <text data-target-label="true" className="chart-axis" x={width - 8} y={13} textAnchor="end">
    {`${axisLabel(comparison.label, 24)} ${constant ? formatNumber(refs[0]) : `${formatNumber(Math.min(...refs))}–${formatNumber(Math.max(...refs))}`}`}
  </text>;
}

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

export { formatNumber } from "./format";
import { formatNumber } from "./format";

function niceTicks(min: number, max: number, count = 4): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  if (min === max) return [min];
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10;
  const start = Math.floor(min / step) * step;
  const ticks: number[] = [];
  // Keep going until a tick reaches the data's max. Stopping half a step past
  // it left anything in that last half-step above the axis, drawn over the
  // chart title (data max 12, ticks 0/5/10).
  for (let v = start, i = 0; i < 32; v += step, i++) {
    const tick = Number(v.toFixed(10));
    ticks.push(tick);
    if (tick >= max) break;
  }
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

export function Legend({ items }: { items: { label: string; color: string; dash?: string }[] }) {
  if (items.length < 2) return null; // one series is named by the title
  return (
    <div className="legend">
      {items.map((item) => (
        <span className="legend-item" key={item.label}>
          {item.dash !== undefined ? (
            // A line chart's key shows the stroke itself, dash and all.
            <svg width="22" height="10" aria-hidden="true" focusable="false">
              <line
                x1="2"
                x2="20"
                y1="5"
                y2="5"
                stroke={item.color}
                strokeWidth={2.5}
                strokeDasharray={item.dash || undefined}
                strokeLinecap="round"
              />
            </svg>
          ) : (
            <span className="legend-mark" style={{ background: item.color }} />
          )}
          {item.label}
        </span>
      ))}
    </div>
  );
}

/**
 * The chart's real width in CSS pixels, so it draws at 1:1. A fixed viewBox
 * scaled to a full-width card blew 11px axis labels up to 20px and more.
 */
function useWidth(fallback: number) {
  // A callback ref, not useRef: the chart's box only mounts once rows arrive,
  // and an effect keyed on a ref object would never see it appear.
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.round(entry.contentRect.width);
      if (next > 0) setWidth(Math.max(280, next));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [node]);
  return [setNode, width] as const;
}

/** Dash pattern per series index: solid first, then dashed, dotted, dash-dot. */
const DASHES = ["", "7 5", "2 4", "10 4 2 4"];
function dashFor(index: number): string {
  return DASHES[index % DASHES.length];
}

/**
 * A smooth path through the points that never overshoots them (monotone cubic,
 * Fritsch–Carlson): a curve that dips below zero between two positive values
 * would show data that does not exist.
 */
function smoothPath(points: [number, number][]): string {
  const n = points.length;
  if (n === 0) return "";
  if (n < 3) return points.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ");
  const dx: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    dx.push(points[i + 1][0] - points[i][0]);
    slope.push((points[i + 1][1] - points[i][1]) / (dx[i] || 1));
  }
  const tangent = [slope[0]];
  for (let i = 1; i < n - 1; i++) {
    tangent.push(slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2);
  }
  tangent.push(slope[n - 2]);
  for (let i = 0; i < n - 1; i++) {
    if (slope[i] === 0) {
      tangent[i] = 0;
      tangent[i + 1] = 0;
      continue;
    }
    const a = tangent[i] / slope[i];
    const b = tangent[i + 1] / slope[i];
    const h = a * a + b * b;
    if (h > 9) {
      const t = 3 / Math.sqrt(h);
      tangent[i] = t * a * slope[i];
      tangent[i + 1] = t * b * slope[i];
    }
  }
  let d = `M${points[0][0]},${points[0][1]}`;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = points[i];
    const [x1, y1] = points[i + 1];
    const h = dx[i] / 3;
    d += ` C${x0 + h},${y0 + tangent[i] * h} ${x1 - h},${y1 - tangent[i + 1] * h} ${x1},${y1}`;
  }
  return d;
}

/** useId output contains colons; url(#…) needs them escaped. */
function gradientUrl(id: string): string {
  return `url(#${CSS.escape(id)})`;
}

/** A trend shape with no axes, for use inside a stat tile. */
export function Sparkline({ values }: { values: number[] }) {
  const id = useId();
  if (values.length < 2) return null;
  const w = 112;
  const h = 34;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map(
    (v, i) => [(i / (values.length - 1)) * w, h - ((v - min) / span) * (h - 6) - 3] as [number, number],
  );
  const line = smoothPath(points);
  const last = points[points.length - 1];
  return (
    <svg className="sparkline" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.28} />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={`${line} L${w},${h} L0,${h} Z`} fill={gradientUrl(id)} stroke="none" />
      <path className="chart-line" d={line} stroke="var(--accent)" />
      <circle cx={last[0]} cy={last[1]} r={2.5} fill="var(--accent)" />
    </svg>
  );
}

interface LineProps extends StoryProps {
  rows: Record<string, unknown>[];
  xField: string;
  series: { label: string; field: string }[];
}

export function LineChart({ rows, xField, series, comparison, annotation }: LineProps) {
  const [tip, setTip] = useState<Tip | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const gradientBase = useId();
  const [box, W] = useWidth(720);

  const nums = series.flatMap(s => rows.flatMap(r => finite(r[s.field]) === null ? [] : [r[s.field] as number]));
  if (!nums.length) return <p className="empty">No values for this period. Try a different filter.</p>;

  const H = 260;
  const pad = { top: 64, right: 54, bottom: 30, left: 48 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const refs = comparison ? rows.flatMap(r => finite(r[comparison.field]) === null ? [] : [r[comparison.field] as number]) : [];
  const ticks = niceTicks(Math.min(0, ...nums, ...refs), Math.max(0, ...nums, ...refs));
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];
  const ySpan = yMax - yMin || 1;

  const xAt = (i: number) => pad.left + (rows.length === 1 ? plotW / 2 : (i / (rows.length - 1)) * plotW);
  const yAt = (v: number) => pad.top + plotH - ((v - yMin) / ySpan) * plotH;
  const baseline = yAt(Math.max(yMin, 0));

  const legend = series.map((s, i) => ({ label: s.label, color: seriesColor(i), dash: dashFor(i) }));
  const labelEvery = Math.ceil(rows.length / 6);
  // Only the lead series is filled: a second area over it mixes the two hues
  // into a third colour that belongs to neither.
  const filled = (index: number) => index === 0;
  const pathFor = (field: string) => {
    const runs: [number, number][][] = [[]];
    rows.forEach((row, i) => {
      const value = finite(row[field]);
      if (value === null) { if (runs[runs.length - 1].length) runs.push([]); }
      else runs[runs.length - 1].push([xAt(i), yAt(value)]);
    });
    return runs.filter(run => run.length).map(smoothPath).join(" ");
  };

  return (
    <div ref={box}>
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
                value: formatNumber(finite(rows[index][s.field]) ?? NaN),
                color: seriesColor(si),
              })),
            ],
          });
        }}
      >
        <defs>
          {series.map((s, si) => (
            <linearGradient key={s.field} id={`${gradientBase}-${si}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={seriesColor(si)} stopOpacity={0.24} />
              <stop offset="100%" stopColor={seriesColor(si)} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>

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
            <text className="chart-axis" key={i} x={xAt(i)} y={H - 10} textAnchor="middle">
              <title>{String(row[xField] ?? "")}</title>{axisLabel(row[xField])}
            </text>
          ) : null,
        )}

        {hoverIndex !== null ? (
          <line
            className="chart-cursor"
            x1={xAt(hoverIndex)}
            x2={xAt(hoverIndex)}
            y1={pad.top}
            y2={pad.top + plotH}
          />
        ) : null}

        {comparison && refs.length ? <path data-comparison={comparison.kind}
          d={pathFor(comparison.field)} fill="none" stroke="var(--series-1)"
          strokeWidth={comparison.kind === "prior" ? 1.5 : 2}
          opacity={comparison.kind === "prior" ? 0.35 : 0.8} strokeDasharray="7 5">
          <title>{comparison.label}</title>
        </path> : null}
        <TargetLabel comparison={comparison} refs={refs} width={W} />
        {series.map((s, si) => {
          const valid = rows.flatMap((r, i) => finite(r[s.field]) === null ? [] : [{ i, value: r[s.field] as number }]);
          if (!valid.length) return null;
          const points = valid.map(r => [xAt(r.i), yAt(r.value)] as [number, number]);
          const line = pathFor(s.field);
          const last = points[points.length - 1];
          const lastValue = valid[valid.length - 1].value;
          return (
            <g key={s.field}>
              {filled(si) && points.length > 1 && valid.length === rows.length ? (
                <path
                  d={`${line} L${last[0]},${baseline} L${points[0][0]},${baseline} Z`}
                  fill={gradientUrl(`${gradientBase}-${si}`)}
                  stroke="none"
                />
              ) : null}
              <path
                className="chart-line"
                d={line}
                stroke={seriesColor(si)}
                strokeDasharray={dashFor(si) || undefined}
              />
              <circle cx={last[0]} cy={last[1]} r={3.5} fill={seriesColor(si)} stroke="var(--surface-0)" strokeWidth={2} />
              {/* Direct label on the final point: identity without relying on colour. */}
              {!(si === 0 && annotation?.index === valid[valid.length - 1].i) ? <text data-value-label={valid[valid.length - 1].i} className="chart-label" x={W - pad.right + 8} y={last[1] + 4} fill={seriesColor(si)}>
                {formatNumber(lastValue)}
              </text> : null}
              {hoverIndex !== null && finite(rows[hoverIndex][s.field]) !== null ? (
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
        <PointNote annotation={annotation} x={annotation ? xAt(annotation.index) : 0}
          y={annotation ? yAt(annotation.value) : 0} width={W} />
       </svg>
       <Legend items={[...legend, ...(comparison && refs.length ? [{
         label: comparison.label, color: "var(--series-1)", dash: "7 5",
       }] : [])]} />
      <Tooltip tip={tip} />
    </div>
  );
}

interface BarProps extends StoryProps {
  rows: Record<string, unknown>[];
  categoryField: string;
  series: { label: string; field: string }[];
}

/** A bar rounded at the top only, so it still sits squarely on the axis. */
function barPath(x: number, y: number, w: number, h: number, r: number): string {
  if (h <= 0) return "";
  const radius = Math.min(r, w / 2, h);
  return (
    `M${x},${y + h} V${y + radius} Q${x},${y} ${x + radius},${y} ` +
    `H${x + w - radius} Q${x + w},${y} ${x + w},${y + radius} V${y + h} Z`
  );
}

export function BarChart({ rows, categoryField, series, comparison, annotation, lowerIsBetter }: BarProps) {
  const [tip, setTip] = useState<Tip | null>(null);
  const [hoverRow, setHoverRow] = useState<number | null>(null);
  const [box, W] = useWidth(720);
  const nums = series.flatMap(s => rows.flatMap(r => finite(r[s.field]) === null ? [] : [r[s.field] as number]));
  if (!nums.length) return <p className="empty">No values for this period. Try a different filter.</p>;

  const angled = rows.some(r => String(r[categoryField] ?? "").length * 7 > (W - 64) / rows.length);
  const H = angled ? 320 : 280;
  const pad = { top: 64, right: 16, bottom: angled ? 96 : 34, left: 48 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const refs = comparison ? rows.flatMap(r => finite(r[comparison.field]) === null ? [] : [r[comparison.field] as number]) : [];
  const ticks = niceTicks(Math.min(0, ...nums, ...refs), Math.max(0, ...nums, ...refs));
  const yMin = ticks[0], yMax = ticks[ticks.length - 1];
  const span = yMax - yMin || 1;

  const groupW = plotW / rows.length;
  // Bars stay slim on wide charts: a 120px slab per category reads as a block.
  const inner = Math.max(2, Math.min(groupW - 12, 56 * series.length));
  const barW = Math.max(6, inner / series.length - 2); // 2px surface gap
  const yAt = (v: number) => pad.top + plotH - ((v - yMin) / span) * plotH;
  // Values on the bars when they fit; otherwise the tooltip carries them.
  const labelled = series.length === 1 && rows.length <= 12;

  return (
    <div ref={box}>
      <svg
        className="chart"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Bar chart of ${series.map((s) => s.label).join(", ")} by ${categoryField}`}
        onMouseLeave={() => {
          setTip(null);
          setHoverRow(null);
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

        {rows.map((row, ri) => {
          const groupX = pad.left + groupW * ri + (groupW - (barW + 2) * series.length + 2) / 2;
          return (
            <g
              key={ri}
              className="bar-group"
              opacity={hoverRow === null || hoverRow === ri ? 1 : 0.45}
              onMouseEnter={() => setHoverRow(ri)}
            >
              <text data-category-label={ri} className="chart-axis"
                x={pad.left + groupW * ri + groupW / 2} y={H - pad.bottom + 18}
                transform={angled ? `rotate(-35 ${pad.left + groupW * ri + groupW / 2} ${H - pad.bottom + 18})` : undefined}
                textAnchor={angled ? "end" : "middle"}>
                <title>{String(row[categoryField] ?? "")}</title>{axisLabel(row[categoryField], angled ? Math.min(22, Math.floor((groupW * ri + groupW / 2 + 40) / 5.8)) : Math.max(3, Math.floor(groupW / 7)))}
              </text>
              {series.map((s, si) => {
                const value = finite(row[s.field]);
                if (value === null) return null;
                const x = groupX + si * (barW + 2);
                const y = yAt(value);
                const ref = comparison ? finite(row[comparison.field]) : null;
                const bad = ref !== null && lowerIsBetter != null &&
                  (lowerIsBetter ? value > ref : value < ref);
                const color = bad ? "var(--critical)" : seriesColor(si);
                return (
                  <g key={s.field}>
                    <path
                      d={barPath(x, Math.min(y, yAt(0)), barW, Math.abs(yAt(0) - y), 5)}
                      data-bar-tone={bad ? "bad" : "neutral"}
                      fill={color}
                      stroke={annotation?.index === ri && si === 0 ? "var(--ink-1)" : undefined}
                      strokeWidth={annotation?.index === ri && si === 0 ? 2 : undefined}
                      onMouseMove={(event) =>
                        setTip({
                          x: event.clientX,
                          y: event.clientY,
                          rows: [
                            { label: String(row[categoryField] ?? ""), value: "" },
                            { label: s.label, value: formatNumber(value), color },
                          ],
                        })
                      }
                    />
                    {labelled && !(si === 0 && annotation?.index === ri) ? (
                      <text data-value-label={ri} className="chart-label" x={x + barW / 2} y={y + (value < 0 ? 14 : -6)} textAnchor="middle">
                        {formatNumber(value)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
            </g>
          );
        })}
        {comparison ? rows.map((row, i) => {
          const value = finite(row[comparison.field]);
          if (value === null) return null;
          const x = pad.left + groupW * i;
          return <g key={i} data-comparison={comparison.kind}>
            <title>{`${comparison.label}: ${formatNumber(value)}`}</title>
            {comparison.kind === "target" ? <line x1={x + 4} x2={x + groupW - 4}
              y1={yAt(value)} y2={yAt(value)} stroke="var(--series-1)" strokeWidth={2} strokeDasharray="7 5" />
              : <rect x={x + groupW / 2 - 20} width={40} y={Math.min(yAt(value), yAt(0))}
                height={Math.max(1, Math.abs(yAt(value) - yAt(0)))} fill="none"
                stroke="var(--series-1)" strokeWidth={1.5} strokeDasharray="7 5" opacity={0.35} />}
          </g>;
        }) : null}
        <PointNote annotation={annotation}
          x={annotation ? pad.left + groupW * (annotation.index + 0.5) : 0}
          y={annotation ? yAt(annotation.value) : 0} width={W} />
        <TargetLabel comparison={comparison} refs={refs} width={W} />
      </svg>
      <Legend items={[...series.map((s, i) => ({ label: s.label, color: seriesColor(i) })),
        ...(comparison && refs.length ? [{ label: comparison.label, color: "var(--series-1)", dash: "7 5" }] : [])]} />
      <Tooltip tip={tip} />
    </div>
  );
}

/** Past this many slices the rest fold into "Other": thin slices are unreadable. */
const MAX_SLICES = 6;

/** Share of a whole. Total in the middle, exact values and shares in the list. */
export function DonutChart({
  rows,
  categoryField,
  valueField,
  unit,
}: {
  rows: Record<string, unknown>[];
  categoryField: string;
  valueField: string;
  unit?: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const slices = rows
    .map((r) => ({ label: String(r[categoryField] ?? ""), value: Math.max(0, Number(r[valueField]) || 0) }))
    .filter((s) => s.value > 0)
    .sort((a, b) => b.value - a.value);
  if (!slices.length) return <p className="empty">No data yet.</p>;
  if (slices.length > MAX_SLICES) {
    const rest = slices.splice(MAX_SLICES - 1);
    slices.push({ label: "Other", value: rest.reduce((sum, s) => sum + s.value, 0) });
  }
  const total = slices.reduce((sum, s) => sum + s.value, 0);

  const size = 200;
  const r = 78;
  const stroke = 24;
  const circumference = 2 * Math.PI * r;
  const focus = active === null ? null : slices[active];
  const starts = slices.map((_, i) =>
    slices.slice(0, i).reduce((sum, s) => sum + (s.value / total) * circumference, 0),
  );

  return (
    <div className="donut">
      <svg
        className="donut-chart"
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`Share of ${valueField} by ${categoryField}`}
        onMouseLeave={() => setActive(null)}
      >
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={stroke} />
        {slices.map((slice, i) => {
          const length = (slice.value / total) * circumference;
          // A small gap between slices, so adjacent hues never touch.
          const gap = slices.length > 1 ? Math.min(3, length / 2) : 0;
          return (
            <circle
              key={slice.label}
              className="donut-slice"
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={seriesColor(i)}
              strokeWidth={active === i ? stroke + 6 : stroke}
              strokeDasharray={`${length - gap} ${circumference - length + gap}`}
              strokeDashoffset={-starts[i]}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              onMouseEnter={() => setActive(i)}
            />
          );
        })}
        <text x={size / 2} y={size / 2 + 4} textAnchor="middle" className="donut-total">
          {formatNumber(focus ? focus.value : total)}
        </text>
        <text x={size / 2} y={size / 2 + 24} textAnchor="middle" className="donut-caption">
          {focus ? focus.label : unit ? `Total ${unit}` : "Total"}
        </text>
      </svg>
      <ul className="donut-legend">
        {slices.map((slice, i) => (
          <li
            key={slice.label}
            className={active === i ? "is-active" : undefined}
            onMouseEnter={() => setActive(i)}
            onMouseLeave={() => setActive(null)}
          >
            <span className="legend-mark" style={{ background: seriesColor(i) }} />
            <span className="donut-label">{slice.label}</span>
            <span className="donut-value">{formatNumber(slice.value)}</span>
            <span className="donut-share">{((slice.value / total) * 100).toFixed(0)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
