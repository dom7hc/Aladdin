import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { LineChart, BarChart } from "./charts.tsx";
globalThis.CSS ??= { escape: value => value.replace(/:/g, "\\:") };
const rows = [{ label: "A very long category label that cannot fit", actual: 12, __reference: 10 },
  { label: "B", actual: 8, __reference: 10 }];
const series = [{ label: "Actual", field: "actual" }];
const comparison = { kind: "target", label: "Sample target", field: "__reference" };
const annotation = { index: 0, value: 12, label: rows[0].label, text: "Peak · 12" };
test("line target is a named dashed SVG path and one annotation", () => {
  const html = renderToStaticMarkup(React.createElement(LineChart, { rows, xField: "label", series, comparison, annotation }));
  assert.match(html, /data-comparison="target"/);
  assert.match(html, /Sample target/);
  assert.equal((html.match(/data-annotation=/g) ?? []).length, 1);
  assert.ok(!html.includes("NaN"));
});

test("target labels occupy a reserved top lane, and annotated bars omit plain values", () => {
  const html = renderToStaticMarkup(React.createElement(BarChart,
    { rows, categoryField: "label", series, comparison, annotation, lowerIsBetter: true }));
  assert.match(html, /data-target-label="true"/);
  assert.match(html, /data-bar-tone="bad"/);
  assert.match(html, /data-bar-tone="neutral"/);
  assert.equal((html.match(/data-value-label=/g) ?? []).length, 1);
  const long = renderToStaticMarkup(React.createElement(BarChart,
    { rows: rows.map(r => ({ ...r, label: r.label.repeat(3) })), categoryField: "label", series }));
  assert.match(long, /rotate\(-35/);
  const highGood = renderToStaticMarkup(React.createElement(BarChart,
    { rows, categoryField: "label", series, comparison, annotation, lowerIsBetter: false }));
  assert.equal((highGood.match(/data-bar-tone="bad"/g) ?? []).length, 1);
  const unknown = renderToStaticMarkup(React.createElement(BarChart,
    { rows, categoryField: "label", series, comparison, annotation }));
  assert.ok(!unknown.includes('data-bar-tone="bad"'));
});
test("ISO chart axes become short month names without changing raw tooltips", () => {
  const html = renderToStaticMarkup(React.createElement(LineChart,
    { rows: [{ date: "2026-05-31", actual: 10 }, { date: "2026-06-30", actual: 12 }],
      xField: "date", series }));
  assert.match(html, /<title>2026-05-31<\/title>May/);
  assert.match(html, /<title>2026-06-30<\/title>Jun/);
});
test("bar target, ghost prior, long-label tooltip and negative bar geometry", () => {
  for (const kind of ["target", "prior"]) {
    const html = renderToStaticMarkup(React.createElement(BarChart, { rows: [{ ...rows[0], actual: -2 }, rows[1]],
      categoryField: "label", series, comparison: { ...comparison, kind }, annotation: { ...annotation, value: -2 } }));
    assert.match(html, new RegExp(`data-comparison="${kind}"`));
    assert.match(html, /<title>A very long category label/);
    assert.equal((html.match(/data-annotation=/g) ?? []).length, 1);
    assert.ok(!html.includes("NaN"));
  }
});
test("missing values remain gaps, not invented zero values", () => {
  for (const Component of [LineChart, BarChart]) {
    const html = renderToStaticMarkup(React.createElement(Component, {
      rows: [{ label: "A", actual: null }, { label: "B", actual: Infinity }],
      xField: "label", categoryField: "label", series,
    }));
    assert.match(html, /No values for this period/);
    assert.ok(!html.includes("Infinity"));
  }
});
