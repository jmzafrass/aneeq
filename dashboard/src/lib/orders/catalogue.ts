import { MAGENTA_START_KEY, SKU_CATEGORY_MAP } from "./constants";
import type { CatalogueRow, CatalogueSummary, ProcessedOrderRow } from "./types";

const LEGACY_COGS: Record<string, number> = {
  "ultimate revival": 465.12,
  "power regrowth": 444.21,
  "essential boost": 235.75,
  "oral mix": 233.74,
  "oral minoxidil": 214.99,
  "vital recharge": 235.75,
  "max power": 332.95,
  "delay spray": 69.04,
  "essential routine": 62.32,
  "advanced routine": 80.48,
  cleanser: 23.73,
  "moisturizer spf": 23.73,
  moisturizer: 26.0,
  "eye cream": 28.27,
  serum: 23.73,
  shampoo: 23.73,
  conditioner: 23.73,
  "regrowth hair pack": 37.35,
  "regrowth pack": 37.35,
  "beard growth serum": 159.0,
};

const MAGENTA_COGS: Record<string, number> = {
  "ultimate revival": 284.7,
  "power regrowth": 271.7,
  "essential boost": 142.35,
  "oral mix": 142.35,
  "oral minoxidil": 129.35,
  "vital recharge": 142.35,
  "max power": 207.35,
  "delay spray": 69.04,
  "essential routine": 62.32,
  "advanced routine": 80.48,
  cleanser: 23.73,
  "moisturizer spf": 23.73,
  moisturizer: 26.0,
  "eye cream": 28.27,
  serum: 23.73,
  shampoo: 23.73,
  conditioner: 23.73,
  "regrowth hair pack": 37.35,
  "regrowth pack": 37.35,
  "beard growth serum": 159.0,
};

function isMagentaMonth(orderMonth: string) {
  return orderMonth >= MAGENTA_START_KEY;
}

function normSku(sku: string) {
  return sku.toLowerCase().trim();
}

export function computeCatalogueSummary(orders: ProcessedOrderRow[]): CatalogueSummary {
  const skuStats = new Map<string, {
    units: number;
    revenue: number;
    cogs: number;
    category: string;
    marginLabel: string;
  }>();

  for (const order of orders) {
    if (!Number.isFinite(order.price)) continue;
    if (!order.skuNames.length) continue;

    for (const rawSku of order.skuNames) {
      const sku = normSku(rawSku);
      const category = SKU_CATEGORY_MAP[sku] ?? "Unknown";
      const stats = skuStats.get(sku) ?? { units: 0, revenue: 0, cogs: 0, category, marginLabel: "" };
      stats.units += 1;
      stats.revenue += order.price;

      const cogsTable = isMagentaMonth(order.order_month) ? MAGENTA_COGS : LEGACY_COGS;
      const cogsPerUnit = cogsTable[sku] ?? 0;
      stats.cogs += cogsPerUnit;
      if (!stats.marginLabel && isMagentaMonth(order.order_month) && (MAGENTA_COGS[sku] ?? 0) !== (LEGACY_COGS[sku] ?? 0)) {
        stats.marginLabel = "Magenta pricing";
      }
      skuStats.set(sku, stats);
    }
  }

  const rows: CatalogueRow[] = Array.from(skuStats.entries()).map(([sku, stats]) => {
    const avgPrice = stats.units ? stats.revenue / stats.units : 0;
    const cogsPerUnit = stats.units ? stats.cogs / stats.units : 0;
    const takeRate = stats.revenue ? (stats.revenue - stats.cogs) / stats.revenue : 0;
    return {
      category: stats.category,
      sku,
      units: stats.units,
      avgPrice,
      revenue: stats.revenue,
      cogsPerUnit,
      cogsTotal: stats.cogs,
      takeRate,
      marginLabel: stats.marginLabel,
    };
  });

  rows.sort((a, b) => a.category.localeCompare(b.category) || a.sku.localeCompare(b.sku));

  const totals = rows.reduce(
    (acc, row) => {
      acc.units += row.units;
      acc.revenue += row.revenue;
      acc.cogs += row.cogsTotal;
      return acc;
    },
    { units: 0, revenue: 0, cogs: 0 },
  );

  const totalTakeRate = totals.revenue ? (totals.revenue - totals.cogs) / totals.revenue : 0;

  return {
    rows,
    totals: {
      units: totals.units,
      revenue: totals.revenue,
      cogs: totals.cogs,
      takeRate: totalTakeRate,
    },
  };
}
