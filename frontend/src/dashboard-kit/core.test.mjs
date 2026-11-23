import test from "node:test";
import assert from "node:assert/strict";
import { normalizeSpec, endpointsFor, asRows, asObject, trustworthyDelta, boundNumber } from "./normalize.ts";
import { formatNumber } from "./format.ts";
import { makeSnapshot } from "./snapshot.ts";

const legacy = { title: "Orders", layout: "kpi-overview", widgets: [
  { kind: "stat", endpoint: "/api/metrics", label: "Orders", field: "total" },
] };
test("legacy defaults are stable, nonmutating and direction unknown", () => {
  const result = normalizeSpec(legacy);
  assert.deepEqual(normalizeSpec(result), result);
  assert.equal(legacy.schemaVersion, undefined);
  assert.equal(result.hero.lowerIsBetter, null);
  assert.equal(result.provenance.kind, "unknown");
});
test("all bindings enumerated; unsafe paths are fatal", () => {
  const spec = normalizeSpec(legacy);
  spec.hero.comparison = { endpoint: "/api/reference" };
  assert.deepEqual(endpointsFor(spec), ["/api/metrics", "/api/reference"]);
  for (const endpoint of ["/api/../x", "/api/x?x=1", "/api/%20", "//evil", "/api/x\n"])
    assert.throws(() => normalizeSpec({ ...legacy, widgets: [{ ...legacy.widgets[0], endpoint }] }));
});
test("normalization preserves zero, rejects invented numeric nulls", () => {
  const hero = normalizeSpec(legacy).hero;
  assert.equal(boundNumber(hero, { total: 0 }), 0);
  assert.equal(boundNumber(hero, { total: null }), null);
  assert.equal(boundNumber(hero, { total: "12" }), null);
  for (const key of ["items", "rows", "data", "results"])
    assert.deepEqual(asRows({ [key]: [{ x: 2 }] }), [{ x: 2 }]);
  assert.deepEqual(asObject([{ x: 1 }]), { x: 1 });
});
test("formatting is finite, shared and deterministic", () => {
  assert.equal(formatNumber(1280), "1.3k");
  assert.equal(formatNumber(Infinity), "—");
  assert.equal(formatNumber(-1_000_000), "-1.0M");
  assert.equal(trustworthyDelta(null), undefined);
  assert.equal(trustworthyDelta(1000), undefined);
  assert.equal(trustworthyDelta(0), 0);
});
test("snapshot freezes complete finite payloads", () => {
  const spec = normalizeSpec(legacy), data = { "/api/metrics": { total: 3 } };
  const snapshot = makeSnapshot(spec, endpointsFor(spec), data, "a".repeat(64), "2026-11-23T00:00:00Z");
  data["/api/metrics"].total = 99;
  assert.equal(snapshot.endpoints["/api/metrics"].total, 3);
  assert.throws(() => makeSnapshot(spec, endpointsFor(spec), {}, "a".repeat(64), snapshot.capturedAt));
  assert.throws(() => makeSnapshot(spec, endpointsFor(spec), { "/api/metrics": { x: NaN } }, "a".repeat(64), snapshot.capturedAt));
});
