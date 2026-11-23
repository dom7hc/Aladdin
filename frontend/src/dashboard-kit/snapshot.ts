import type { DashboardSnapshot, DashboardSpec, Payload } from "./types";

function finiteJson(value: unknown): boolean {
  if (typeof value === "number") return Number.isFinite(value);
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (Array.isArray(value)) return value.every(finiteJson);
  return typeof value === "object" && Object.values(value).every(finiteJson);
}

/** Caller supplies the complete validated endpoint list; clone freezes scope. */
export function makeSnapshot(
  spec: DashboardSpec, paths: string[], endpoints: Record<string, Payload>,
  specHash: string, capturedAt: string,
): DashboardSnapshot {
  if (!/^[a-f0-9]{64}$/.test(specHash) || !Number.isFinite(Date.parse(capturedAt)))
    throw new Error("Invalid snapshot identity");
  if (paths.some(p => !(p in endpoints))) throw new Error("Missing snapshot endpoint");
  if (!finiteJson(endpoints)) throw new Error("Snapshot requires finite JSON");
  if (Object.values(endpoints).some(p => p === null || typeof p !== "object"))
    throw new Error("Invalid snapshot payload");
  return structuredClone({
    schemaVersion: 1, endpoints, specHash, capturedAt,
    scope: "Initial generation / default filters",
    provenance: spec.provenance ?? { kind: "unknown" },
  });
}
