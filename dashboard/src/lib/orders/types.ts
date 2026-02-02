export type Vertical = "pom hl" | "pom sh" | "otc hl" | "otc sh" | "otc sk" | "pom bg";

export interface ProcessedOrderRow {
  order_key: string;
  order_ts: Date;
  order_month: string;
  price: number;
  skuNames: string[];
  verticals: Set<Vertical>;
  customerId: string;
  customerLabel: string;
  notes: string;
}

export interface MomOrdersRow {
  month: string;
  orders: number;
  orders_mom_abs: number | null;
  orders_mom_pct: number | null;
  ado: number;
  ado_pacing: number | null;
  is_partial: 0 | 1;
}

export interface MomOrdersByVerticalRow {
  month: string;
  vertical: Vertical;
  orders: number;
  orders_mom_abs: number | null;
  orders_mom_pct: number | null;
  ado_vertical: number;
  ado_vertical_pacing: number | null;
  is_partial: 0 | 1;
}

export interface OrdersQA {
  noVerticalPct: number;
  multiVerticalPct: number;
  unknownCount: number;
  headlineVsVerticals: Array<{ month: string; headline: number; vertical_sum: number; delta: number }>;
}

export interface ProcessOrdersResult {
  momOrders: MomOrdersRow[];
  momOrdersByVertical: MomOrdersByVerticalRow[];
  qa: OrdersQA;
  processedOrders: ProcessedOrderRow[];
  churn: ChurnSummary;
}

export interface CatalogueRow {
  category: string;
  sku: string;
  units: number;
  avgPrice: number;
  revenue: number;
  cogsPerUnit: number;
  cogsTotal: number;
  takeRate: number;
  marginLabel: string;
}

export interface CatalogueSummary {
  rows: CatalogueRow[];
  totals: {
    units: number;
    revenue: number;
    cogs: number;
    takeRate: number;
  };
}

export interface ChurnRow {
  month: string;
  label: "subscribers" | "onetime" | "total";
  prevActive: number;
  retained: number;
  churned: number;
  churnRate: number;
  reactivated: number;
}

export interface ChurnByCategoryRow {
  month: string;
  category: string;
  prevActive: number;
  retained: number;
  churned: number;
  churnRate: number;
  reactivated: number;
}

export interface ChurnSummary {
  months: string[];
  overview: ChurnRow[];
  byCategory: ChurnByCategoryRow[];
  daily: Array<{ date: string; subscribers: number; onetime: number; total: number }>;
  dailyRetention: DailyRetentionRow[];
  weeklyRetention: WeeklyRetentionRow[];
  monthlyActive: Array<{ month: string; subscribers: number; onetime: number; total: number }>;
}

export interface DailyRetentionRow {
  date: string;
  label: "subscribers" | "onetime" | "total";
  prevActive: number;
  retained: number;
  churned: number;
  churnRate: number;
  retentionRate: number;
  reactivated: number;
}

export interface WeeklyRetentionRow {
  week: string;
  label: "subscribers" | "onetime" | "total";
  prevActive: number;
  retained: number;
  churned: number;
  retentionRate: number;
}
