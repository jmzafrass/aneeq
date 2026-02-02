import { LTV_URL } from "./constants";
import { parseCsv } from "./csv";
import { Dimension, LtvRawRow, LtvRow, Metric } from "./types";
import { isValidCohort, normalizeMeasure, parseCohortMonthKey } from "./utils";

function extractDimension(value: unknown): Dimension {
  if (value === "category" || value === "sku") return value;
  return "overall";
}

function extractMetric(value: unknown): Metric {
  if (value === "same") return "same";
  return "any";
}

function ensureFirstValue(dimension: Dimension, raw: unknown) {
  if (dimension === "overall") return "ALL";
  const value = String(raw ?? "").trim();
  return value || "";
}

function coerceNumber(raw: unknown, defaultValue = 0) {
  const value = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(value) ? Number(value) : defaultValue;
}

export async function fetchLtvData(cacheBuster?: number, signal?: AbortSignal) {
  if (!LTV_URL || LTV_URL.startsWith("<PUT_PUBLIC_URL")) {
    throw new Error("No URL for LTV data");
  }
  const url = cacheBuster ? `${LTV_URL}?t=${cacheBuster}` : LTV_URL;
  const res = await fetch(url, { cache: "no-store", mode: "cors", signal });
  if (!res.ok) throw new Error(`LTV HTTP ${res.status}`);
  const text = await res.text();
  const raw = await parseCsv<LtvRawRow>(text);

  const rows: LtvRow[] = [];
  for (const entry of raw) {
    if (!isValidCohort(entry.cohort_month)) continue;
    const { date, key } = parseCohortMonthKey(String(entry.cohort_month));
    if (!key) continue;
    const dimension = extractDimension(entry.dimension);
    const metric = extractMetric(entry.metric);
    const firstValue = ensureFirstValue(dimension, entry.first_value);
    const ltvPerUser = coerceNumber(entry.ltv_per_user);
    if (ltvPerUser <= 0) continue;

    rows.push({
      cohort_type: String(entry.cohort_type ?? "purchase"),
      cohortMonth: date,
      cohortMonthKey: key,
      dimension,
      first_value: firstValue,
      m: coerceNumber(entry.m),
      metric,
      measure: normalizeMeasure(entry.measure),
      cohort_size: coerceNumber(entry.cohort_size),
      ltv_per_user: ltvPerUser,
    });
  }

  return rows.filter((row) => Number.isInteger(row.m) && row.m >= 0);
}
