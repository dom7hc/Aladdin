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
  /** One of the names in icons.tsx; absent or unknown, one is guessed from the label. */
  icon?: string;
  /** Explicit favourable direction; absent remains neutral, never guessed. */
  lowerIsBetter?: boolean;
  /** What the change compares against, e.g. "vs last month". */
  deltaLabel?: string;
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

/** Share of a whole: a few categories that add up to a total. */
export interface DonutWidget {
  kind: "donut";
  title: string;
  categoryField: string;
  valueField: string;
  unit?: string;
}

/** Measures against their targets, one row each. */
export interface ProgressWidget {
  kind: "progress";
  title: string;
  labelField: string;
  valueField: string;
  targetField: string;
  unit?: string;
}

/** The top entries by one value, largest first. */
export interface RankingWidget {
  kind: "ranking";
  title: string;
  labelField: string;
  valueField: string;
  unit?: string;
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

export type Widget = (
  | StatWidget
  | LineWidget
  | BarWidget
  | DonutWidget
  | ProgressWidget
  | RankingWidget
  | TableWidget
) & {
  /** Backend path this widget reads, e.g. "/api/metrics". */
  endpoint: string;
  id?: string;
  unit?: string;
  comparison?: Comparison;
};

export interface Filter {
  label: string;
  field: string;
  options: string[];
}

export interface DashboardSpec {
  schemaVersion?: 2;
  hero?: HeroBinding | null;
  provenance?: Provenance;
  title: string;
  subtitle?: string;
  layout: Layout;
  theme?: string;
  /** Resolved by the platform; style is one of the looks in looks.css. */
  designSystem?: { palette?: string; fonts?: string; style?: string };
  widgets: Widget[];
  filters?: Filter[];
  /** The user's file, written by the platform: shown under the title. */
  source?: { filename: string; rows: number; fileRows: number };
}

/** Numeric conclusions are computed from payloads, never model-supplied copy. */
export interface Comparison {
  kind: "target" | "prior";
  label: string;
  endpoint: string;
  field: string;
  unit: string;
  /** Align previous series by category/time key, never by array position. */
  keyField?: string;
}

export interface HeroBinding {
  id: string;
  label: string;
  endpoint: string;
  field: string;
  unit?: string;
  lowerIsBetter?: boolean | null;
  minSamples?: number;
  comparison?: Comparison;
}

export interface Provenance {
  kind: "sample" | "upload" | "unknown";
  fixtureId?: string;
  seed?: number;
  dateAnchor?: string;
  label?: string;
}

export type Payload = Record<string, unknown> | Record<string, unknown>[];

export interface DashboardSnapshot {
  schemaVersion: 1;
  specHash: string;
  capturedAt: string;
  scope: string;
  endpoints: Record<string, Payload>;
  provenance: Provenance;
}
