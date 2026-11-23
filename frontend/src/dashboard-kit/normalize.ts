import type { DashboardSpec, Payload, HeroBinding } from "./types";

export function safeEndpoint(value: unknown): value is string {
  return typeof value === "string" && /^\/api\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*$/.test(value)
    && !/[\r\n]/.test(value);
}

export function endpointsFor(spec: DashboardSpec): string[] {
  const paths = new Set<string>();
  for (const binding of [...spec.widgets, ...(spec.hero ? [spec.hero] : [])]) {
    for (const endpoint of [binding.endpoint, binding.comparison?.endpoint]) {
      if (endpoint === undefined) continue;
      if (!safeEndpoint(endpoint)) throw new Error("Unsafe dashboard endpoint");
      paths.add(endpoint);
    }
  }
  return [...paths].sort();
}

export function normalizeSpec(input: DashboardSpec): DashboardSpec {
  const spec = structuredClone(input);
  endpointsFor(spec); // Safety is fatal, not a cosmetic default.
  if (spec.schemaVersion !== undefined && spec.schemaVersion !== 2)
    throw new Error("Unsupported dashboard version");
  spec.schemaVersion ??= 2;
  spec.provenance ??= { kind: spec.source ? "upload" : "unknown" };
  spec.widgets.forEach((widget, i) => { widget.id ??= `widget-${i + 1}`; });
  if (spec.hero === undefined) {
    const first = spec.widgets.find(w => w.kind === "stat");
    spec.hero = first?.kind === "stat" ? {
      id: first.id!, label: first.label, endpoint: first.endpoint, field: first.field,
      ...(first.unit !== undefined ? { unit: first.unit } : {}),
      ...(first.lowerIsBetter !== undefined ? { lowerIsBetter: first.lowerIsBetter } : {}),
      ...(first.comparison ? { comparison: first.comparison } : {}),
    } : null;
  }
  if (spec.hero) {
    spec.hero.lowerIsBetter ??= null;
    spec.hero.minSamples ??= 2;
  }
  if (spec.filters) {
    spec.filters = spec.filters.filter(f => f && typeof f.field === "string" && f.field.trim()
      && Array.isArray(f.options) && f.options.length);
    if (!spec.filters.length) delete spec.filters;
  }
  return spec;
}

export function asRows(payload: Payload | undefined): Record<string, unknown>[] {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === "object")
    for (const key of ["items", "rows", "data", "results"]) {
      if (Array.isArray(payload[key])) return payload[key] as Record<string, unknown>[];
    }
  return [];
}

export function asObject(payload: Payload | undefined): Record<string, unknown> {
  return Array.isArray(payload) ? payload[0] ?? {} : payload ?? {};
}

export function trustworthyDelta(value: unknown): number | undefined {
  if (value === null || value === undefined || value === "") return undefined;
  const number = Number(value);
  return Number.isFinite(number) && Math.abs(number) <= 999 ? number : undefined;
}

/** Binding helper does not convert missing/empty values into invented zeroes. */
export function boundNumber(binding: HeroBinding, payload: Payload | undefined): number | null {
  const value = asObject(payload)[binding.field];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
