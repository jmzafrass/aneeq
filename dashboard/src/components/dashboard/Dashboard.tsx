'use client';

import { useEffect, useMemo, useState, useRef } from "react";

import { LtvFilters } from "@/components/filters/LtvFilters";
import { RetentionFilters } from "@/components/filters/RetentionFilters";
import { LtvHeatmap } from "@/components/tables/LtvHeatmap";
import { HeatmapRow, RetentionHeatmap } from "@/components/tables/RetentionHeatmap";
import { OrdersDashboard } from "@/components/orders/OrdersDashboard";
import { CatalogueDashboard } from "@/components/orders/CatalogueDashboard";
import { ChurnDashboard } from "@/components/orders/ChurnDashboard";
import { UsersDashboard } from "@/components/users/UsersDashboard";
import { useActiveUsersData } from "@/hooks/useActiveUsersData";
import { useLtvData } from "@/hooks/useLtvData";
import { useRetentionData } from "@/hooks/useRetentionData";
import { RETENTION_URL, LTV_URL, MARKETING_SPEND_AED } from "@/lib/analytics/constants";
import { addMonths, classNames, monthKeyFromDate, monthsDiff } from "@/lib/analytics/utils";
import type { Dimension, Metric, LtvRow, RetentionRow, Segment } from "@/lib/analytics/types";
import { ChurnV2Dashboard } from "@/components/churn-v2/ChurnV2Dashboard";

interface PivotResult {
  rows: HeatmapRow[];
  maxMonth: number;
  maxValue?: number;
}

function buildRetentionPivot(
  rows: RetentionRow[],
  filters: {
    dimension: Dimension;
    metric: Metric;
    segment: Segment;
    firstValue: string;
    startMonth: string;
    endMonth: string;
  },
  lastObservedMonth: string,
): PivotResult {
  const filtered = rows.filter((row) => {
    if (row.segment !== filters.segment) return false;
    if (row.dimension !== filters.dimension) return false;
    if (filters.dimension !== "overall" && row.first_value !== filters.firstValue) return false;
    if (row.metric !== filters.metric) return false;
    if (filters.startMonth && row.cohortMonthKey < filters.startMonth) return false;
    if (filters.endMonth && row.cohortMonthKey > filters.endMonth) return false;
    if (filters.dimension === "overall" && row.first_value !== "ALL") return false;
    return true;
  });

  const byMonth = new Map<string, { size: number; values: Record<number, number | undefined> }>();
  for (const row of filtered) {
    if (!byMonth.has(row.cohortMonthKey)) {
      byMonth.set(row.cohortMonthKey, { size: row.cohort_size, values: {} });
    }
    const group = byMonth.get(row.cohortMonthKey)!;
    const allowed = lastObservedMonth ? monthsDiff(row.cohortMonthKey, lastObservedMonth) : Number.MAX_SAFE_INTEGER;
    if (lastObservedMonth && row.m > allowed) continue;
    group.values[row.m] = row.retention;
  }

  const ordered = Array.from(byMonth.entries())
    .map(([cohortMonth, group]) => ({
      cohortMonth,
      cohortSize: group.size,
      values: group.values,
    }))
    .sort((a, b) => a.cohortMonth.localeCompare(b.cohortMonth));

  const maxMonth = filtered.length
    ? lastObservedMonth
      ? Math.max(0, ...filtered.map((row) => monthsDiff(row.cohortMonthKey, lastObservedMonth)))
      : Math.max(0, ...filtered.map((row) => row.m))
    : 0;

  return { rows: ordered, maxMonth };
}

function buildLtvPivot(
  rows: LtvRow[],
  filters: {
    dimension: Dimension;
    metric: Metric;
    segment: Segment;
    firstValue: string;
    startMonth: string;
    endMonth: string;
    measure: "revenue" | "gm";
  },
  lastObservedMonth: string,
): PivotResult {
  const filtered = rows.filter((row) => {
    if (row.segment !== filters.segment) return false;
    if (row.dimension !== filters.dimension) return false;
    if (filters.dimension !== "overall" && row.first_value !== filters.firstValue) return false;
    if (row.metric !== filters.metric) return false;
    if (row.measure !== filters.measure) return false;
    if (filters.startMonth && row.cohortMonthKey < filters.startMonth) return false;
    if (filters.endMonth && row.cohortMonthKey > filters.endMonth) return false;
    if (lastObservedMonth && row.cohortMonthKey >= lastObservedMonth) return false;
    if (filters.dimension === "overall" && row.first_value !== "ALL") return false;
    return true;
  });

  const byMonth = new Map<string, { size: number; values: Record<number, number | undefined> }>();
  let maxValue = 0;

  for (const row of filtered) {
    if (!byMonth.has(row.cohortMonthKey)) {
      byMonth.set(row.cohortMonthKey, { size: row.cohort_size, values: {} });
    }
    const group = byMonth.get(row.cohortMonthKey)!;
    const allowed = lastObservedMonth ? monthsDiff(row.cohortMonthKey, lastObservedMonth) : Number.MAX_SAFE_INTEGER;
    if (lastObservedMonth && row.m > allowed) continue;
    if (row.ltv_per_user <= 0) continue;
    group.values[row.m] = row.ltv_per_user;
    if (row.ltv_per_user > maxValue) maxValue = row.ltv_per_user;
  }

  const ordered = Array.from(byMonth.entries())
    .map(([cohortMonth, group]) => ({
      cohortMonth,
      cohortSize: group.size,
      values: group.values,
    }))
    .sort((a, b) => a.cohortMonth.localeCompare(b.cohortMonth));

  const maxMonth = filtered.length
    ? lastObservedMonth
      ? Math.max(0, ...filtered.map((row) => monthsDiff(row.cohortMonthKey, lastObservedMonth)))
      : Math.max(0, ...filtered.map((row) => row.m))
    : 0;

  return { rows: ordered, maxMonth, maxValue };
}

function retentionCellColor(value?: number) {
  if (value === undefined) return "bg-gray-50 text-gray-400";
  if (value >= 0.9) return "bg-sky-600 text-white";
  if (value >= 0.75) return "bg-sky-500 text-white";
  if (value >= 0.6) return "bg-sky-400 text-white";
  if (value >= 0.45) return "bg-sky-300";
  if (value >= 0.3) return "bg-sky-200";
  if (value >= 0.15) return "bg-sky-100";
  return "bg-sky-50";
}

function ltvCellColor(value: number | undefined, max: number) {
  if (value === undefined) return "bg-gray-50 text-gray-400";
  if (max <= 0) return "bg-sky-50";
  const ratio = value / max;
  if (ratio >= 0.9) return "bg-sky-600 text-white";
  if (ratio >= 0.75) return "bg-sky-500 text-white";
  if (ratio >= 0.6) return "bg-sky-400 text-white";
  if (ratio >= 0.45) return "bg-sky-300";
  if (ratio >= 0.3) return "bg-sky-200";
  if (ratio >= 0.15) return "bg-sky-100";
  return "bg-sky-50";
}

type PrimaryTab = "current" | "cohorts" | "users" | "orders" | "catalogue" | "churn" | "churnV2";

const PRIMARY_TABS: Array<{ id: PrimaryTab; label: string }> = [
  { id: "current", label: "Current Orders" },
  { id: "cohorts", label: "Cohort Analytics" },
  { id: "users", label: "User Analytics" },
  { id: "orders", label: "Orders MoM" },
  { id: "catalogue", label: "Product Catalogue" },
  { id: "churn", label: "Churn Analysis" },
  { id: "churnV2", label: "Churn V2" },
];

export function Dashboard() {
  const [primaryTab, setPrimaryTab] = useState<PrimaryTab>("current");
  const [cohortTab, setCohortTab] = useState<"retention" | "ltv">("retention");
  const [refreshKey, setRefreshKey] = useState(() => Date.now());
  const retentionLastMonthRef = useRef("");
  const ltvLastMonthRef = useRef("");

  const {
    rows: retentionRows,
    error: retentionError,
    isLoading: retentionLoading,
    usingFallback: retentionFallback,
  } = useRetentionData(refreshKey);

  const { rows: ltvRows, error: ltvError, isLoading: ltvLoading, usingFallback: ltvFallback } = useLtvData(refreshKey);

  const {
    rows: activeRows,
    error: activeError,
    isLoading: activeLoading,
    usingFallback: activeFallback,
  } = useActiveUsersData(refreshKey);

  const [dimension, setDimension] = useState<Dimension>("overall");
  const [metric, setMetric] = useState<Metric>("any");
  const [segment, setSegment] = useState<Segment>("all");
  const [firstValue, setFirstValue] = useState("ALL");
  const [startMonth, setStartMonth] = useState("");
  const [endMonth, setEndMonth] = useState("");

  const [ltvDimension, setLtvDimension] = useState<Dimension>("overall");
  const [ltvMetric, setLtvMetric] = useState<Metric>("any");
  const [ltvSegment, setLtvSegment] = useState<Segment>("all");
  const [ltvFirstValue, setLtvFirstValue] = useState("ALL");
  const [ltvStartMonth, setLtvStartMonth] = useState("");
  const [ltvEndMonth, setLtvEndMonth] = useState("");
  const [showCac, setShowCac] = useState(false);

  const uniqueRetention = useMemo(() => {
    const segmentRows = retentionRows.filter((row) => row.segment === segment);
    const categories = Array.from(
      new Set(segmentRows.filter((row) => row.dimension === "category").map((row) => row.first_value)),
    )
      .filter(Boolean)
      .sort();
    const skus = Array.from(
      new Set(segmentRows.filter((row) => row.dimension === "sku").map((row) => row.first_value)),
    )
      .filter(Boolean)
      .sort();
    const months = Array.from(new Set(segmentRows.map((row) => row.cohortMonthKey))).sort();
    return { categories, skus, months };
  }, [retentionRows, segment]);

  const uniqueLtv = useMemo(() => {
    const gmRows = ltvRows.filter((row) => row.measure === "gm" && row.segment === ltvSegment);
    const categories = Array.from(
      new Set(gmRows.filter((row) => row.dimension === "category").map((row) => row.first_value)),
    )
      .filter(Boolean)
      .sort();
    const skus = Array.from(new Set(gmRows.filter((row) => row.dimension === "sku").map((row) => row.first_value)))
      .filter(Boolean)
      .sort();
    const months = Array.from(new Set(gmRows.map((row) => row.cohortMonthKey))).sort();
    return { categories, skus, months };
  }, [ltvRows, ltvSegment]);

  useEffect(() => {
    if (!startMonth && uniqueRetention.months.length) {
      setStartMonth(uniqueRetention.months[0]);
    }
  }, [uniqueRetention.months, startMonth]);

  useEffect(() => {
    if (!uniqueRetention.months.length) return;
    const latest = uniqueRetention.months[uniqueRetention.months.length - 1];
    if (!endMonth) {
      setEndMonth(latest);
      retentionLastMonthRef.current = latest;
      return;
    }
    if (retentionLastMonthRef.current !== latest) {
      retentionLastMonthRef.current = latest;
      setEndMonth(latest);
    }
  }, [uniqueRetention.months, endMonth]);

  useEffect(() => {
    if (!ltvStartMonth && uniqueLtv.months.length) {
      setLtvStartMonth(uniqueLtv.months[0]);
    }
  }, [uniqueLtv.months, ltvStartMonth]);

  useEffect(() => {
    if (!uniqueLtv.months.length) return;
    const latest = uniqueLtv.months[uniqueLtv.months.length - 1];
    if (!ltvEndMonth) {
      setLtvEndMonth(latest);
      ltvLastMonthRef.current = latest;
      return;
    }
    if (ltvLastMonthRef.current !== latest) {
      ltvLastMonthRef.current = latest;
      setLtvEndMonth(latest);
    }
  }, [uniqueLtv.months, ltvEndMonth]);

  useEffect(() => {
    if (dimension === "category" && !uniqueRetention.categories.includes(firstValue)) {
      setFirstValue(uniqueRetention.categories[0] ?? "");
    }
    if (dimension === "sku" && !uniqueRetention.skus.includes(firstValue)) {
      setFirstValue(uniqueRetention.skus[0] ?? "");
    }
  }, [dimension, firstValue, uniqueRetention.categories, uniqueRetention.skus]);

  useEffect(() => {
    if (ltvDimension === "category" && !uniqueLtv.categories.includes(ltvFirstValue)) {
      setLtvFirstValue(uniqueLtv.categories[0] ?? "");
    }
    if (ltvDimension === "sku" && !uniqueLtv.skus.includes(ltvFirstValue)) {
      setLtvFirstValue(uniqueLtv.skus[0] ?? "");
    }
  }, [ltvDimension, ltvFirstValue, uniqueLtv.categories, uniqueLtv.skus]);

  const lastObservedRetentionMonth = useMemo(() => {
    const cohortZero = retentionRows.filter((row) => row.m === 0);
    if (!cohortZero.length) return "";
    const lastKey = cohortZero.reduce((latest, row) => (row.cohortMonthKey > latest ? row.cohortMonthKey : latest), "");
    if (!lastKey) return "";
    const [year, month] = lastKey.split("-").map((value) => Number.parseInt(value, 10));
    if (!Number.isFinite(year) || !Number.isFinite(month)) return "";
    const end = addMonths(new Date(year, month - 1, 1), 1);
    return monthKeyFromDate(end);
  }, [retentionRows]);

  const lastObservedLtvMonth = lastObservedRetentionMonth;

  const effectiveMetric = dimension === "overall" ? "any" : metric;
  const effectiveFirstValue = dimension === "overall" ? "ALL" : firstValue;

  const effectiveLtvMetric = ltvDimension === "overall" ? "any" : ltvMetric;
  const effectiveLtvFirstValue = ltvDimension === "overall" ? "ALL" : ltvFirstValue;

  const retentionPivot = useMemo(
    () =>
      buildRetentionPivot(
        retentionRows,
        {
          dimension,
          metric: effectiveMetric,
          segment,
          firstValue: effectiveFirstValue,
          startMonth,
          endMonth,
        },
        lastObservedRetentionMonth,
      ),
    [retentionRows, dimension, effectiveMetric, segment, effectiveFirstValue, startMonth, endMonth, lastObservedRetentionMonth],
  );

  const ltvPivot = useMemo(
    () =>
      buildLtvPivot(
      ltvRows,
      {
        dimension: ltvDimension,
        metric: effectiveLtvMetric,
        segment: ltvSegment,
        firstValue: effectiveLtvFirstValue,
        startMonth: ltvStartMonth,
        endMonth: ltvEndMonth,
        measure: showCac ? "gm" : "revenue",
      },
        lastObservedLtvMonth,
      ),
    [
      ltvRows,
      ltvDimension,
      effectiveLtvMetric,
      ltvSegment,
      effectiveLtvFirstValue,
      ltvStartMonth,
      ltvEndMonth,
      lastObservedLtvMonth,
      showCac,
    ],
  );

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <div className="p-6 max-w-[1400px] mx-auto">
        <h1 className="text-2xl font-bold mb-6">Customer Analytics Dashboard</h1>

        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:gap-4">
          <div className="flex flex-wrap gap-2">
            {PRIMARY_TABS.map((tab) => (
              <button
                key={tab.id}
                className={classNames(
                  "px-4 py-2 rounded-lg text-sm font-medium",
                  primaryTab === tab.id ? "bg-blue-600 text-white" : "bg-gray-200",
                )}
                onClick={() => setPrimaryTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="flex md:ml-auto">
            <button
              className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 hover:bg-gray-200"
              onClick={() => setRefreshKey(Date.now())}
              title="Re-run data fetches"
            >
              Refresh data
            </button>
          </div>
        </div>

        {primaryTab === "current" ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="mb-2 text-sm font-semibold text-slate-900">Current month order view</div>
              <p className="text-xs text-gray-600">
                Embedded Airtable report covering the live monthly order tracker with month-over-month benchmarks and drilldowns.
              </p>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="h-[540px] w-full overflow-hidden rounded-lg border border-gray-200">
                <iframe
                  title="Current month order dashboard"
                  className="airtable-embed h-full w-full"
                  src="https://airtable.com/embed/appykWziIu3ZogEa1/shrS2atipEwwkqVgz"
                  loading="lazy"
                  frameBorder="0"
                  style={{ background: "transparent" }}
                />
              </div>
            </div>
          </div>
        ) : primaryTab === "cohorts" ? (
          <div className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-white p-4 rounded-xl shadow">
                <div className="text-sm font-medium mb-1">Retention data source</div>
                <div className="text-xs text-gray-600 break-all">
                  {retentionFallback ? "Embedded fallback sample" : `Local CSV asset (${RETENTION_URL})`}
                </div>
                <div className="text-[11px] text-gray-500 mt-2">Parsed rows: {retentionRows.length}</div>
                {retentionError && <div className="mt-2 text-xs text-red-600">{String(retentionError)}</div>}
              </div>
              <div className="bg-white p-4 rounded-xl shadow">
                <div className="text-sm font-medium mb-1">LTV data source</div>
                <div className="text-xs text-gray-600 break-all">
                  {ltvFallback ? "Embedded fallback sample" : `Local CSV asset (${LTV_URL})`}
                </div>
                <div className="text-[11px] text-gray-500 mt-2">Parsed rows: {ltvRows.length}</div>
                {ltvError && <div className="mt-2 text-xs text-red-600">{String(ltvError)}</div>}
              </div>
            </div>

            <div className="flex gap-2">
              <button
                className={classNames(
                  "px-4 py-2 rounded-lg text-sm font-medium",
                  cohortTab === "retention" ? "bg-blue-600 text-white" : "bg-gray-200",
                )}
                onClick={() => setCohortTab("retention")}
              >
                Retention
              </button>
              <button
                className={classNames(
                  "px-4 py-2 rounded-lg text-sm font-medium",
                  cohortTab === "ltv" ? "bg-blue-600 text-white" : "bg-gray-200",
                )}
                onClick={() => setCohortTab("ltv")}
              >
                LTV
              </button>
            </div>

            {cohortTab === "retention" ? (
              <div className="space-y-4">
                <RetentionFilters
                  dimension={dimension}
                  metric={effectiveMetric}
                  segment={segment}
                  firstValue={effectiveFirstValue}
                  startMonth={startMonth}
                  endMonth={endMonth}
                  months={uniqueRetention.months}
                  categories={uniqueRetention.categories}
                  skus={uniqueRetention.skus}
                  onDimensionChange={(value) => {
                    setDimension(value);
                    if (value === "overall") {
                      setMetric("any");
                      setFirstValue("ALL");
                    } else if (value === "category") {
                      setFirstValue(uniqueRetention.categories[0] ?? "");
                    } else {
                      setFirstValue(uniqueRetention.skus[0] ?? "");
                    }
                  }}
                  onMetricChange={(value) => setMetric(value)}
                  onSegmentChange={(value) => setSegment(value)}
                  onFirstValueChange={(value) => setFirstValue(value)}
                  onStartMonthChange={setStartMonth}
                  onEndMonthChange={setEndMonth}
                />

                <RetentionHeatmap
                  rows={retentionPivot.rows}
                  maxMonth={retentionPivot.maxMonth}
                  cellColor={retentionCellColor}
                />

                <div className="text-xs text-gray-600 bg-gray-50 p-4 rounded space-y-2">
                  <p className="font-semibold text-gray-700">How is this calculated?</p>
                  <ul className="list-disc pl-4 space-y-1">
                    <li>
                      <strong>Cohort:</strong> Customers are grouped by the month of their <em>first</em> delivered order. Cohort size (n) is the number of unique customers who first purchased in that month.
                    </li>
                    <li>
                      <strong>Retention (subscription-aware):</strong> A subscriber is counted as &quot;active&quot; for the full duration of their billing cadence after each purchase. For example, a customer on a 3-month plan who purchases in January is marked as retained in Jan, Feb, and Mar — even without a new transaction. The cadence is read from the subscription interval field (1, 2, or 3 months).
                    </li>
                    <li>
                      <strong>One-time buyers:</strong> Customers whose first order did not include a subscription product (POM HL or POM BG). They are only counted as &quot;active&quot; in the month they actually made a purchase.
                    </li>
                    <li>
                      <strong>Segment filter:</strong> &quot;All&quot; blends subscribers + one-time using the above rules. &quot;Subscribers&quot; isolates only customers whose first purchase included a subscription product. &quot;One-time&quot; isolates non-subscription first purchases.
                    </li>
                    <li>
                      <strong>Metric:</strong> &quot;Any&quot; = the customer was active with any product. &quot;Same&quot; = the customer was active specifically within the same category as their first purchase (measures category stickiness).
                    </li>
                    <li>
                      <strong>M0, M1, M2…:</strong> Months since first purchase. M0 is always 100%. M1 is one month later, etc. Values are capped at the last fully completed calendar month.
                    </li>
                  </ul>
                  <p className="text-[11px] text-gray-400">
                    Source: allorders.csv (delivered orders only). Billing cadence from Airtable subscription_frequency_interval and Sub_interval fields. AED amounts converted to USD at the pegged rate (1 AED = $0.2723).
                  </p>
                  {(retentionLoading || !retentionRows.length) && <p className="mt-1">Loading retention data…</p>}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <LtvFilters
                  dimension={ltvDimension}
                  metric={effectiveLtvMetric}
                  segment={ltvSegment}
                  firstValue={effectiveLtvFirstValue}
                  startMonth={ltvStartMonth}
                  endMonth={ltvEndMonth}
                  months={uniqueLtv.months}
                  categories={uniqueLtv.categories}
                  skus={uniqueLtv.skus}
                  onDimensionChange={(value) => {
                    setLtvDimension(value);
                    if (value === "overall") {
                      setLtvMetric("any");
                      setLtvFirstValue("ALL");
                    } else if (value === "category") {
                      setLtvFirstValue(uniqueLtv.categories[0] ?? "");
                    } else {
                      setLtvFirstValue(uniqueLtv.skus[0] ?? "");
                    }
                  }}
                  onMetricChange={(value) => setLtvMetric(value)}
                  onSegmentChange={(value) => setLtvSegment(value)}
                  onFirstValueChange={(value) => setLtvFirstValue(value)}
                  onStartMonthChange={setLtvStartMonth}
                  onEndMonthChange={setLtvEndMonth}
                />

                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-gray-500">
                    {showCac ? "Showing: Gross Margin LTV with CAC analysis" : "Showing: Revenue LTV"}
                  </span>
                  <button
                    onClick={() => setShowCac(!showCac)}
                    className={classNames(
                      "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                      showCac
                        ? "bg-amber-100 text-amber-800 hover:bg-amber-200"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    )}
                  >
                    {showCac ? "Switch to Revenue LTV" : "Show CAC & Margin LTV"}
                  </button>
                </div>
                <LtvHeatmap
                  rows={ltvPivot.rows}
                  maxMonth={ltvPivot.maxMonth}
                  maxValue={ltvPivot.maxValue ?? 0}
                  cellColor={ltvCellColor}
                  marketingSpend={showCac ? MARKETING_SPEND_AED : undefined}
                />

                <div className="text-xs text-gray-600 bg-gray-50 p-4 rounded space-y-2">
                  <p className="font-semibold text-gray-700">How is this calculated?</p>
                  <ul className="list-disc pl-4 space-y-1">
                    <li>
                      <strong>Cohort:</strong> Customers grouped by the month of their first delivered order.
                    </li>
                    {showCac ? (
                      <>
                        <li>
                          <strong>LTV (Gross Margin):</strong> Cumulative profit per customer (Revenue − COGS). At M0 it shows first-month profit; at M3 the total profit across months 0–3. COGS uses Magenta pricing from July 2025.
                        </li>
                        <li>
                          <strong>CAC:</strong> Marketing spend ÷ new customers. Lower = more efficient acquisition.
                        </li>
                        <li>
                          <strong>Break-even:</strong> First month where cumulative margin exceeds CAC. Green ring = profitable customer.
                        </li>
                      </>
                    ) : (
                      <li>
                        <strong>LTV (Revenue):</strong> Cumulative revenue per customer from M0 through each month. At M0 it shows average first-month spend; at M3 the total spend across months 0–3.
                      </li>
                    )}
                    <li>
                      <strong>Segment:</strong> &quot;Subscribers&quot; = subscription-first customers. &quot;One-time&quot; = non-subscription. &quot;All&quot; = combined.
                    </li>
                    <li>
                      <strong>Reading:</strong> Darker blue = higher LTV. Steadily increasing row = customers keep spending.
                      {showCac && " Green rings = break-even achieved."}
                    </li>
                  </ul>
                  <p className="text-[11px] text-gray-400">
                    Source: allorders.csv (delivered orders).
                    {showCac && " COGS from Product table. Marketing spend from Meta + Google."}
                  </p>
                  {(ltvLoading || !ltvRows.length) && <p className="mt-1">Loading LTV data…</p>}
                  {ltvError && <p className="mt-1 text-red-600">{String(ltvError)}</p>}
                </div>
              </div>
            )}
          </div>
        ) : primaryTab === "users" ? (
          <UsersDashboard rows={activeRows} isLoading={activeLoading} error={activeError} usingFallback={activeFallback} />
        ) : primaryTab === "orders" ? (
          <OrdersDashboard />
        ) : primaryTab === "catalogue" ? (
          <CatalogueDashboard />
        ) : primaryTab === "churn" ? (
          <ChurnDashboard />
        ) : (
          <ChurnV2Dashboard />
        )}
      </div>
    </div>
  );
}
