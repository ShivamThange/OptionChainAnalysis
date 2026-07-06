// REST helpers for history / time-series (charts that need persisted data).

export interface SeriesPoint { ts: number; value: number }

export async function fetchSeries(
  underlying: string,
  column: string,
  limit = 300
): Promise<SeriesPoint[]> {
  const r = await fetch(`/api/series/${underlying}/${column}?limit=${limit}`);
  if (!r.ok) return [];
  const j = await r.json();
  return j.series ?? [];
}

export async function fetchHealth(): Promise<any> {
  const r = await fetch("/api/health");
  return r.ok ? r.json() : null;
}
