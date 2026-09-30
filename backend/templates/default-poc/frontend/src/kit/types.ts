// The dashboard spec — the one frontend file the generator writes.
//
// Keep this in step with backend/app/generation/spec.py, which validates the
// same shape before anything is written to the workspace.

export type Layout = "kpi-overview" | "analytics-breakdown" | "records-workspace";

/** A number shown on its own, optionally with a change and a sparkline. */
export interface StatWidget {
  kind: "stat";
  label: string;
  /** Field on the endpoint payload holding the value. */
  field: string;
  unit?: string;
  /** Field holding a percentage change; positive is treated as up. */
  deltaField?: string;
  /** Field holding an array of numbers for the sparkline. */
  trendField?: string;
}

/** A value over an ordered dimension — time, usually. */
export interface LineWidget {
  kind: "line";
  title: string;
  xField: string;
  series: { label: string; field: string }[];
}

/** A value compared across categories. */
export interface BarWidget {
  kind: "bar";
  title: string;
  categoryField: string;
  series: { label: string; field: string }[];
}

export interface TableWidget {
  kind: "table";
  title: string;
  columns: { label: string; field: string; align?: "left" | "right" }[];
  /**
   * Editable tables render add/edit/delete controls and expect the backend to
   * implement POST <endpoint>, PUT <endpoint>/{id} and DELETE <endpoint>/{id};
   * rows carry an "id". Validated by app/generation/spec.py.
   */
  editable?: boolean;
}

export type Widget = (StatWidget | LineWidget | BarWidget | TableWidget) & {
  /** Backend path this widget reads, e.g. "/api/metrics". */
  endpoint: string;
};

export interface Filter {
  label: string;
  field: string;
  options: string[];
}

export interface DashboardSpec {
  title: string;
  subtitle?: string;
  layout: Layout;
  theme?: string;
  widgets: Widget[];
  filters?: Filter[];
}
