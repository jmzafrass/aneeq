import { RETENTION_URL } from "./constants";
import { parseCsv } from "./csv";
import { Dimension, Metric, RetentionRawRow, RetentionRow } from "./types";
import { isValidCohort, parseCohortMonthKey, parseRetention } from "./utils";

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

function coerceNumber(raw: unknown) {
  const value = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(value) ? Number(value) : 0;
}

function shapeWideRows(rawRows: RetentionRawRow[]) {
  const rows: RetentionRow[] = [];
  for (const raw of rawRows) {
    if (!isValidCohort(raw.cohort_month)) continue;
    const { date, key } = parseCohortMonthKey(String(raw.cohort_month));
    if (!key) continue;
    const dimension = extractDimension(raw.dimension);
    const firstValue = ensureFirstValue(dimension, raw.first_value);
    const metric = extractMetric(raw.metric);
    const cohortSize = coerceNumber(
      raw.cohort_size ?? (raw as Record<string, unknown>).cohortsize ?? (raw as Record<string, unknown>).size,
    );

    for (const [column, value] of Object.entries(raw)) {
      if (column === "cohort_month" || column === "dimension" || column === "first_value" || column === "metric") continue;
      if (column === "cohort_size" || column === "size" || column === "cohortsize") continue;
      if (column === "retention" || column === "m") continue;

      const trimmed = column.trim();
      let monthNumber = Number.NaN;
      if (trimmed.startsWith("m") && trimmed.length > 1) {
        monthNumber = Number.parseInt(trimmed.slice(1), 10);
      } else {
        monthNumber = Number.parseInt(trimmed, 10);
      }
      if (!Number.isInteger(monthNumber) || monthNumber < 0) continue;

      const parsedValue = parseRetention(value);
      if (parsedValue <= 0) continue;

      rows.push({
        cohortMonth: date,
        cohortMonthKey: key,
        dimension,
        first_value: firstValue,
        m: monthNumber,
        metric,
        cohort_size: cohortSize,
        retention: parsedValue,
      });
    }
  }
  return rows;
}

function shapeLongRows(rawRows: RetentionRawRow[]) {
  const rows: RetentionRow[] = [];
  for (const raw of rawRows) {
    if (!isValidCohort(raw.cohort_month)) continue;
    const { date, key } = parseCohortMonthKey(String(raw.cohort_month));
    if (!key) continue;
    const dimension = extractDimension(raw.dimension);
    const firstValue = ensureFirstValue(dimension, raw.first_value);
    const metric = extractMetric(raw.metric);
    const mValue = coerceNumber(raw.m);
    if (!Number.isInteger(mValue) || mValue < 0) continue;
    const retention = parseRetention(raw.retention);
    if (retention <= 0) continue;
    rows.push({
      cohortMonth: date,
      cohortMonthKey: key,
      dimension,
      first_value: firstValue,
      m: mValue,
      metric,
      cohort_size: coerceNumber(raw.cohort_size),
      retention,
    });
  }
  return rows;
}

export async function fetchRetentionData(cacheBuster?: number, signal?: AbortSignal) {
  if (!RETENTION_URL || RETENTION_URL.startsWith("<PUT_PUBLIC_URL")) {
    throw new Error("No URL for retention data");
  }
  const url = cacheBuster ? `${RETENTION_URL}?t=${cacheBuster}` : RETENTION_URL;
  const res = await fetch(url, { cache: "no-store", mode: "cors", signal });
  if (!res.ok) throw new Error(`Retention HTTP ${res.status}`);
  const text = await res.text();
  const raw = await parseCsv<RetentionRawRow>(text);

  if (!raw.length) return [];
  const keys = Object.keys(raw[0] ?? {});
  const hasLong = raw.some((row) => row.m !== undefined);
  const hasWide = keys.some((key) => {
    if (!key) return false;
    const trimmed = key.trim();
    if (trimmed.startsWith("m") && Number.isInteger(Number.parseInt(trimmed.slice(1), 10))) return true;
    return Number.isInteger(Number.parseInt(trimmed, 10));
  });

  if (hasLong) {
    return shapeLongRows(raw);
  }
  if (hasWide) {
    return shapeWideRows(raw);
  }
  return [];
}
