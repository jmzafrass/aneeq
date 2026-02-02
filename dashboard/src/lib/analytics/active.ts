import { buildActiveFallback } from "./constants";
import type { ActiveUsersRow } from "./types";

export async function fetchActiveUsersData(cacheBuster?: number, signal?: AbortSignal) {
  const endpoint = cacheBuster
    ? `/api/users/active?source=default&t=${cacheBuster}`
    : "/api/users/active?source=default";

  const res = await fetch(endpoint, {
    method: "POST",
    cache: "no-store",
    signal,
  });

  if (!res.ok) throw new Error(`Active users HTTP ${res.status}`);
  const payload = (await res.json()) as { rows?: ActiveUsersRow[] };
  const rows = payload.rows ?? [];

  if (!rows.length) {
    return buildActiveFallback();
  }

  return rows;
}
