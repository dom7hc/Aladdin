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
  assert.match(f.insight, /No category or time breakdown/);
  assert.ok(f.insight.split(/\s+/).length <= 20);
  assert.equal(fact(40, 45).tone, "good");
  assert.equal(fact(45, 45).tone, "neutral");
  assert.equal(fact(54, 45, {}, { ...hero, lowerIsBetter: null }).tone, "neutral");
});
test("percentage points are not relative percent", () => {
  const f = fact(4, 3, {}, { ...hero, unit: "%", comparison: { ...comparison, unit: "%" } });
  assert.equal(f.deltaText, "+1 pp");
  assert.equal(f.relativePercent, null);
  assert.equal(f.delta, 1);
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
  assert.match(f.title, /3 days above the sample target/);
  assert.equal(f.rows[0].__reference, 5);
});

const trend = { kind: "line", title: "Hiring trend", endpoint: "/api/series", xField: "date",
  unit: "days", series: [{ label: "Time to hire", field: "actual" }],
  comparison: { ...comparison, endpoint: "/api/series", keyField: "date" } };
const driver = { ...widget, endpoint: "/api/groups", series: trend.series,
  comparison: { ...comparison, endpoint: "/api/groups", keyField: "label" } };
const seriesRows = [
  { date: "2026-07-31", actual: 40, target: 45 },
  { date: "2026-08-31", actual: 48, target: 45 },
  { date: "2026-09-30", actual: 50, target: 45 },
  { date: "2026-10-31", actual: 54, target: 45 },
];
const context = { "/api/metrics": { actual: 54, sampleCount: 12 }, "/api/ref": { target: 45 },
  "/api/series": seriesRows, "/api/groups": [{ label: "Engineering", actual: 60, target: 45 },
    { label: "Sales", actual: 48, target: 45 }] };
test("hero adds computed category gap and monthly trend, not a causal claim", () => {
  const f = heroFact(hero, context, [driver, trend]);
  assert.match(f.insight, /Engineering has the largest gap \(\+15 days\)/);
  assert.match(f.insight, /rose in 3 of 3 monthly changes/);
  assert.ok(f.insight.split(/\s+/).length <= 20);
  assert.equal(f.supporting.length, 2);
  assert.equal(f.supporting[0].label, "September");
  assert.equal(f.supporting[0].value, 50);
  assert.ok(!/caused|because|drives/.test(f.insight));
});
test("monthly takeaway names months and continuous target run", () => {
  const f = chartFacts(trend, seriesRows, seriesRows);
  assert.match(f.title, /Time to hire has stayed above the sample target since August/);
  assert.ok(!/2026-/.test(f.title));
});
test("unsorted, duplicate, missing and gapped months do not imply continuous trends", () => {
  for (const rows of [[...seriesRows].reverse(), [...seriesRows, seriesRows[3]],
    [seriesRows[0], seriesRows[2], seriesRows[3]],
    seriesRows.map((r, i) => i === 1 ? { ...r, actual: null } : r)]) {
    const f = heroFact(hero, { ...context, "/api/series": rows }, [trend]);
    assert.ok(!/monthly changes/.test(f.insight));
    assert.ok(!/since/.test(chartFacts(trend, rows, rows).title));
  }
});
test("unrelated metrics and ambiguous categories cannot explain the headline", () => {
  assert.match(heroFact(hero, context, [{ ...driver, unit: "USD" },
    { ...trend, series: [{ label: "Other metric", field: "actual" }] }]).insight,
    /No category or time breakdown/);
  const duplicate = { ...context, "/api/groups": [...context["/api/groups"], context["/api/groups"][0]] };
  assert.match(heroFact(hero, duplicate, [driver]).insight, /No category or time breakdown/);
  assert.match(heroFact(hero, { ...context, "/api/metrics": { actual: 54, sampleCount: 1 } },
    [driver, trend]).insight, /Too few/);
});
test("target equality and mixed directions use neutral exact trend counts", () => {
  const rows = seriesRows.map((r, i) => ({ ...r, actual: [40, 40, 30, 54][i] }));
  const f = heroFact(hero, { ...context, "/api/series": rows }, [trend]);
  assert.match(f.insight, /rose in 1 of 3 monthly changes/);
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
