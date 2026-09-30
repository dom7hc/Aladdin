// Renders a DashboardSpec. This is the whole frontend of a generated PoC: the
// generator supplies the spec and the backend endpoints, nothing more.

import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { BarChart, LineChart } from "./charts";
import type { DashboardSpec, Widget } from "./types";
import { Card, DataTable, EditableDataTable, FilterRail, StatTile, ThemeSwitcher } from "./widgets";

type Payload = Record<string, unknown> | Record<string, unknown>[];

/** One fetch per distinct endpoint, shared by every widget that reads it. */
function useEndpointData(
  endpoints: string[],
  filters: Record<string, string>,
  refresh: number,
) {
  const key = `${endpoints.join("|")}::${JSON.stringify(filters)}::${refresh}`;
  const [data, setData] = useState<Record<string, Payload>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const query = new URLSearchParams(
      Object.entries(filters).filter(([, v]) => v && v !== "All"),
    ).toString();

    Promise.all(
      endpoints.map(async (endpoint) => {
        const url = query ? `${endpoint}?${query}` : endpoint;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`${endpoint} returned ${response.status}`);
        return [endpoint, (await response.json()) as Payload] as const;
      }),
    )
      .then((pairs) => {
        if (cancelled) return;
        setData(Object.fromEntries(pairs));
        setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load data");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { data, error, loading };
}

function asRows(payload: Payload | undefined): Record<string, unknown>[] {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === "object") {
    // Endpoints often wrap a list: {items: [...]}, {rows: [...]}, {data: [...]}.
    for (const key of ["items", "rows", "data", "results"]) {
      const value = (payload as Record<string, unknown>)[key];
      if (Array.isArray(value)) return value as Record<string, unknown>[];
    }
  }
  return [];
}

function asObject(payload: Payload | undefined): Record<string, unknown> {
  if (Array.isArray(payload)) return payload[0] ?? {};
  return (payload as Record<string, unknown>) ?? {};
}

function WidgetView({
  widget,
  payload,
  onMutate,
}: {
  widget: Widget;
  payload: Payload | undefined;
  onMutate: () => void;
}) {
  switch (widget.kind) {
    case "stat": {
      const source = asObject(payload);
      const trend = source[widget.trendField ?? ""];
      return (
        <StatTile
          label={widget.label}
          value={(source[widget.field] as number | string) ?? "—"}
          unit={widget.unit}
          delta={
            widget.deltaField !== undefined ? Number(source[widget.deltaField]) || 0 : undefined
          }
          trend={Array.isArray(trend) ? (trend as number[]) : undefined}
        />
      );
    }
    case "line":
      return (
        <Card title={widget.title}>
          <LineChart rows={asRows(payload)} xField={widget.xField} series={widget.series} />
        </Card>
      );
    case "bar":
      return (
        <Card title={widget.title}>
          <BarChart
            rows={asRows(payload)}
            categoryField={widget.categoryField}
            series={widget.series}
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
              onMutate={onMutate}
            />
          ) : (
            <DataTable rows={asRows(payload)} columns={widget.columns} />
          )}
        </Card>
      );
    default:
      return null;
  }
}

/** Layouts differ only in how widgets are grouped into rows. */
function arrange(spec: DashboardSpec, node: (w: Widget) => ReactNode) {
  const stats = spec.widgets.filter((w) => w.kind === "stat");
  const rest = spec.widgets.filter((w) => w.kind !== "stat");

  const statRow = stats.length ? <div className="row row-4">{stats.map(node)}</div> : null;

  switch (spec.layout) {
    case "analytics-breakdown": {
      const plots = rest.filter((w) => w.kind === "line" || w.kind === "bar");
      const others = rest.filter((w) => w.kind !== "line" && w.kind !== "bar");
      return (
        <>
          {statRow}
          {plots.length ? <div className="row row-2">{plots.map(node)}</div> : null}
          {others.map(node)}
        </>
      );
    }
    case "records-workspace":
      // The filter rail is rendered by the shell; tables stack full width.
      return (
        <>
          {statRow}
          {rest.map(node)}
        </>
      );
    case "kpi-overview":
    default:
      return (
        <>
          {statRow}
          {rest.map(node)}
        </>
      );
  }
}

export function Dashboard({ spec }: { spec: DashboardSpec }) {
  const [filters, setFilters] = useState<Record<string, string>>({});
  // Bumped by editable tables after a successful mutation; every endpoint then
  // refetches, so stats and charts stay consistent with the table.
  const [refresh, setRefresh] = useState(0);

  // index.html is a platform-owned fallback, so its <title> is generic. The
  // browser tab should name the dashboard, not say "PoC".
  useEffect(() => {
    if (spec.title) document.title = spec.title;
  }, [spec.title]);
  const endpoints = useMemo(
    () => Array.from(new Set(spec.widgets.map((w) => w.endpoint))),
    [spec],
  );
  const { data, error, loading } = useEndpointData(endpoints, filters, refresh);

  const node = (widget: Widget) => (
    <WidgetView
      key={`${widget.kind}-${"title" in widget ? widget.title : widget.label}`}
      widget={widget}
      payload={data[widget.endpoint]}
      onMutate={() => setRefresh((r) => r + 1)}
    />
  );

  const body = arrange(spec, node);
  const hasRail = spec.layout === "records-workspace" && (spec.filters?.length ?? 0) > 0;

  return (
    <div className="shell">
      <header className="shell-header">
        <div>
          <div className="shell-title">{spec.title}</div>
          {spec.subtitle ? <div className="shell-sub">{spec.subtitle}</div> : null}
        </div>
        <span className="shell-spacer" />
        <ThemeSwitcher initialTheme={spec.theme} />
      </header>

      <main className="shell-main">
        {error ? (
          <Card title="Could not load data">
            <p className="empty">
              {error}. The dashboard is running, but its API did not answer as expected.
            </p>
          </Card>
        ) : null}
        {loading && !Object.keys(data).length ? <p className="empty">Loading…</p> : null}

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
      </main>
    </div>
  );
}
