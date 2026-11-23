/** Pure, shared facts. Text never infers causes or guesses favourable direction. */
import type { Comparison, DashboardSpec, HeroBinding, Payload, Widget } from "./types";
import { asObject, asRows } from "./normalize";
import { formatNumber } from "./format";

export function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
const rounded = (value: number) => Number(value.toPrecision(12));
const amount = (value: number, unit?: string) => `${formatNumber(value)}${unit ? ` ${unit}` : ""}`;
const short = (text: string, limit = 32) => text.length > limit ? `${text.slice(0, limit - 1)}…` : text;

/** Strict ISO calendar dates: no timezone shifts or invalid-day rollover. */
export function monthLabel(value: unknown, abbreviated = false): string | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00Z`);
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return null;
  return date.toLocaleDateString("en-US", { month: abbreviated ? "short" : "long", timeZone: "UTC" });
}
const proseComparison = (label: string) => label === "Sample target" ? "the sample target" : short(label);
function monthlyRows(widget: Widget, rows: Record<string, unknown>[]): boolean {
  if (widget.kind !== "line" || rows.length < 2) return false;
  const months = rows.map(row => {
    const date = String(row[widget.xField]);
    return monthLabel(date) && finite(row[widget.series[0]?.field]) !== null
      ? Number(date.slice(0, 4)) * 12 + Number(date.slice(5, 7)) : null;
  });
  return months.every((m, i) => m !== null && (i === 0 || m === months[i - 1]! + 1));
}
export interface SupportingFact { label: string; value: number; unit?: string; note: string }

function heroContext(binding: HeroBinding, data: Record<string, Payload>, widgets: Widget[]) {
  const matching = widgets.filter(w => (w.kind === "line" || w.kind === "bar") &&
    w.unit === binding.unit && w.series.length === 1 && w.series[0].label === binding.label);
  const bar = matching.find(w => w.kind === "bar" && w.comparison?.kind === binding.comparison?.kind &&
    w.comparison?.label === binding.comparison?.label && w.comparison?.unit === binding.unit);
  let driver = "";
  if (bar?.kind === "bar" && bar.comparison) {
    const rows = asRows(data[bar.endpoint]);
    const keys = rows.map(r => r[bar.categoryField]);
    const refs = alignComparison(rows, data[bar.comparison.endpoint], bar.comparison);
    // Partial or duplicate groups cannot establish a largest gap.
    if (rows.length >= 2 && keys.every(k => typeof k === "string" && k.length) &&
      new Set(keys).size === rows.length && refs.every(r => r !== null) &&
      rows.every(r => finite(r[bar.series[0].field]) !== null)) {
      const gaps = rows.map((r, i) => ({ label: String(r[bar.categoryField]),
        delta: rounded(Number(r[bar.series[0].field]) - refs[i]!) }))
        .filter(r => Number.isFinite(r.delta))
        .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta) || a.label.localeCompare(b.label, "en"));
      const top = gaps[0];
      if (top?.delta) driver = `${short(top.label, 18).split(/\s+/).slice(0, 2).join(" ")} has the largest gap (${top.delta > 0 ? "+" : ""}${amount(top.delta, binding.unit === "%" ? "pp" : binding.unit)})`;
    }
  }
  const line = matching.find(w => {
    const rows = asRows(data[w.endpoint]);
    return monthlyRows(w, rows) &&
      finite(rows[rows.length - 1]?.[w.kind === "line" ? w.series[0].field : ""]) === finite(asObject(data[binding.endpoint])[binding.field]);
  });
  const supporting: SupportingFact[] = [];
  let trend = "";
  if (line?.kind === "line") {
    const rows = asRows(data[line.endpoint]);
    const values = rows.map(r => Number(r[line.series[0].field]));
    const changes = values.slice(1).map((v, i) => v - values[i]);
    const up = changes.filter(v => v > 0).length, down = changes.filter(v => v < 0).length;
    trend = up || down ? `${up >= down ? "rose" : "fell"} in ${Math.max(up, down)} of ${changes.length} monthly changes`
      : `was unchanged across ${values.length} months`;
    const peak = values.indexOf(Math.max(...values));
    supporting.push(
      { label: monthLabel(rows[rows.length - 2][line.xField])!, value: values[values.length - 2], unit: binding.unit, note: "Previous month" },
      { label: monthLabel(rows[peak][line.xField])!, value: values[peak], unit: binding.unit, note: `Peak in ${values.length} months` },
    );
  }
  const subject = short(binding.label, 24).split(/\s+/).slice(0, 3).join(" ").toLowerCase();
  return { insight: driver ? `${driver}${trend ? `; ${subject} ${trend}` : ""}.`
    : trend ? `${short(binding.label, 24)} ${trend}.` : "No category or time breakdown available.", supporting };
}

export interface HeroFact {
  id: string;
  actual: number | null;
  reference: number | null;
  delta: number | null;
  relativePercent: number | null;
  sampleCount: number | null;
  tone: "good" | "bad" | "neutral";
  valueText: string;
  deltaText: string;
  comparisonText: string;
  insight: string;
  supporting: SupportingFact[];
}

export function heroFact(binding: HeroBinding, data: Record<string, Payload>, widgets: Widget[] = []): HeroFact {
  const source = asObject(data[binding.endpoint]);
  const actual = finite(source[binding.field]);
  const sampleCount = finite(source.sampleCount);
  const c = binding.comparison;
  const reference = c && c.unit === (binding.unit ?? "")
    ? finite(asObject(data[c.endpoint])[c.field]) : null;
  const rawDelta = actual !== null && reference !== null ? actual - reference : null;
  const delta = rawDelta !== null && Number.isFinite(rawDelta) ? rounded(rawDelta) : null;
  const relative = delta !== null && reference !== null && reference > 0 && binding.unit !== "%"
    ? rounded(delta / reference * 100) : null;
  const relativePercent = relative !== null && Number.isFinite(relative) ? relative : null;
  const tiny = sampleCount !== null && sampleCount < (binding.minSamples ?? 2);
  const tone = delta === null || delta === 0 || tiny || binding.lowerIsBetter == null
    ? "neutral" : (delta < 0) === binding.lowerIsBetter ? "good" : "bad";
  const deltaUnit = binding.unit === "%" ? "pp" : binding.unit;
  const difference = delta === null ? "" : `${delta > 0 ? "+" : ""}${amount(delta, deltaUnit)}`;
  const label = short(binding.label);
  const refLabel = short(c?.label ?? "");
  const context = heroContext(binding, data, widgets);
  let insight = actual === null ? `${label}: no value available.`
    : tiny ? `Too few observations to assess ${label.toLowerCase()}.`
    : context.insight;
  // Bound copy even for a model-supplied, very verbose label; raw labels remain tooltips.
  if (insight.split(/\s+/).length > 20)
    insight = "A longer category or time breakdown is available in the charts.";
  return {
    id: binding.id, actual, reference, delta, relativePercent, sampleCount, tone,
    valueText: actual === null ? "—" : formatNumber(actual),
    deltaText: difference,
    comparisonText: c && reference !== null ? `vs ${refLabel} ${amount(reference, c.unit)}` : "Comparison unavailable",
    insight, supporting: actual === null || tiny ? [] : context.supporting,
  };
}

/** Duplicates are ambiguous, not an excuse to pair records by array position. */
export function alignComparison(
  rows: Record<string, unknown>[], payload: Payload | undefined, comparison: Comparison,
): (number | null)[] {
  if (!comparison.keyField) {
    // A scalar target is valid; a previous-period series must have explicit keys.
    const scalar = comparison.kind === "target" && !Array.isArray(payload)
      ? finite(asObject(payload)[comparison.field]) : null;
    return rows.map(() => scalar);
  }
  const key = comparison.keyField;
  const refs = new Map<unknown, number | null>();
  for (const row of asRows(payload)) {
    if (row[key] == null) continue;
    refs.set(row[key], refs.has(row[key]) ? null : finite(row[comparison.field]));
  }
  const counts = new Map<unknown, number>();
  for (const row of rows) counts.set(row[key], (counts.get(row[key]) ?? 0) + 1);
  return rows.map(row => row[key] != null && counts.get(row[key]) === 1 ? refs.get(row[key]) ?? null : null);
}

export interface Annotation { index: number; label: string; value: number; text: string }
export interface ChartFacts {
  rows: Record<string, unknown>[];
  title: string;
  annotation: Annotation | null;
  comparison?: Comparison;
}

export function chartFacts(widget: Widget, payload?: Payload, reference?: Payload): ChartFacts {
  const rows = asRows(payload);
  const title = "title" in widget ? widget.title : widget.label;
  if (widget.kind !== "line" && widget.kind !== "bar")
    return { rows, title, annotation: null };
  const c = widget.comparison?.unit === (widget.unit ?? "") ? widget.comparison : undefined;
  const aligned = c ? alignComparison(rows, reference, c) : rows.map(() => null);
  const clean = rows.map((row, i) => ({
    ...row,
    ...Object.fromEntries(widget.series.map(s => [s.field, finite(row[s.field])])),
    __reference: aligned[i],
  }));
  const key = widget.kind === "line" ? widget.xField : widget.categoryField;
  const field = widget.series[0]?.field;
  const entries = rows.flatMap((row, index) => {
    const value = finite(row[field]);
    return value === null ? [] : [{ index, label: String(row[key] ?? "Unlabelled"), value }];
  });
  if (entries.length < 2 || entries.every(e => e.value === 0))
    return { rows: clean, title: entries.length ? `${title} · ${entries.length} observations` : "No values for this period", annotation: null, comparison: c };
  const values = entries.map(e => e.value);
  const max = Math.max(...values), min = Math.min(...values);
  // Compare extremes and the largest matched reference difference on a common scale.
  const centre = (max + min) / 2;
  const candidates = entries.map(e => {
    const ref = aligned[e.index];
    const delta = ref === null ? null : rounded(e.value - ref);
    return { ...e, delta, score: Math.max(Math.abs(e.value - centre), delta === null ? 0 : Math.abs(delta)) };
  }).sort((a, b) => b.score - a.score || (a.label < b.label ? -1 : a.label > b.label ? 1 : a.index - b.index));
  const notable = candidates[0];
  const diff = notable.delta;
  const unit = widget.unit === "%" ? "percentage points" : widget.unit;
  const displayLabel = monthLabel(notable.label) ?? short(notable.label);
  let takeaway = diff !== null && c
    ? `${displayLabel} ${diff === 0 ? "matches" : `is ${amount(Math.abs(diff), unit)} ${diff > 0 ? "above" : "below"}`} ${proseComparison(c.label)}`
    : `${short(notable.label)} has ${notable.value === max ? "the highest" : "the lowest"} ${short(widget.series[0].label.toLowerCase())}: ${amount(notable.value, widget.unit)}`;
  if (monthlyRows(widget, rows)) {
    const last = rows.length - 1;
    const finalDelta = aligned[last] === null ? null : Number(rows[last][field]) - aligned[last]!;
    if (c?.kind === "target" && finalDelta !== null && finalDelta !== 0) {
      let start = last;
      while (start > 0 && aligned[start - 1] !== null &&
        Math.sign(Number(rows[start - 1][field]) - aligned[start - 1]!) === Math.sign(finalDelta)) start--;
      if (last > start) takeaway = `${short(widget.series[0].label)} has stayed ${finalDelta > 0 ? "above" : "below"} ${proseComparison(c.label)} since ${monthLabel(rows[start][key])}`;
    } else {
      const change = Number(rows[last][field]) - Number(rows[0][field]);
      takeaway = `${short(widget.series[0].label)} ${change === 0 ? "is unchanged" : `is ${change > 0 ? "up" : "down"} ${amount(Math.abs(change), unit)}`} from ${monthLabel(rows[0][key])} to ${monthLabel(rows[last][key])}`;
    }
  }
  return {
    rows: clean, title: takeaway, comparison: c,
    annotation: { index: notable.index, label: notable.label, value: notable.value,
      text: `${short(monthLabel(notable.label, true) ?? notable.label, 18).split(/\s+/).slice(0, 4).join(" ")} · ${formatNumber(notable.value)}` },
  };
}

/**
 * Whether lower values are better for a chart: only when the chart plots the
 * hero's own metric (same unit and first series label). Any other chart has no
 * known direction, so its bars are never coloured good or bad. Shared by the
 * dashboard and the presentation so both colour the same bars.
 */
export function chartDirection(spec: DashboardSpec, widget: Widget): boolean | null | undefined {
  const hero = spec.hero;
  if (!hero || (widget.kind !== "bar" && widget.kind !== "line")) return undefined;
  return widget.unit === hero.unit && widget.series[0]?.label === hero.label ? hero.lowerIsBetter : undefined;
}
