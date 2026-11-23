// Renders a DashboardSpec. This is the whole frontend of a generated PoC: the
// generator supplies the spec and the backend endpoints, nothing more.

import type { CSSProperties, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { BarChart, DonutChart, LineChart } from "./charts";
import { Icon } from "./icons";
import { asRows, asObject, trustworthyDelta, endpointsFor, normalizeSpec } from "./normalize";
import { chartFacts, heroFact, finite } from "./insights";
import type { DashboardSpec, Widget } from "./types";
import {
  Card,
  DataTable,
  EditableDataTable,
  FilterRail,
  ProgressList,
  RankingList,
  Skeleton,
  StatTile,
  ThemeSwitcher,
  Hero,
  DataState,
} from "./widgets";

type Payload = Record<string, unknown> | Record<string, unknown>[];

/**
 * One fetch per distinct endpoint, shared by every widget that reads it.
 *
 * Each endpoint succeeds or fails on its own: with Promise.all, a single 404
 * blanked every widget on the page, including the ones whose data had loaded.
 */
function useEndpointData(
  endpoints: string[],
  filters: Record<string, string>,
  refresh: number,
) {
  const key = `${endpoints.join("|")}::${JSON.stringify(filters)}::${refresh}`;
  const [data, setData] = useState<Record<string, Payload>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const query = new URLSearchParams(
      Object.entries(filters).filter(([, v]) => v && v !== "All"),
    ).toString();

    Promise.allSettled(
      endpoints.map(async (endpoint) => {
        const url = query ? `${endpoint}?${query}` : endpoint;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`${endpoint} returned ${response.status}`);
        return (await response.json()) as Payload;
      }),
    ).then((results) => {
      if (cancelled) return;
      const loaded: Record<string, Payload> = {};
      const failed: Record<string, string> = {};
      results.forEach((result, i) => {
        if (result.status === "fulfilled") loaded[endpoints[i]] = result.value;
        else
          failed[endpoints[i]] =
            result.reason instanceof Error ? result.reason.message : "Could not load data";
      });
      setData(loaded);
      setErrors(failed);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { data, errors, loading };
}

function WidgetView({
  widget,
  payload,
  error,
  onMutate,
  reference,
  loading,
}: {
  widget: Widget;
  payload: Payload | undefined;
  error?: string;
  onMutate: () => void;
  reference?: Payload;
  loading?: boolean;
}) {
  if (error) {
    // Only this widget is affected; the rest of the dashboard still renders.
    return (
      <Card title={"title" in widget ? widget.title : widget.label}>
        <DataState error onRetry={onMutate} />
      </Card>
    );
  }
  if (loading) return <Card><div className="skeleton-card" aria-label="Loading figures" aria-busy="true" /></Card>;
  if (widget.kind === "stat" ? finite(asObject(payload)[widget.field]) === null : !asRows(payload).length)
    return <Card title={"title" in widget ? widget.title : widget.label}><DataState /></Card>;
  const facts = chartFacts(widget, payload, reference);
  const comparison = facts.comparison ? { ...facts.comparison, field: "__reference" } : undefined;
  switch (widget.kind) {
    case "stat": {
      const source = asObject(payload);
      const trend = source[widget.trendField ?? ""];
      const rawDelta = widget.deltaField !== undefined ? source[widget.deltaField] : undefined;
      return (
        <StatTile
          label={widget.label}
          value={(source[widget.field] as number | string) ?? "—"}
          unit={widget.unit}
          delta={trustworthyDelta(rawDelta)}
          deltaLabel={widget.deltaLabel}
          trend={Array.isArray(trend) ? (trend as number[]) : undefined}
          icon={widget.icon}
          lowerIsBetter={widget.lowerIsBetter}
        />
      );
    }
    case "line":
      return (
        <Card title={facts.title}>
          <LineChart rows={facts.rows} xField={widget.xField} series={widget.series}
            comparison={comparison} annotation={facts.annotation} />
        </Card>
      );
    case "bar":
      return (
        <Card title={facts.title}>
          <BarChart
            rows={facts.rows}
            categoryField={widget.categoryField}
            series={widget.series}
            comparison={comparison}
            annotation={facts.annotation}
          />
        </Card>
      );
    case "donut":
      return (
        <Card title={widget.title}>
          <DonutChart
            rows={asRows(payload)}
            categoryField={widget.categoryField}
            valueField={widget.valueField}
            unit={widget.unit}
          />
        </Card>
      );
    case "progress":
      return (
        <Card title={widget.title}>
          <ProgressList
            rows={asRows(payload)}
            labelField={widget.labelField}
            valueField={widget.valueField}
            targetField={widget.targetField}
            unit={widget.unit}
          />
        </Card>
      );
    case "ranking":
      return (
        <Card title={widget.title}>
          <RankingList
            rows={asRows(payload)}
            labelField={widget.labelField}
            valueField={widget.valueField}
            unit={widget.unit}
          />
        </Card>
      );
    case "table":
      return (
        <Card title={widget.title}>
          {widget.editable ? (
            <EditableDataTable
              endpoint={widget.endpoint}
              rows={asRows(payload)}
              columns={widget.columns}
              title={widget.title}
              onMutate={onMutate}
            />
          ) : (
            <DataTable rows={asRows(payload)} columns={widget.columns} title={widget.title} />
          )}
        </Card>
      );
    default:
      return null;
  }
}

// Narrow widgets read well in a third of the width; wide ones need more.
const NARROW = new Set<Widget["kind"]>(["donut", "progress", "ranking"]);

/** One grid row with explicit column widths, stacking on small screens. */
function Split({ cols, children }: { cols: string; children: ReactNode }) {
  return (
    <div className="row row-split" style={{ "--cols": cols } as CSSProperties}>
      {children}
    </div>
  );
}

/**
 * Pairs widgets into rows so no card is stretched across a whole screen when
 * it holds a donut or a short list: a chart next to a narrow widget gets two
 * thirds, two charts share half each, narrow widgets sit three to a row.
 * Tables always take the full width. Order follows the spec.
 */
function pairRows(widgets: Widget[], node: (w: Widget) => ReactNode): ReactNode[] {
  const queue = [...widgets];
  const rows: ReactNode[] = [];
  const take = (pred: (w: Widget) => boolean) => {
    const index = queue.findIndex(pred);
    return index === -1 ? undefined : queue.splice(index, 1)[0];
  };
  while (queue.length) {
    const first = queue.shift()!;
    const key = rows.length;
    if (first.kind === "table") {
      rows.push(<div key={key}>{node(first)}</div>);
    } else if (NARROW.has(first.kind)) {
      // Narrow widgets group with each other first, from anywhere later in
      // the spec: two lists side by side beat a list stretched across a screen.
      const more: Widget[] = [first];
      for (let next = take((w) => NARROW.has(w.kind)); next; ) {
        more.push(next);
        if (more.length === 3) break;
        next = take((w) => NARROW.has(w.kind));
      }
      if (more.length === 1) {
        // A lone narrow widget borrows the next chart as its partner.
        const partner = take((w) => w.kind === "line" || w.kind === "bar");
        if (partner) {
          rows.push(
            <Split key={key} cols="1fr 2fr">
              {node(first)}
              {node(partner)}
            </Split>,
          );
          continue;
        }
      }
      rows.push(
        <Split key={key} cols={`repeat(${more.length}, 1fr)`}>
          {more.map(node)}
        </Split>,
      );
    } else {
      const narrow = take((w) => NARROW.has(w.kind));
      if (narrow) {
        rows.push(
          <Split key={key} cols="2fr 1fr">
            {node(first)}
            {node(narrow)}
          </Split>,
        );
      } else if (queue[0] && (queue[0].kind === "line" || queue[0].kind === "bar")) {
        rows.push(
          <Split key={key} cols="1fr 1fr">
            {node(first)}
            {node(queue.shift()!)}
          </Split>,
        );
      } else {
        rows.push(<div key={key}>{node(first)}</div>);
      }
    }
  }
  return rows;
}

/** Headline numbers first, then everything else in paired rows. */
function arrange(spec: DashboardSpec, node: (w: Widget) => ReactNode) {
  const stats = spec.widgets.filter((w) => w.kind === "stat" &&
    !(spec.hero?.endpoint === w.endpoint && spec.hero.field === w.field));
  const rest = spec.widgets.filter((w) => w.kind !== "stat");
  return (
    <>
      {stats.length ? <div className="row row-4">{stats.map(node)}</div> : null}
      {pairRows(rest, node)}
    </>
  );
}

/** Where the numbers come from: people trust what they can trace. */
function SourceNote({ source }: { source: NonNullable<DashboardSpec["source"]> }) {
  const n = (value: number) => value.toLocaleString();
  const sampled = source.fileRows > source.rows;
  return (
    <div className="shell-source">
      Data: {source.filename} ·{" "}
      {sampled
        ? `${n(source.rows)} of ${n(source.fileRows)} rows, sampled evenly`
        : `${n(source.rows)} rows`}
    </div>
  );
}

export function Dashboard({ spec: input }: { spec: DashboardSpec }) {
  const spec = useMemo(() => normalizeSpec(input), [input]);
  const [filters, setFilters] = useState<Record<string, string>>({});
  // Bumped by editable tables after a successful mutation; every endpoint then
  // refetches, so stats and charts stay consistent with the table.
  const [refresh, setRefresh] = useState(0);

  // index.html is a platform-owned fallback, so its <title> is generic. The
  // browser tab should name the dashboard, not say "PoC".
  useEffect(() => {
    if (spec.title) document.title = spec.title;
  }, [spec.title]);
  // The look (shape, depth, density) from looks.css. The platform resolved it
  // to a known id; an absent one keeps theme.css's defaults.
  const look = spec.designSystem?.style;
  useEffect(() => {
    if (look) document.documentElement.setAttribute("data-look", look);
  }, [look]);
  const endpoints = useMemo(
    () => endpointsFor(spec),
    [spec],
  );
  const { data, errors, loading } = useEndpointData(endpoints, filters, refresh);

  // Each widget sits in a cell carrying its position, which staggers the
  // entrance animation in theme.css.
  const node = (widget: Widget) => (
    <div
      className="cell"
      key={`${widget.kind}-${"title" in widget ? widget.title : widget.label}`}
      style={{ "--i": Math.min(2.5, spec.widgets.indexOf(widget) + 1) } as CSSProperties}
    >
      <WidgetView
        widget={widget}
        payload={data[widget.endpoint]}
        error={errors[widget.endpoint]}
        onMutate={() => setRefresh((r) => r + 1)}
        reference={widget.comparison ? data[widget.comparison.endpoint] : undefined}
        loading={loading}
      />
    </div>
  );

  const body = arrange(spec, node);
  const hasRail = spec.layout === "records-workspace" && (spec.filters?.length ?? 0) > 0;

  return (
    <div className="shell">
      <header className="shell-header">
        <span className="shell-mark">
          <Icon name="dashboard" size={20} />
        </span>
        <div>
          <h1 className="shell-title">{spec.title}</h1>
          {spec.provenance?.kind === "sample" ? (
            <span className="sample-badge" role="note">Sample data</span>
          ) : null}
          {spec.subtitle ? <div className="shell-sub">{spec.subtitle}</div> : null}
          {spec.source ? <SourceNote source={spec.source} /> : null}
        </div>
        <span className="shell-spacer" />
        <ThemeSwitcher initialTheme={spec.theme} />
      </header>

      <main className="shell-main">
        {loading && !Object.keys(data).length && !Object.keys(errors).length ? (
          <Skeleton />
        ) : <>
          {spec.hero ? errors[spec.hero.endpoint] ? <Card title={spec.hero.label}>
            <DataState error onRetry={() => setRefresh(r => r + 1)} />
          </Card> : loading ? <div className="card skeleton-card skeleton-hero" aria-busy="true" aria-label="Loading headline" />
            : <Hero label={spec.hero.label} unit={spec.hero.unit} fact={heroFact(spec.hero, data)} /> : null}
          {hasRail ? (
          <div className="row row-rail">
            <FilterRail
              filters={spec.filters ?? []}
              value={filters}
              onChange={(field, option) => setFilters((f) => ({ ...f, [field]: option }))}
            />
            <div className="row">{body}</div>
          </div>
        ) : (
          body
          )}
        </>}
      </main>
    </div>
  );
}
