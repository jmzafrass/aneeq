import type { ActiveUsersRow, LtvRow, RetentionRow } from "./types";

export const RETENTION_URL = "/data/purchase_retention.csv";

export const LTV_URL = "/data/ltv_by_category_sku.csv";

export const FALLBACK_RETENTION_ROWS: RetentionRow[] = [
  { cohortMonth: new Date(2024, 9, 1), cohortMonthKey: "2024-10", dimension: "overall", first_value: "ALL", m: 0, metric: "any", segment: "all", cohort_size: 3, retention: 1 },
  { cohortMonth: new Date(2024, 9, 1), cohortMonthKey: "2024-10", dimension: "overall", first_value: "ALL", m: 1, metric: "any", segment: "all", cohort_size: 3, retention: 0.6667 },
  { cohortMonth: new Date(2024, 10, 1), cohortMonthKey: "2024-11", dimension: "overall", first_value: "ALL", m: 0, metric: "any", segment: "all", cohort_size: 5, retention: 1 },
  { cohortMonth: new Date(2024, 10, 1), cohortMonthKey: "2024-11", dimension: "overall", first_value: "ALL", m: 1, metric: "any", segment: "all", cohort_size: 5, retention: 0.6 },
];

export const FALLBACK_LTV_ROWS: LtvRow[] = [
  { cohort_type: "purchase", cohortMonth: new Date(2024, 9, 1), cohortMonthKey: "2024-10", dimension: "overall", first_value: "ALL", m: 0, metric: "any", measure: "revenue", segment: "all", cohort_size: 3, ltv_per_user: 350 },
  { cohort_type: "purchase", cohortMonth: new Date(2024, 9, 1), cohortMonthKey: "2024-10", dimension: "overall", first_value: "ALL", m: 1, metric: "any", measure: "revenue", segment: "all", cohort_size: 3, ltv_per_user: 700 },
  { cohort_type: "purchase", cohortMonth: new Date(2024, 10, 1), cohortMonthKey: "2024-11", dimension: "overall", first_value: "ALL", m: 0, metric: "any", measure: "revenue", segment: "all", cohort_size: 5, ltv_per_user: 350 },
];

export const FALLBACK_ACTIVE_ROWS: ActiveUsersRow[] = [
  { month: "2024-10-01", active_subscribers: 3, active_onetime: 1, active_total: 4, is_future_vs_today: 0 },
  { month: "2024-11-01", active_subscribers: 5, active_onetime: 2, active_total: 6, is_future_vs_today: 0 },
];

export function buildRetentionFallback(): RetentionRow[] {
  return FALLBACK_RETENTION_ROWS.map((row) => ({ ...row, cohortMonth: new Date(row.cohortMonth) }));
}

export function buildLtvFallback(): LtvRow[] {
  return FALLBACK_LTV_ROWS.map((row) => ({ ...row, cohortMonth: new Date(row.cohortMonth) }));
}

export function buildActiveFallback(): ActiveUsersRow[] {
  return [...FALLBACK_ACTIVE_ROWS];
}

/**
 * Monthly marketing spend in AED (all channels combined).
 * Used to calculate CAC (Customer Acquisition Cost) per cohort.
 */
export const MARKETING_SPEND_AED: Record<string, number> = {
  "2024-10": 3034,
  "2024-11": 14765,
  "2024-12": 17466,
  "2025-01": 27372,
  "2025-02": 16761,
  "2025-03": 39748,
  "2025-04": 38939,
  "2025-05": 49600,
  "2025-06": 50600,
  "2025-07": 51880,
  "2025-08": 58139,
  "2025-09": 94500,
  "2025-10": 80142,
  "2025-11": 68266,
  "2025-12": 74215,
  "2026-01": 84900,
};
