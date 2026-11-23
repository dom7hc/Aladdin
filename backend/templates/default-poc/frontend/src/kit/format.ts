/** One numeric formatter for dashboards and presentation output. */
export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return abs < 10 && !Number.isInteger(value) ? value.toFixed(1) : String(Math.round(value));
}
