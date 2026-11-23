/** Pure, shared facts. Text never infers causes or guesses favourable direction. */
import type { Comparison, HeroBinding, Payload, Widget } from "./types";
import { asObject, asRows } from "./normalize";
import { formatNumber } from "./format";

export function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
const rounded = (value: number) => Number(value.toPrecision(12));
const amount = (value: number, unit?: string) => `${formatNumber(value)}${unit ? ` ${unit}` : ""}`;
const short = (text: string, limit = 32) => text.length > limit ? `${text.slice(0, limit - 1)}…` : text;

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
}

export function heroFact(binding: HeroBinding, data: Record<string, Payload>): HeroFact {
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
  let insight = actual === null ? `${label}: no value available.`
    : tiny ? `Too few observations to assess ${label.toLowerCase()}.`
    : delta === null ? `${label} is ${amount(actual, binding.unit)}; no comparison available.`
    : delta === 0 ? `${label} matches ${refLabel}.`
    : `${label} is ${amount(Math.abs(delta), binding.unit === "%" ? "percentage points" : binding.unit)} ${delta > 0 ? "above" : "below"} ${refLabel}.`;
  // Bound copy even for a model-supplied, very verbose label; raw labels remain tooltips.
  if (insight.split(/\s+/).length > 20)
    insight = delta === null ? `Current value: ${amount(actual ?? 0, binding.unit)}.`
      : `${amount(Math.abs(delta), deltaUnit)} ${delta > 0 ? "above" : delta < 0 ? "below" : "from"} the stated comparison.`;
  return {
    id: binding.id, actual, reference, delta, relativePercent, sampleCount, tone,
    valueText: actual === null ? "—" : formatNumber(actual),
    deltaText: difference,
    comparisonText: c && reference !== null ? `vs ${refLabel} ${amount(reference, c.unit)}` : "Comparison unavailable",
    insight,
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
  const takeaway = diff !== null && c
    ? `${short(notable.label)} ${diff === 0 ? "matches" : `is ${amount(Math.abs(diff), unit)} ${diff > 0 ? "above" : "below"}`} ${short(c.label)}`
    : `${short(notable.label)} has ${notable.value === max ? "the highest" : "the lowest"} ${short(widget.series[0].label.toLowerCase())}: ${amount(notable.value, widget.unit)}`;
  return {
    rows: clean, title: takeaway, comparison: c,
    annotation: { index: notable.index, label: notable.label, value: notable.value,
      text: `${short(notable.label, 18).split(/\s+/).slice(0, 4).join(" ")} · ${formatNumber(notable.value)}` },
  };
}
