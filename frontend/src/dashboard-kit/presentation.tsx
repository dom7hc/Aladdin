// The HTML presentation: 16:9 slides built from a stored presentation input.
//
// Every figure goes through the same heroFact/chartFacts path the dashboard
// renders with, on the same captured payloads, so a slide can never show a
// number the dashboard does not. Copy comes from the user's requirements; when
// a requirement is missing the slide is dropped rather than padded.

import { BarChart, DonutChart, LineChart } from "./charts";
import { formatNumber } from "./format";
import { chartDirection, chartFacts, heroFact } from "./insights";
import type { HeroFact } from "./insights";
import { asRows } from "./normalize";
import type { DashboardSnapshot, DashboardSpec, Payload, Widget } from "./types";

export interface PresentationInput {
  schemaVersion: 1;
  rendererVersion: string;
  spec: DashboardSpec;
  snapshot: DashboardSnapshot;
  theme: { css: string; attributes: Record<string, string> };
  copy: {
    problem?: string;
    targetUsers?: string[];
    successCriteria?: string[];
    features?: string[];
    mainWorkflow?: string[];
  };
}

export const RENDERER_VERSION = "dashboard-kit-014-v1";
const CHART_KINDS = new Set(["line", "bar", "donut"]);
const MAX_CHART_SLIDES = 4;

export type Slide =
  | { kind: "title"; title: string; audience: string | null }
  | { kind: "problem"; problem: string; audience: string[] }
  | { kind: "headline"; label: string; unit?: string; fact: HeroFact }
  | { kind: "chart"; widget: Widget; title: string }
  | { kind: "capabilities"; items: string[] }
  | { kind: "ask"; ask: string; who: string | null };

/** A requirement worth a slide: real words, not a placeholder. */
function meaningful(text: unknown): text is string {
  return typeof text === "string" && text.trim().split(/\s+/).length >= 3;
}

function clean(list: unknown): string[] {
  return Array.isArray(list) ? list.filter(meaningful).map(s => s.trim()) : [];
}

function hasData(widget: Widget, payload: Payload | undefined): boolean {
  return asRows(payload).length > 0 && CHART_KINDS.has(widget.kind);
}

const human = (field: string) => field.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]+/g, " ").toLowerCase();

/**
 * What the dashboard lets people do, derived from what it actually contains so
 * every line is true. Requirement features only top up a short list.
 */
function capabilities(spec: DashboardSpec, data: Record<string, Payload>, features: string[]): string[] {
  const items: string[] = [];
  if (spec.hero?.comparison)
    items.push(`Track ${spec.hero.label.toLowerCase()} against the ${spec.hero.comparison.label.toLowerCase()}`);
  const bar = spec.widgets.find(w => w.kind === "bar");
  if (bar && bar.kind === "bar") {
    const names = asRows(data[bar.endpoint]).map(r => r[bar.categoryField]).filter(v => v != null).map(String);
    const shown = names.slice(0, 3);
    const list = shown.length < 2 ? `each ${human(bar.categoryField)}`
      : names.length > 3 ? `${shown.join(", ")} and more`
      : `${shown.slice(0, -1).join(", ")} and ${shown.at(-1)}`;
    items.push(`Compare ${bar.series[0]?.label.toLowerCase() ?? "values"} across ${list}`);
  }
  if (spec.filters?.length)
    items.push(`Filter by ${spec.filters.slice(0, 2).map(f => f.label.toLowerCase()).join(" and ")}`);
  if (spec.widgets.some(w => w.kind === "table"))
    items.push("Search the detail and download it as CSV");
  for (const feature of features) if (items.length < 3) items.push(feature);
  return items.slice(0, 3);
}

export function buildSlides(input: PresentationInput): Slide[] {
  const { spec, snapshot, copy } = input;
  const data = snapshot.endpoints;
  const users = clean(copy.targetUsers);
  const slides: Slide[] = [{ kind: "title", title: spec.title, audience: users[0] ?? null }];
  if (meaningful(copy.problem)) slides.push({ kind: "problem", problem: copy.problem.trim(), audience: users.slice(0, 3) });
  if (spec.hero)
    slides.push({ kind: "headline", label: spec.hero.label, unit: spec.hero.unit, fact: heroFact(spec.hero, data, spec.widgets) });
  for (const widget of spec.widgets) {
    if (slides.filter(s => s.kind === "chart").length >= MAX_CHART_SLIDES) break;
    const payload = data[widget.endpoint];
    if (!hasData(widget, payload)) continue;
    const reference = widget.kind !== "stat" && "comparison" in widget && widget.comparison
      ? data[widget.comparison.endpoint] : undefined;
    const facts = chartFacts(widget, payload, reference);
    slides.push({ kind: "chart", widget, title: facts.title });
  }
  const caps = capabilities(spec, data, clean(copy.features));
  if (caps.length) slides.push({ kind: "capabilities", items: caps });
  const ask = clean(copy.successCriteria)[0];
  slides.push({
    kind: "ask",
    ask: ask ?? "Review this dashboard with the people who will use it, and agree how often it should be refreshed.",
    who: users[0] ?? null,
  });
  return slides;
}

function ChartBody({ widget, data, lowerIsBetter }: {
  widget: Widget; data: Record<string, Payload>; lowerIsBetter?: boolean | null;
}) {
  const payload = data[widget.endpoint];
  const reference = "comparison" in widget && widget.comparison ? data[widget.comparison.endpoint] : undefined;
  const facts = chartFacts(widget, payload, reference);
  const comparison = facts.comparison ? { ...facts.comparison, field: "__reference" } : undefined;
  if (widget.kind === "line")
    return <LineChart rows={facts.rows} xField={widget.xField} series={widget.series}
      comparison={comparison} annotation={facts.annotation} />;
  if (widget.kind === "bar")
    return <BarChart rows={facts.rows} categoryField={widget.categoryField} series={widget.series}
      comparison={comparison} annotation={facts.annotation} lowerIsBetter={lowerIsBetter} />;
  if (widget.kind === "donut")
    return <DonutChart rows={asRows(payload)} categoryField={widget.categoryField}
      valueField={widget.valueField} unit={widget.unit} />;
  return null;
}

function Footer({ input, index, total }: { input: PresentationInput; index: number; total: number }) {
  const sample = input.snapshot.provenance?.kind === "sample";
  const captured = new Date(input.snapshot.capturedAt);
  const when = Number.isNaN(captured.getTime()) ? "" :
    captured.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  return <footer className="slide-footer">
    <span>{input.spec.title}</span>
    <span>{[sample ? "Sample data" : "Your data", when && `snapshot ${when}`].filter(Boolean).join(" · ")}</span>
    <span className="slide-number">{index + 1} / {total}</span>
  </footer>;
}

function SlideView({ slide, input }: { slide: Slide; input: PresentationInput }) {
  const data = input.snapshot.endpoints;
  const sample = input.snapshot.provenance?.kind === "sample";
  switch (slide.kind) {
    case "title":
      return <div className="slide-body">
        {sample && <span className="slide-pill">Sample data</span>}
        <h1>{slide.title}</h1>
        {slide.audience && <p className="slide-lede">For {slide.audience}</p>}
        {input.snapshot.scope && <p className="slide-scope">{input.snapshot.scope}</p>}
      </div>;
    case "problem":
      return <div className="slide-body">
        <p className="slide-kicker">The problem</p>
        <h2 className="slide-statement">{slide.problem}</h2>
        {slide.audience.length > 0 && <p className="slide-lede">Who it helps: {slide.audience.join(" · ")}</p>}
      </div>;
    case "headline": {
      const f = slide.fact;
      return <div className="slide-body slide-headline">
        <div className="slide-headline-main">
          <p className="slide-kicker">{slide.label}</p>
          <p className="slide-hero"><span className="slide-hero-value">{f.valueText}</span>
            {slide.unit && <span className="slide-hero-unit">{slide.unit}</span>}</p>
          {f.deltaText && <p className={`slide-delta tone-${f.tone}`}>
            {f.deltaText}{f.tone !== "neutral" && ` · ${f.tone === "good" ? "better" : "worse"}`}
            <span className="slide-delta-vs"> {f.comparisonText}</span></p>}
          <p className="slide-insight">{f.insight}</p>
        </div>
        {f.supporting.length > 0 && <div className="slide-supporting">
          {f.supporting.slice(0, 3).map(s => <div className="slide-tile" key={s.label}>
            <p className="slide-tile-label">{s.note ? `${s.note} · ${s.label}` : s.label}</p>
            <p className="slide-tile-value">{formatNumber(s.value)}{s.unit && <span> {s.unit}</span>}</p>
          </div>)}
        </div>}
      </div>;
    }
    case "chart":
      return <div className="slide-body slide-chart">
        <h2>{slide.title}</h2>
        <div className="slide-plot">
          <ChartBody widget={slide.widget} data={data} lowerIsBetter={chartDirection(input.spec, slide.widget)} />
        </div>
      </div>;
    case "capabilities":
      return <div className="slide-body">
        <p className="slide-kicker">What you can do with it</p>
        <ol className="slide-list">{slide.items.map(item => <li key={item}>{item}</li>)}</ol>
      </div>;
    case "ask":
      return <div className="slide-body slide-ask">
        <p className="slide-kicker">Next step</p>
        <h2 className="slide-statement">{slide.ask}</h2>
        {slide.who && <p className="slide-lede">With {slide.who}</p>}
      </div>;
  }
}

export function PresentationSlides({ input }: { input: PresentationInput }) {
  const slides = buildSlides(input);
  return <main className="deck" aria-label={`${input.spec.title} presentation`}>
    {slides.map((slide, i) => (
      <section className={`slide slide-${slide.kind}`} key={i} data-slide={i + 1}
        aria-label={`Slide ${i + 1} of ${slides.length}`}>
        <SlideView slide={slide} input={input} />
        <Footer input={input} index={i} total={slides.length} />
      </section>
    ))}
  </main>;
}
