import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { buildSlides, PresentationSlides } from "./presentation.tsx";
import { buildStandaloneHtml, escapeHtml, rootAttributes, safeStyle, CSP } from "./export.ts";
import { chartFacts, heroFact } from "./insights.ts";
globalThis.CSS ??= { escape: value => value.replace(/:/g, "\\:") };

const fixture = () => JSON.parse(readFileSync(new URL("./fixtures/presentation-input.json", import.meta.url), "utf8"));
const render = input => renderToStaticMarkup(React.createElement(PresentationSlides, { input }));

test("slide order follows the art direction: title, problem, headline, charts, capabilities, ask", () => {
  const kinds = buildSlides(fixture()).map(s => s.kind);
  assert.deepEqual(kinds, ["title", "problem", "headline", "chart", "chart", "capabilities", "ask"]);
});

test("every headline and chart figure equals the dashboard's own computation", () => {
  const input = fixture();
  const data = input.snapshot.endpoints;
  const html = render(input);
  const hero = heroFact(input.spec.hero, data, input.spec.widgets);
  assert.ok(html.includes(hero.valueText), "hero value");
  assert.ok(html.includes(escapeHtml(hero.deltaText)), "hero delta");
  assert.ok(html.includes(escapeHtml(hero.insight)), "hero insight");
  for (const widget of input.spec.widgets.filter(w => w.kind === "bar" || w.kind === "line")) {
    const reference = widget.comparison ? data[widget.comparison.endpoint] : undefined;
    const facts = chartFacts(widget, data[widget.endpoint], reference);
    assert.ok(html.includes(escapeHtml(facts.title)), `chart title ${widget.id}`);
    if (facts.annotation) assert.ok(html.includes(escapeHtml(facts.annotation.text)), `annotation ${widget.id}`);
  }
  assert.ok(!html.includes("NaN") && !html.includes("undefined"));
});

test("sample data is labelled on the title slide and every footer", () => {
  const html = render(fixture());
  const slides = buildSlides(fixture()).length;
  assert.match(html, /slide-pill">Sample data/);
  assert.equal((html.match(/Sample data · snapshot/g) ?? []).length, slides);
});

test("placeholder requirements shorten the deck instead of padding it", () => {
  const input = fixture();
  input.copy = { problem: "p", targetUsers: [], successCriteria: [], features: [], mainWorkflow: [] };
  const kinds = buildSlides(input).map(s => s.kind);
  assert.ok(!kinds.includes("problem"));
  assert.equal(kinds.at(-1), "ask");
  assert.ok(render(input).length > 0);
});

test("no chartable data gives title, headline and the closing slides, never an empty slide", () => {
  const input = fixture();
  for (const w of input.spec.widgets) if (w.kind !== "stat") input.snapshot.endpoints[w.endpoint] = [];
  const kinds = buildSlides(input).map(s => s.kind);
  assert.ok(!kinds.includes("chart"));
  assert.ok(kinds.includes("headline"));
});

test("hostile text from requirements or payloads cannot become markup", () => {
  const input = fixture();
  input.spec.title = '</title><script>alert(1)</script>';
  input.copy.problem = '<img src=x onerror=alert(1)> overspend is noticed far too late';
  const body = render(input);
  assert.ok(!body.includes("<script>") && !body.includes("<img"));
  const page = buildStandaloneHtml({ title: input.spec.title, bodyHtml: body, themeCss: "a{}</style><script>x</script>",
    attributes: { "data-theme": '"><script>', onload: "alert(1)" } });
  assert.equal((page.match(/<script>/g) ?? []).length, 1, "only the navigation script");
  assert.ok(!page.includes("onload="));
  assert.ok(!safeStyle("x</style>").includes("</style>"));
  assert.ok(!rootAttributes({ "data-mode": '"x' }).includes('""x'));
});

test("the file makes no network requests: strict CSP and no external URLs", () => {
  const page = buildStandaloneHtml({ title: "t", bodyHtml: render(fixture()), themeCss: fixture().theme.css, attributes: {} });
  assert.ok(page.includes(CSP));
  assert.match(CSP, /default-src 'none'/);
  assert.ok(!/(src|href)=["']?https?:/i.test(page));
  assert.ok(!/@import|url\(\s*["']?https?:/i.test(page));
});

test("capabilities are derived from the dashboard and read naturally", () => {
  const slide = buildSlides(fixture()).find(s => s.kind === "capabilities");
  assert.ok(slide.items.some(i => /^Compare .+ across .+/.test(i)));
  assert.ok(slide.items.every(i => !/ and .+ and more/.test(i) && !/seeded|KPI overview/i.test(i)));
});
