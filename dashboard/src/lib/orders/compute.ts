import fs from "node:fs/promises";
import path from "node:path";

import { parse as parseCsv } from "csv-parse/sync";

import type {
  ChurnByCategoryRow,
  ChurnRow,
  ChurnSummary,
  DailyRetentionRow,
  WeeklyRetentionRow,
} from "@/lib/orders/types";

export type Segment = "subscribers" | "onetime" | "total";
export type Metric = "any" | "same";

interface ProcessedOrder {
  id: string;
  uid: string;
  date: Date;
  monthKey: string;
  price: number;
  categories: string[];
  skus: string[];
  notes: string;
  status: string;
}

export interface RetentionOutputRow {
  cohort_month: string;
  dimension: "overall" | "category";
  first_value: string;
  m: number;
  metric: Metric;
  cohort_size: number;
  retention: string;
}

export interface LtvOutputRow {
  cohort_type: "purchase";
  cohort_month: string;
  dimension: "overall" | "category";
  first_value: string;
  m: number;
  metric: Metric;
  measure: "revenue";
  cohort_size: number;
  ltv_per_user: number;
}

export interface SurvivalOutputRow {
  cohort_month: string;
  category: string;
  m: number;
  cohort_size: number;
  survival_rate: number;
}

export interface WaterfallOutputRow {
  month: string;
  category: string;
  start_active: number;
  new_active: number;
  reactivated: number;
  churned: number;
  end_active: number;
}

export interface ComputeAllResult {
  asOfMonth: string;
  churn: ChurnSummary;
  retention: RetentionOutputRow[];
  ltv: LtvOutputRow[];
  survival: SurvivalOutputRow[];
  waterfall: WaterfallOutputRow[];
}

const SUBSCRIPTION_CATEGORIES = new Set(["pom hl", "pom bg"]);
const CATEGORY_PRIORITY = ["pom hl", "pom bg", "pom sh", "otc hl", "otc sh", "otc sk"];
const DAY_MS = 24 * 60 * 60 * 1000;

function zeroPad(value: number) {
  return String(value).padStart(2, "0");
}

function ym(date: Date) {
  return `${date.getFullYear()}-${zeroPad(date.getMonth() + 1)}`;
}

function ymd(date: Date) {
  return `${date.getFullYear()}-${zeroPad(date.getMonth() + 1)}-${zeroPad(date.getDate())}`;
}

function addMonths(date: Date, months: number) {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

function monthKeyToDate(key: string) {
  const [year, month] = key.split("-").map((part) => Number.parseInt(part, 10));
  return new Date(year, month - 1, 1);
}

function clampAsOfMonth(maxMonth: string) {
  const today = new Date();
  const lastFull = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  const baseline = ym(lastFull);
  if (!maxMonth) return baseline;
  return maxMonth < baseline ? maxMonth : baseline;
}

function parseFlexibleDate(raw: unknown): Date | null {
  if (raw == null) return null;
  const value = String(raw).trim().split(" ")[0];

  const monthFirst = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/;
  const isoPattern = /^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$/;

  let match = value.match(monthFirst);
  if (match) {
    const [, first, second, y] = match;
    const a = Number.parseInt(first, 10);
    const b = Number.parseInt(second, 10);
    const year = Number.parseInt(y, 10);
    // Prefer day-first (dd/mm/yyyy) since allorders.csv uses this format
    if (b >= 1 && b <= 12 && a >= 1 && a <= 31) {
      const date = new Date(year, b - 1, a);
      if (!Number.isNaN(date.getTime())) return date;
    }
    // Fall back to month-first (mm/dd/yyyy)
    if (a >= 1 && a <= 12 && b >= 1 && b <= 31) {
      const date = new Date(year, a - 1, b);
      if (!Number.isNaN(date.getTime())) return date;
    }
  }

  match = value.match(isoPattern);
  if (match) {
    const [, y, m, d] = match;
    const date = new Date(Number.parseInt(y, 10), Number.parseInt(m, 10) - 1, Number.parseInt(d, 10));
    if (!Number.isNaN(date.getTime())) return date;
  }

  const fallback = new Date(value);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
}

function isoWeekStart(dateStr: string) {
  const source = new Date(dateStr);
  // Normalise to UTC to avoid timezone drift
  const utc = new Date(Date.UTC(source.getFullYear(), source.getMonth(), source.getDate()));
  const day = utc.getUTCDay(); // Sunday = 0
  const delta = (day + 6) % 7; // days since Monday
  utc.setUTCDate(utc.getUTCDate() - delta);
  return `${utc.getUTCFullYear()}-${zeroPad(utc.getUTCMonth() + 1)}-${zeroPad(utc.getUTCDate())}`;
}

function weeklySets(store: Map<string, Set<string>>) {
  const acc = new Map<string, Set<string>>();
  const dates = Array.from(store.keys()).sort();
  for (const date of dates) {
    const key = isoWeekStart(date);
    if (!acc.has(key)) acc.set(key, new Set());
    (store.get(date) ?? new Set<string>()).forEach((uid) => acc.get(key)!.add(uid));
  }
  return new Map(Array.from(acc.entries()).sort((a, b) => a[0].localeCompare(b[0])));
}

function buildWeeklyRetention(store: Map<string, Set<string>>, label: Segment): WeeklyRetentionRow[] {
  const weeks = weeklySets(store);
  const keys = Array.from(weeks.keys());
  const rows: WeeklyRetentionRow[] = [];
  for (let index = 1; index < keys.length; index += 1) {
    const prev = weeks.get(keys[index - 1]) ?? new Set<string>();
    const curr = weeks.get(keys[index]) ?? new Set<string>();
    const prevSize = prev.size;
    const retained = Array.from(prev).filter((uid) => curr.has(uid)).length;
    const churned = prevSize - retained;
    rows.push({
      week: keys[index],
      label,
      prevActive: prevSize,
      retained,
      churned,
      retentionRate: prevSize ? retained / prevSize : 0,
    });
  }
  return rows;
}

function splitValues(value: unknown) {
  if (value == null) return [] as string[];
  return String(value)
    .split(/[;,]/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function prioritizeCategory(categories: string[]) {
  const unique = Array.from(new Set(categories.filter(Boolean)));
  const order = new Map(CATEGORY_PRIORITY.map((category, index) => [category, index]));
  return (
    unique.sort((a, b) => {
      const pa = order.get(a) ?? Number.MAX_SAFE_INTEGER;
      const pb = order.get(b) ?? Number.MAX_SAFE_INTEGER;
      if (pa !== pb) return pa - pb;
      return a.localeCompare(b);
    })[0] ?? ""
  );
}

function cadenceMonths(notes: string, isSubscription: boolean) {
  if (!isSubscription) return 0;
  if (!notes || !notes.trim()) return 1;
  const pattern = /(\d+)\s*(?:month|months|mo|mos)/gi;
  let sum = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(notes))) {
    const value = Number.parseInt(match[1], 10);
    if (Number.isFinite(value)) sum += value;
  }
  return Math.max(1, sum || 1);
}

function toNumber(value: unknown) {
  if (value == null) return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const cleaned = String(value).replace(/,/g, "");
  const match = cleaned.match(/[-+]?\d*\.?\d+/);
  if (!match) return 0;
  const numeric = Number(match[0]);
  return Number.isFinite(numeric) ? numeric : 0;
}

function parseOrders(records: Record<string, unknown>[]): ProcessedOrder[] {
  const output: ProcessedOrder[] = [];

  const get = (row: Record<string, unknown>, candidates: string[]) => {
    const normalized = new Map<string, string>();
    for (const key of Object.keys(row)) {
      normalized.set(key.replace(/[^a-z0-9]/gi, "").toLowerCase(), key);
    }

    for (const candidate of candidates) {
      const lookup = candidate.replace(/[^a-z0-9]/gi, "").toLowerCase();
      if (normalized.has(lookup)) return row[normalized.get(lookup)!];
    }

    for (const key of Object.keys(row)) {
      const compact = key.replace(/[^a-z0-9]/gi, "").toLowerCase();
      if (candidates.some((candidate) => compact.includes(candidate.replace(/[^a-z0-9]/gi, "").toLowerCase()))) {
        return row[key];
      }
    }

    return undefined;
  };

  for (const row of records) {
    const status = String(get(row, ["Status Order", "Order Status", "Status"]) ?? "").trim().toLowerCase();
    if (status !== "delivered") continue;

    const parsedDate = parseFlexibleDate(get(row, ["Order Date", "Created At", "Date"]));
    if (!parsedDate) continue;

    const id =
      String(get(row, ["Order_id", "orderid", "id"]) ?? "").trim() ||
      `${ym(parsedDate)}:${Math.random().toString(36).slice(2)}`;
    const uid =
      String(get(row, ["name_uid", "final_id", "customer_id", "source_user_id", "user_id", "Customer"]) ?? "").trim();
    if (!uid) continue;

    const price = toNumber(get(row, ["Price", "Total", "Order Total", "Amount"]));
    const categories = splitValues(get(row, ["Category", "Categories"]));
    const skus = splitValues(get(row, ["SKUs", "SKU", "Products", "Items"]));
    const notes = String(get(row, ["Notes", "Note", "Subscription Notes", "Cadence"]) ?? "");

    output.push({
      id,
      uid,
      date: parsedDate,
      monthKey: ym(parsedDate),
      price,
      categories,
      skus,
      notes,
      status,
    });
  }

  return output;
}

export function parseOrdersCsv(buffer: Buffer | string): ProcessedOrder[] {
  const records = parseCsv(buffer, {
    columns: true,
    skip_empty_lines: true,
    trim: true,
  }) as Record<string, unknown>[];
  return parseOrders(records);
}

export async function loadOrdersFromCsv(csvPath: string): Promise<ProcessedOrder[]> {
  const buffer = await fs.readFile(csvPath);
  return parseOrdersCsv(buffer);
}

export function computeAllFromOrders(orders: ProcessedOrder[]): ComputeAllResult {
  if (!orders.length) {
    return {
      asOfMonth: "—",
      churn: { months: [], overview: [], byCategory: [], daily: [], dailyRetention: [], weeklyRetention: [], monthlyActive: [] },
      retention: [],
      ltv: [],
      survival: [],
      waterfall: [],
    };
  }

  const maxMonthInData = orders.reduce((acc, order) => (order.monthKey > acc ? order.monthKey : acc), orders[0].monthKey);
  const asOfMonth = clampAsOfMonth(maxMonthInData);

  const subscriptionMonthly = new Map<string, Set<string>>();
  const onetimeMonthly = new Map<string, Set<string>>();
  const totalMonthly = new Map<string, Set<string>>();
  const categoryMonthly = new Map<string, Map<string, Set<string>>>();

  const subscriptionDaily = new Map<string, Set<string>>();
  const onetimeDaily = new Map<string, Set<string>>();

  const asOfMonthDate = new Date(Number(asOfMonth.slice(0, 4)), Number(asOfMonth.slice(5)) - 1, 1);
  const asOfDailyCutoff = new Date(asOfMonthDate.getFullYear(), asOfMonthDate.getMonth() + 1, 0);

  for (const order of orders) {
    const categories = order.categories;
    const isSubscriptionOrder = categories.some((category) => SUBSCRIPTION_CATEGORIES.has(category));
    const subscriptionCadence = isSubscriptionOrder ? cadenceMonths(order.notes, true) : 0;

    if (isSubscriptionOrder) {
      for (let offset = 0; offset < subscriptionCadence; offset += 1) {
        const target = addMonths(new Date(order.date.getFullYear(), order.date.getMonth(), 1), offset);
        const key = ym(target);
        if (key > asOfMonth) break;

        if (!subscriptionMonthly.has(key)) subscriptionMonthly.set(key, new Set());
        subscriptionMonthly.get(key)!.add(order.uid);

        categories
          .filter((category) => SUBSCRIPTION_CATEGORIES.has(category))
          .forEach((category) => {
            if (!categoryMonthly.has(category)) categoryMonthly.set(category, new Map());
            const categoryMap = categoryMonthly.get(category)!;
            if (!categoryMap.has(key)) categoryMap.set(key, new Set());
            categoryMap.get(key)!.add(order.uid);
          });
      }
    } else {
      const monthKey = ym(order.date);
      if (!onetimeMonthly.has(monthKey)) onetimeMonthly.set(monthKey, new Set());
      onetimeMonthly.get(monthKey)!.add(order.uid);

      const spill = new Date(order.date.getTime() + 30 * DAY_MS);
      const spillKey = ym(spill);
      if (spillKey !== monthKey && spillKey <= asOfMonth) {
        if (!onetimeMonthly.has(spillKey)) onetimeMonthly.set(spillKey, new Set());
        onetimeMonthly.get(spillKey)!.add(order.uid);
      }

      categories.forEach((category) => {
        if (!categoryMonthly.has(category)) categoryMonthly.set(category, new Map());
        const categoryMap = categoryMonthly.get(category)!;
        if (!categoryMap.has(monthKey)) categoryMap.set(monthKey, new Set());
        categoryMap.get(monthKey)!.add(order.uid);
        if (spillKey !== monthKey && spillKey <= asOfMonth) {
          if (!categoryMap.has(spillKey)) categoryMap.set(spillKey, new Set());
          categoryMap.get(spillKey)!.add(order.uid);
        }
      });
    }

    const startDay = new Date(order.date.getFullYear(), order.date.getMonth(), order.date.getDate());
    const endDay = isSubscriptionOrder ? addMonths(startDay, subscriptionCadence) : new Date(order.date.getTime() + 30 * DAY_MS);

    for (let cursor = new Date(startDay); cursor <= asOfDailyCutoff && cursor < endDay; cursor = new Date(cursor.getTime() + DAY_MS)) {
      const key = ymd(cursor);
      if (isSubscriptionOrder) {
        if (!subscriptionDaily.has(key)) subscriptionDaily.set(key, new Set());
        subscriptionDaily.get(key)!.add(order.uid);
      } else {
        if (!onetimeDaily.has(key)) onetimeDaily.set(key, new Set());
        onetimeDaily.get(key)!.add(order.uid);
      }
    }
  }

  const monthKeys = new Set<string>();
  [...subscriptionMonthly.keys(), ...onetimeMonthly.keys()].forEach((monthKey) => {
    if (monthKey <= asOfMonth) monthKeys.add(monthKey);
  });
  const orderedMonths = Array.from(monthKeys).sort();

  orderedMonths.forEach((month) => {
    const combined = new Set<string>();
    subscriptionMonthly.get(month)?.forEach((uid) => combined.add(uid));
    onetimeMonthly.get(month)?.forEach((uid) => combined.add(uid));
    totalMonthly.set(month, combined);
  });

  const buildFirstSeenMap = (store: Map<string, Set<string>>) => {
    const firstSeen = new Map<string, string>();
    for (const month of orderedMonths) {
      (store.get(month) ?? new Set()).forEach((uid) => {
        if (!firstSeen.has(uid)) firstSeen.set(uid, month);
      });
    }
    return firstSeen;
  };

  const firstSeenSubscription = buildFirstSeenMap(subscriptionMonthly);
  const firstSeenOnetime = buildFirstSeenMap(onetimeMonthly);
  const firstSeenTotal = buildFirstSeenMap(totalMonthly);

  const overview: ChurnRow[] = [];

  const buildMonthlyChurn = (store: Map<string, Set<string>>, label: Segment, firstSeen: Map<string, string>) => {
    for (let index = 1; index < orderedMonths.length; index += 1) {
      const prev = store.get(orderedMonths[index - 1]) ?? new Set<string>();
      const curr = store.get(orderedMonths[index]) ?? new Set<string>();
      const prevSize = prev.size;
      const retained = Array.from(prev).filter((uid) => curr.has(uid)).length;
      const churned = prevSize - retained;
      const rawNew = Array.from(curr).filter((uid) => !prev.has(uid));
      const newUsers = rawNew.filter((uid) => firstSeen.get(uid) === orderedMonths[index]).length;
      const reactivated = rawNew.length - newUsers;
      overview.push({
        month: orderedMonths[index],
        label,
        prevActive: prevSize,
        retained,
        churned,
        churnRate: prevSize ? churned / prevSize : 0,
        reactivated,
      });
    }
  };

  buildMonthlyChurn(subscriptionMonthly, "subscribers", firstSeenSubscription);
  buildMonthlyChurn(onetimeMonthly, "onetime", firstSeenOnetime);
  buildMonthlyChurn(totalMonthly, "total", firstSeenTotal);

  const byCategory: ChurnByCategoryRow[] = [];
  for (const [category, store] of categoryMonthly.entries()) {
    for (let index = 1; index < orderedMonths.length; index += 1) {
      const prev = store.get(orderedMonths[index - 1]) ?? new Set<string>();
      const curr = store.get(orderedMonths[index]) ?? new Set<string>();
      const prevSize = prev.size;
      const retained = Array.from(prev).filter((uid) => curr.has(uid)).length;
      const churned = prevSize - retained;
      const reactivated = Array.from(curr).filter((uid) => !prev.has(uid)).length;
      byCategory.push({
        month: orderedMonths[index],
        category,
        prevActive: prevSize,
        retained,
        churned,
        churnRate: prevSize ? churned / prevSize : 0,
        reactivated,
      });
    }
  }

  const dailyKeys = Array.from(new Set([...subscriptionDaily.keys(), ...onetimeDaily.keys()])).sort();
  const daily = dailyKeys.map((key) => {
    const subs = (subscriptionDaily.get(key) ?? new Set()).size;
    const ones = (onetimeDaily.get(key) ?? new Set()).size;
    return { date: key, subscribers: subs, onetime: ones, total: subs + ones };
  });

  const buildDailyRetention = (store: Map<string, Set<string>>, label: Segment) => {
    const rows: DailyRetentionRow[] = [];
    for (let index = 1; index < dailyKeys.length; index += 1) {
      const prev = store.get(dailyKeys[index - 1]) ?? new Set<string>();
      const curr = store.get(dailyKeys[index]) ?? new Set<string>();
      const prevSize = prev.size;
      const retained = Array.from(prev).filter((uid) => curr.has(uid)).length;
      const churned = prevSize - retained;
      const reactivated = Array.from(curr).filter((uid) => !prev.has(uid)).length;
      rows.push({
        date: dailyKeys[index],
        label,
        prevActive: prevSize,
        retained,
        churned,
        churnRate: prevSize ? churned / prevSize : 0,
        retentionRate: prevSize ? retained / prevSize : 0,
        reactivated,
      });
    }
    return rows;
  };

  const totalDaily = new Map<string, Set<string>>();
  dailyKeys.forEach((key) => {
    const set = new Set<string>();
    (subscriptionDaily.get(key) ?? new Set()).forEach((uid) => set.add(uid));
    (onetimeDaily.get(key) ?? new Set()).forEach((uid) => set.add(uid));
    totalDaily.set(key, set);
  });

  const dailyRetention: DailyRetentionRow[] = [
    ...buildDailyRetention(subscriptionDaily, "subscribers"),
    ...buildDailyRetention(onetimeDaily, "onetime"),
    ...buildDailyRetention(totalDaily, "total"),
  ];

  const weeklyRetention: WeeklyRetentionRow[] = [
    ...buildWeeklyRetention(subscriptionDaily, "subscribers"),
    ...buildWeeklyRetention(onetimeDaily, "onetime"),
    ...buildWeeklyRetention(totalDaily, "total"),
  ];

  const monthlyActive = orderedMonths.map((month) => ({
    month,
    subscribers: (subscriptionMonthly.get(month) ?? new Set()).size,
    onetime: (onetimeMonthly.get(month) ?? new Set()).size,
    total: (totalMonthly.get(month) ?? new Set()).size,
  }));


  const ordersByUid = new Map<string, ProcessedOrder[]>();
  for (const order of orders) {
    if (!ordersByUid.has(order.uid)) ordersByUid.set(order.uid, []);
    ordersByUid.get(order.uid)!.push(order);
  }

  const uidFirstMonth = new Map<string, string>();
  const uidFirstCategory = new Map<string, string>();
  for (const [uid, userOrders] of ordersByUid.entries()) {
    userOrders.sort((a, b) => a.date.getTime() - b.date.getTime());
    const firstMonth = ym(userOrders[0].date);
    uidFirstMonth.set(uid, firstMonth);
    const sameMonth = userOrders.filter((order) => ym(order.date) === firstMonth);
    const categories = sameMonth.flatMap((order) => order.categories);
    uidFirstCategory.set(uid, prioritizeCategory(categories));
  }

  const purchasesByUid = new Map<string, Set<string>>();
  const purchasesByUidByCategory = new Map<string, Map<string, Set<string>>>();
  for (const order of orders) {
    const month = ym(order.date);
    if (month > asOfMonth) continue;
    if (!purchasesByUid.has(order.uid)) purchasesByUid.set(order.uid, new Set());
    purchasesByUid.get(order.uid)!.add(month);
    for (const category of order.categories) {
      if (!purchasesByUidByCategory.has(order.uid)) purchasesByUidByCategory.set(order.uid, new Map());
      const categoryMap = purchasesByUidByCategory.get(order.uid)!;
      if (!categoryMap.has(category)) categoryMap.set(category, new Set());
      categoryMap.get(category)!.add(month);
    }
  }

  const retention: RetentionOutputRow[] = [];

  const overallCohorts = new Map<string, Set<string>>();
  uidFirstMonth.forEach((cohort, uid) => {
    if (!overallCohorts.has(cohort)) overallCohorts.set(cohort, new Set());
    overallCohorts.get(cohort)!.add(uid);
  });

  for (const [cohortMonth, users] of Array.from(overallCohorts.entries()).sort()) {
    const cohortSize = users.size;
    for (let offset = 0; offset <= 12; offset += 1) {
      const targetMonth = ym(addMonths(monthKeyToDate(`${cohortMonth}-01`), offset));
      if (targetMonth > asOfMonth) break;
      let retained = 0;
      users.forEach((uid) => {
        if ((purchasesByUid.get(uid) ?? new Set()).has(targetMonth)) retained += 1;
      });
      retention.push({
        cohort_month: `${cohortMonth}-01`,
        dimension: "overall",
        first_value: "ALL",
        m: offset,
        metric: "any",
        cohort_size: cohortSize,
        retention: `${((cohortSize ? retained / cohortSize : 0) * 100).toFixed(2)}%`,
      });
    }
  }

  const categoryCohorts = new Map<string, Map<string, Set<string>>>();
  uidFirstMonth.forEach((cohort, uid) => {
    const category = uidFirstCategory.get(uid);
    if (!category) return;
    if (!categoryCohorts.has(cohort)) categoryCohorts.set(cohort, new Map());
    const cohortMap = categoryCohorts.get(cohort)!;
    if (!cohortMap.has(category)) cohortMap.set(category, new Set());
    cohortMap.get(category)!.add(uid);
  });

  for (const [cohortMonth, map] of Array.from(categoryCohorts.entries()).sort()) {
    for (const [category, users] of Array.from(map.entries()).sort()) {
      const cohortSize = users.size;
      for (let offset = 0; offset <= 12; offset += 1) {
        const targetMonth = ym(addMonths(monthKeyToDate(`${cohortMonth}-01`), offset));
        if (targetMonth > asOfMonth) break;
        let retainedAny = 0;
        let retainedSame = 0;
        users.forEach((uid) => {
          if ((purchasesByUid.get(uid) ?? new Set()).has(targetMonth)) retainedAny += 1;
          if ((purchasesByUidByCategory.get(uid)?.get(category) ?? new Set()).has(targetMonth)) retainedSame += 1;
        });
        retention.push({
          cohort_month: `${cohortMonth}-01`,
          dimension: "category",
          first_value: category,
          m: offset,
          metric: "any",
          cohort_size: cohortSize,
          retention: `${((cohortSize ? retainedAny / cohortSize : 0) * 100).toFixed(2)}%`,
        });
        retention.push({
          cohort_month: `${cohortMonth}-01`,
          dimension: "category",
          first_value: category,
          m: offset,
          metric: "same",
          cohort_size: cohortSize,
          retention: `${((cohortSize ? retainedSame / cohortSize : 0) * 100).toFixed(2)}%`,
        });
      }
    }
  }

  const revenueByUid = new Map<string, Map<string, number>>();
  const revenueByUidByCategory = new Map<string, Map<string, Map<string, number>>>();
  for (const order of orders) {
    const month = ym(order.date);
    if (month > asOfMonth) continue;
    if (!revenueByUid.has(order.uid)) revenueByUid.set(order.uid, new Map());
    const monthMap = revenueByUid.get(order.uid)!;
    monthMap.set(month, (monthMap.get(month) ?? 0) + order.price);

    if (!order.categories.length) continue;
    const share = order.price / order.categories.length;
    for (const category of order.categories) {
      if (!revenueByUidByCategory.has(order.uid)) revenueByUidByCategory.set(order.uid, new Map());
      const categoryMap = revenueByUidByCategory.get(order.uid)!;
      if (!categoryMap.has(category)) categoryMap.set(category, new Map());
      const categoryMonthMap = categoryMap.get(category)!;
      categoryMonthMap.set(month, (categoryMonthMap.get(month) ?? 0) + share);
    }
  }

  const ltv: LtvOutputRow[] = [];

  for (const [cohortMonth, users] of Array.from(overallCohorts.entries()).sort()) {
    const cohortSize = users.size;
    for (let offset = 0; offset <= 12; offset += 1) {
      const targetDate = addMonths(monthKeyToDate(`${cohortMonth}-01`), offset);
      if (ym(targetDate) > asOfMonth) break;
      let total = 0;
      users.forEach((uid) => {
        const monthRevenue = revenueByUid.get(uid) ?? new Map();
        for (let step = 0; step <= offset; step += 1) {
          const key = ym(addMonths(monthKeyToDate(`${cohortMonth}-01`), step));
          total += monthRevenue.get(key) ?? 0;
        }
      });
      ltv.push({
        cohort_type: "purchase",
        cohort_month: `${cohortMonth}-01`,
        dimension: "overall",
        first_value: "ALL",
        m: offset,
        metric: "any",
        measure: "revenue",
        cohort_size: cohortSize,
        ltv_per_user: cohortSize ? Number((total / cohortSize).toFixed(2)) : 0,
      });
    }
  }

  for (const [cohortMonth, map] of Array.from(categoryCohorts.entries()).sort()) {
    for (const [category, users] of Array.from(map.entries()).sort()) {
      const cohortSize = users.size;
      for (let offset = 0; offset <= 12; offset += 1) {
        const targetDate = addMonths(monthKeyToDate(`${cohortMonth}-01`), offset);
        if (ym(targetDate) > asOfMonth) break;
        let totalAny = 0;
        let totalSame = 0;
        users.forEach((uid) => {
          const monthRevenue = revenueByUid.get(uid) ?? new Map();
          for (let step = 0; step <= offset; step += 1) {
            const key = ym(addMonths(monthKeyToDate(`${cohortMonth}-01`), step));
            totalAny += monthRevenue.get(key) ?? 0;
          }
          const categoryRevenue = revenueByUidByCategory.get(uid)?.get(category) ?? new Map();
          for (let step = 0; step <= offset; step += 1) {
            const key = ym(addMonths(monthKeyToDate(`${cohortMonth}-01`), step));
            totalSame += categoryRevenue.get(key) ?? 0;
          }
        });
        ltv.push({
          cohort_type: "purchase",
          cohort_month: `${cohortMonth}-01`,
          dimension: "category",
          first_value: category,
          m: offset,
          metric: "any",
          measure: "revenue",
          cohort_size: cohortSize,
          ltv_per_user: cohortSize ? Number((totalAny / cohortSize).toFixed(2)) : 0,
        });
        ltv.push({
          cohort_type: "purchase",
          cohort_month: `${cohortMonth}-01`,
          dimension: "category",
          first_value: category,
          m: offset,
          metric: "same",
          measure: "revenue",
          cohort_size: cohortSize,
          ltv_per_user: cohortSize ? Number((totalSame / cohortSize).toFixed(2)) : 0,
        });
      }
    }
  }

  const survival: SurvivalOutputRow[] = [];
  for (const category of SUBSCRIPTION_CATEGORIES) {
    const store = categoryMonthly.get(category);
    if (!store) continue;

    const firstSeen = new Map<string, string>();
    Array.from(store.keys())
      .sort()
      .forEach((month) => {
        store.get(month)!.forEach((uid) => {
          if (!firstSeen.has(uid)) firstSeen.set(uid, month);
        });
      });

    const cohorts = new Map<string, Set<string>>();
    firstSeen.forEach((month, uid) => {
      if (!cohorts.has(month)) cohorts.set(month, new Set());
      cohorts.get(month)!.add(uid);
    });

    for (const [cohortMonth, users] of Array.from(cohorts.entries()).sort()) {
      const cohortSize = users.size;
      for (let offset = 0; offset <= 12; offset += 1) {
        const targetMonth = ym(addMonths(monthKeyToDate(`${cohortMonth}-01`), offset));
        if (targetMonth > asOfMonth) break;
        const active = store.get(targetMonth) ?? new Set();
        const stillActive = Array.from(users).filter((uid) => active.has(uid)).length;
        survival.push({
          cohort_month: `${cohortMonth}-01`,
          category,
          m: offset,
          cohort_size: cohortSize,
          survival_rate: cohortSize ? stillActive / cohortSize : 0,
        });
      }
    }
  }

  const waterfall: WaterfallOutputRow[] = [];

  const buildWaterfall = (category: string, store: Map<string, Set<string>>, unionStore?: Map<string, Set<string>>) => {
    let previous = new Set<string>();
    const seenBefore = new Set<string>();

    for (const month of orderedMonths) {
      const source = unionStore ?? store;
      const current = new Set<string>(source.get(month) ?? new Set<string>());
      const startActive = previous.size;
      const retained = new Set(Array.from(previous).filter((uid) => current.has(uid)));
      const churned = previous.size - retained.size;
      const newActive = new Set(Array.from(current).filter((uid) => !previous.has(uid)));
      const reactivated = Array.from(newActive).filter((uid) => seenBefore.has(uid)).length;

      waterfall.push({
        month: `${month}-01`,
        category,
        start_active: startActive,
        new_active: newActive.size,
        reactivated,
        churned,
        end_active: current.size,
      });

      current.forEach((uid) => seenBefore.add(uid));
      previous = current;
    }
  };

  buildWaterfall("ALL", totalMonthly, totalMonthly);
  for (const [category, store] of categoryMonthly.entries()) {
    buildWaterfall(category, store);
  }

  return {
    asOfMonth,
    churn: {
      months: orderedMonths,
      overview,
      byCategory,
      daily,
      dailyRetention,
      weeklyRetention,
      monthlyActive,
    },
    retention,
    ltv,
    survival,
    waterfall,
  };
}

export async function computeAllFromAllOrders(csvPath: string): Promise<ComputeAllResult> {
  const orders = await loadOrdersFromCsv(csvPath);
  return computeAllFromOrders(orders);
}

export function computeAllFromBuffer(buffer: Buffer | string): ComputeAllResult {
  const orders = parseOrdersCsv(buffer);
  return computeAllFromOrders(orders);
}

export async function computeAllFromDefaultOrders(): Promise<ComputeAllResult> {
  const csvPath = path.join(process.cwd(), "public", "data", "allorders.csv");
  return computeAllFromAllOrders(csvPath);
}
