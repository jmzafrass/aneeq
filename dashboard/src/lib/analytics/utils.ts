import { Measure } from "./types";

export function parseCohortMonthKey(raw: string): { date: Date; key: string } {
  const dateStr = raw.split(" ")[0]?.trim();
  const [year = "", month = ""] = dateStr.split("-");
  const y = Number.parseInt(year, 10);
  const m = Number.parseInt(month, 10);
  if (!Number.isFinite(y) || !Number.isFinite(m)) {
    return { date: new Date(NaN), key: "" };
  }
  const date = new Date(y, m - 1, 1);
  const key = `${y}-${String(m).padStart(2, "0")}`;
  return { date, key };
}

export function parseRetention(val: unknown): number {
  if (typeof val === "number") {
    return Number.isFinite(val) ? val : 0;
  }
  if (typeof val === "string") {
    const trimmed = val.trim();
    if (!trimmed) return 0;
    if (trimmed.endsWith("%")) {
      const pct = Number.parseFloat(trimmed.slice(0, -1));
      return Number.isFinite(pct) ? pct / 100 : 0;
    }
    const numeric = Number.parseFloat(trimmed);
    return Number.isFinite(numeric) ? numeric : 0;
  }
  return 0;
}

export function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export function monthKeyFromDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export function addMonths(date: Date, months: number) {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

export function monthsDiff(startKey: string, endKey: string) {
  if (!startKey || !endKey) return 0;
  const [sy, sm] = startKey.split("-").map((part) => Number.parseInt(part, 10));
  const [ey, em] = endKey.split("-").map((part) => Number.parseInt(part, 10));
  if ([sy, sm, ey, em].some((n) => !Number.isFinite(n))) return 0;
  return Math.max(0, (ey - sy) * 12 + (em - sm));
}

export function isValidCohort(value: unknown) {
  const cleaned = String(value ?? "").trim();
  const [datePart] = cleaned.split(" ");
  const segments = datePart.split("-");
  return segments.length >= 2 && segments[0]?.length === 4 && segments[1]?.length === 2;
}

export function normalizeMeasure(raw: unknown): Measure {
  const value = String(raw ?? "revenue")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "_");
  if (value === "gross_margin" || value === "gm") return "gm";
  return "revenue";
}

const AED_TO_USD = 1 / 3.6725;

export function formatUsd(aedValue: number) {
  const usd = aedValue * AED_TO_USD;
  return `$${usd.toFixed(2)}`;
}

export function aedToUsd(aedValue: number): number {
  return aedValue * AED_TO_USD;
}

/**
 * Calculate CAC in USD for a given cohort.
 * @param spendAed Marketing spend in AED for the cohort month
 * @param cohortSize Number of new customers acquired in that month
 * @returns CAC in USD, or undefined if no spend data
 */
export function calculateCacUsd(spendAed: number | undefined, cohortSize: number): number | undefined {
  if (spendAed === undefined || cohortSize <= 0) return undefined;
  return aedToUsd(spendAed) / cohortSize;
}

/**
 * Find the first month (M value) where cumulative LTV exceeds CAC.
 * @param values Record of month index to LTV value
 * @param cacUsd CAC in USD
 * @param maxMonth Maximum month to check
 * @returns Month index where break-even occurs, or undefined if not reached
 */
export function findBreakEvenMonth(
  values: Record<number, number | undefined>,
  cacUsd: number | undefined,
  maxMonth: number
): number | undefined {
  if (cacUsd === undefined) return undefined;
  for (let m = 0; m <= maxMonth; m++) {
    const ltv = values[m];
    if (ltv !== undefined && aedToUsd(ltv) >= cacUsd) {
      return m;
    }
  }
  return undefined;
}
