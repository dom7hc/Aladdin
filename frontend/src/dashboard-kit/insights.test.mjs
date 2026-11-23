import test from "node:test";
import assert from "node:assert/strict";
import { heroFact, chartFacts, alignComparison } from "./insights.ts";

const comparison = { kind: "target", label: "Sample target", endpoint: "/api/ref", field: "target", unit: "days" };
const hero = { id: "hero", label: "Time to hire", endpoint: "/api/metrics", field: "actual",
  unit: "days", lowerIsBetter: true, minSamples: 2, comparison };
const fact = (actual, target, extra = {}, binding = hero) =>
  heroFact(binding, { "/api/metrics": { actual, sampleCount: 12, ...extra }, "/api/ref": { target } });

test("actual minus reference, explicit direction and named comparison", () => {
  const f = fact(54, 45);
  assert.equal(f.delta, 9);
  assert.equal(f.relativePercent, 20);
  assert.equal(f.tone, "bad");
  assert.match(f.comparisonText, /Sample target 45 days/);
  assert.match(f.insight, /9 days above Sample target/);
  assert.ok(f.insight.split(/\s+/).length <= 20);
  assert.equal(fact(40, 45).tone, "good");
  assert.equal(fact(45, 45).tone, "neutral");
  assert.equal(fact(54, 45, {}, { ...hero, lowerIsBetter: null }).tone, "neutral");
});
test("percentage points are not relative percent", () => {
  const f = fact(4, 3, {}, { ...hero, unit: "%", comparison: { ...comparison, unit: "%" } });
  assert.equal(f.deltaText, "+1 pp");
  assert.equal(f.relativePercent, null);
  assert.match(f.insight, /1 percentage points above/);
});
test("zero and negative reference never imply a relative percentage", () => {
  for (const reference of [0, -10]) {
    const f = fact(5, reference);
    assert.equal(f.relativePercent, null);
    assert.equal(f.delta, 5 - reference);
    assert.ok(!f.comparisonText.includes("%"));
  }
});
test("missing, nonfinite, tiny and no-comparison cases stay truthful", () => {
  for (const value of [null, undefined, "", "8", NaN, Infinity])
    assert.equal(fact(value, 4).actual, null);
  for (const value of [null, NaN, Infinity]) {
    assert.equal(fact(8, value).reference, null);
    assert.equal(fact(8, value).tone, "neutral");
  }
  for (const count of [0, 1]) {
    const f = fact(8, 4, { sampleCount: count });
    assert.equal(f.tone, "neutral");
    assert.match(f.insight, /Too few/);
  }
  assert.equal(fact(0, 0).tone, "neutral");
  assert.equal(fact(8, 4, {}, { ...hero, comparison: undefined }).delta, null);
  assert.equal(fact(8, 4, {}, { ...hero, comparison: { ...comparison, unit: "USD" } }).reference, null);
  assert.equal(heroFact(hero, {}).actual, null);
});
const widget = { kind: "bar", id: "chart", title: "Cost", categoryField: "label", unit: "days",
  series: [{ label: "Days", field: "actual" }], comparison: { ...comparison, keyField: "label" } };
test("reference rows align by keys, not positions, ambiguous/missing keys do not match", () => {
  const rows = [{ label: "A", actual: 8 }, { label: "B", actual: 3 }];
  assert.deepEqual(alignComparison(rows, [{ label: "B", target: 2 }, { label: "A", target: 6 }], widget.comparison), [6, 2]);
  assert.deepEqual(alignComparison(rows, [{ label: "A", target: 2 }, { label: "A", target: 3 }], widget.comparison), [null, null]);
  assert.deepEqual(alignComparison(rows, [{ target: 2 }], widget.comparison), [null, null]);
  assert.deepEqual(alignComparison(rows, { target: 4 }, comparison), [4, 4]);
});
test("one deterministic annotation and computed takeaway, ties stable by label", () => {
  const rows = [{ label: "Z", actual: 8 }, { label: "A", actual: 8 }, { label: "B", actual: 2 }];
  const f = chartFacts(widget, rows, [{ label: "Z", target: 5 }, { label: "A", target: 5 }, { label: "B", target: 2 }]);
  assert.equal(f.annotation.label, "A");
  assert.equal(f.annotation.value, 8);
  assert.match(f.title, /A/);
  assert.match(f.title, /3 days above Sample target/);
  assert.equal(f.rows[0].__reference, 5);
});
test("single row, all zero, null and infinite series use neutral titles without invented zeros", () => {
  for (const rows of [[], [{ label: "A", actual: 3 }], [{ label: "A", actual: 0 }, { label: "B", actual: 0 }],
    [{ label: "A", actual: null }, { label: "B", actual: Infinity }]]) {
    const f = chartFacts(widget, rows);
    assert.equal(f.annotation, null);
    assert.ok(!/highest|lowest|better|worse/.test(f.title));
  }
});
test("prior period and lower extremes can win salience; no causal language", () => {
  const rows = [{ label: "A", actual: 1 }, { label: "B", actual: 20 }];
  const ref = [{ label: "B", target: 20 }, { label: "A", target: 50 }];
  const f = chartFacts({ ...widget, comparison: { ...widget.comparison, kind: "prior", label: "Last period" } }, rows, ref);
  assert.equal(f.annotation.label, "A");
  assert.match(f.title, /49 days below Last period/);
  assert.ok(!/because|driven by|caused/.test(f.title));
});
