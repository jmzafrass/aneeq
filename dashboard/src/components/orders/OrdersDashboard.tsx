'use client';

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  CatalogueSummary,
  MomOrdersByVerticalRow,
  MomOrdersRow,
} from "@/lib/orders/types";

interface ApiResponse {
  momOrders: MomOrdersRow[];
  momOrdersByVertical: MomOrdersByVerticalRow[];
  qa: {
    noVerticalPct: number;
    multiVerticalPct: number;
    unknownCount: number;
    headlineVsVerticals: Array<{ month: string; headline: number; vertical_sum: number; delta: number }>;
  };
  catalogue: CatalogueSummary;
  churn: {
    months: string[];
  };
}

const VERTICALS: MomOrdersByVerticalRow["vertical"][] = ["pom hl", "pom sh", "otc hl", "otc sh", "otc sk", "pom bg"];

const COLORS: Record<string, string> = {
  "pom hl": "#1d4ed8",
  "pom sh": "#0ea5e9",
  "otc hl": "#16a34a",
  "otc sh": "#f97316",
  "otc sk": "#a855f7",
  "pom bg": "#f43f5e",
};

interface TableRow {
  [key: string]: string | number;
}

export function OrdersDashboard() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(downloadExcel = false) {
    setLoading(true);
    setError(null);

    const endpoint = downloadExcel ? "/api/orders/compute.xlsx" : "/api/orders/compute";
    const url = `${endpoint}?source=default`;
    const options: RequestInit = { method: "POST" };

    try {
      const response = await fetch(url, options);

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Request failed");
      }

      if (downloadExcel) {
        const blob = await response.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = downloadUrl;
        anchor.download = "mom_orders_outputs.xlsx";
        anchor.click();
        URL.revokeObjectURL(downloadUrl);
      } else {
        const payload = (await response.json()) as ApiResponse;
        setData(payload);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void handleSubmit(false);
  }, []);

  const headlineSeries = useMemo(() => data?.momOrders ?? [], [data]);

  const verticalSeries = useMemo(() => {
    if (!data) return [] as Array<Record<string, number | string>>;
    const base = new Map<string, Record<string, number | string>>();

    data.momOrders.forEach((row) => {
      base.set(row.month, {
        month: row.month,
        orders: row.orders,
        ado: row.ado,
        ado_pacing: row.ado_pacing ?? 0,
      });
    });

    data.momOrdersByVertical.forEach((row) => {
      const bucket = base.get(row.month) ?? { month: row.month };
      bucket[row.vertical] = row.orders;
      base.set(row.month, bucket);
    });

    return Array.from(base.values()).sort((a, b) => String(a.month).localeCompare(String(b.month)));
  }, [data]);

  const qaRows: TableRow[] = useMemo(() => {
    if (!data) return [];
    return [
      {
        metric: "% delivered orders with NO mapped vertical",
        value: `${data.qa.noVerticalPct.toFixed(2)}%`,
      },
      {
        metric: "% delivered orders with MULTIPLE verticals",
        value: `${data.qa.multiVerticalPct.toFixed(2)}%`,
      },
      {
        metric: "Delivered orders with unknown vertical",
        value: data.qa.unknownCount,
      },
      ...data.qa.headlineVsVerticals.map((row) => ({
        metric: `Headline vs vertical sum — ${row.month}`,
        value: `headline=${row.headline}, vertical_sum=${row.vertical_sum}, delta=${row.delta}`,
      })),
    ];
  }, [data]);

  const catalogueRows: TableRow[] = useMemo(() => {
    if (!data) return [];
    const formatter = (value: number) => `Dh ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    const pct = (value: number) => `${(value * 100).toFixed(2)}%`;

    const rows: TableRow[] = data.catalogue.rows.map((row) => ({
      Category: row.category,
      SKU: row.sku,
      Units: row.units,
      "Avg price": formatter(row.avgPrice),
      Revenue: formatter(row.revenue),
      "CoGS / unit": formatter(row.cogsPerUnit),
      "CoGS total": formatter(row.cogsTotal),
      "Take rate": pct(row.takeRate),
      Notes: row.marginLabel,
    }));

    rows.push({});
    rows.push({
      Category: "Totals",
      Units: data.catalogue.totals.units,
      Revenue: formatter(data.catalogue.totals.revenue),
      "CoGS total": formatter(data.catalogue.totals.cogs),
      "Take rate": pct(data.catalogue.totals.takeRate),
    });

    return rows;
  }, [data]);

  return (
    <div className="space-y-5">
      <section className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <button
            className="px-4 py-2 rounded-md bg-blue-600 text-white disabled:opacity-60"
            onClick={() => handleSubmit(false)}
            disabled={loading}
          >
            {loading ? "Processing…" : "Refresh default data"}
          </button>
          <button
            className="px-4 py-2 rounded-md bg-gray-200 disabled:opacity-60"
            onClick={() => handleSubmit(true)}
            disabled={loading}
          >
            Download Excel
          </button>
        </div>
        {error && <span className="block text-sm text-red-600">{error}</span>}
      </section>

      {data && (
        <div className="space-y-5">
          <section className="grid md:grid-cols-4 gap-4">
            <KpiCard
              label="Latest month"
              value={headlineSeries.at(-1)?.month ?? "—"}
            />
            <KpiCard
              label="Delivered orders"
              value={headlineSeries.at(-1)?.orders ?? 0}
            />
            <KpiCard
              label="ADO"
              value={(headlineSeries.at(-1)?.ado ?? 0).toFixed(3)}
              caption={headlineSeries.at(-1)?.is_partial ? "Full month basis" : undefined}
            />
            <KpiCard
              label="ADO (pacing)"
              value={headlineSeries.at(-1)?.ado_pacing == null ? "—" : (headlineSeries.at(-1)?.ado_pacing ?? 0).toFixed(3)}
              caption={headlineSeries.at(-1)?.is_partial ? "Partial month" : "Same as ADO"}
            />
          </section>

          <ChartCard title="Delivered orders per month">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={headlineSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" interval={0} tick={{ fontSize: 12 }} />
                <YAxis />
                <Tooltip formatter={(value: number) => [value, "Orders"]} />
                <Legend />
                <Line type="monotone" dataKey="orders" stroke="#1d4ed8" dot />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Average daily orders">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={headlineSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" interval={0} tick={{ fontSize: 12 }} />
                <YAxis />
                <Tooltip
                  formatter={(value: number, name) => [value.toFixed(3), name === "ado" ? "ADO" : "ADO pacing"]}
                />
                <Legend />
                <Line type="monotone" dataKey="ado" stroke="#0ea5e9" dot />
                <Line type="monotone" dataKey="ado_pacing" stroke="#f97316" dot connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Orders by vertical (multi-credit)">
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={verticalSeries} stackOffset="expand">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" interval={0} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(value) => `${Math.round(value * 100)}%`} />
                <Tooltip
                  formatter={(value: number, name) => [Math.round(value), name]}
                />
                <Legend />
                {VERTICALS.map((vertical) => (
                  <Area
                    key={vertical}
                    type="monotone"
                    stackId="one"
                    dataKey={vertical}
                    stroke={COLORS[vertical]}
                    fill={COLORS[vertical]}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <DataTable
            title="MoM orders (delivered only)"
            rows={headlineSeries.map((row) => ({
              Month: row.month,
              Orders: row.orders,
              "MoM Δ": row.orders_mom_abs ?? "",
              "MoM %": row.orders_mom_pct == null ? "" : `${(row.orders_mom_pct * 100).toFixed(1)}%`,
              ADO: row.ado.toFixed(3),
              "ADO pacing": row.ado_pacing == null ? "" : row.ado_pacing.toFixed(3),
              Partial: row.is_partial ? "Yes" : "",
            }))}
          />

          <DataTable
            title="MoM orders per vertical (delivered only)"
            rows={data.momOrdersByVertical.map((row) => ({
              Month: row.month,
              Vertical: row.vertical,
              Orders: row.orders,
              "MoM Δ": row.orders_mom_abs ?? "",
              "MoM %": row.orders_mom_pct == null ? "" : `${(row.orders_mom_pct * 100).toFixed(1)}%`,
              "ADO (vertical)": row.ado_vertical.toFixed(3),
              "ADO pacing": row.ado_vertical_pacing == null ? "" : row.ado_vertical_pacing.toFixed(3),
              Partial: row.is_partial ? "Yes" : "",
            }))}
          />

          <DataTable
            title="QA summary"
            rows={qaRows}
          />

          {catalogueRows.length > 0 && (
            <DataTable title="Product catalogue (delivered orders)" rows={catalogueRows} />
          )}
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value, caption }: { label: string; value: string | number; caption?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-2xl font-semibold text-slate-900">{value}</div>
      {caption && <div className="text-xs text-gray-400">{caption}</div>}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-2 text-sm font-semibold text-slate-900">{title}</div>
      {children}
    </div>
  );
}

function DataTable({ title, rows }: { title: string; rows: TableRow[] }) {
  if (!rows.length) return null;
  const columns = Object.keys(rows[0]);
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-2 text-sm font-semibold text-slate-900">{title}</div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column} className="whitespace-nowrap bg-gray-50 px-3 py-2 text-left font-medium text-gray-600">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row, index) => (
              <tr key={index} className="hover:bg-gray-50">
                {columns.map((column) => (
                  <td key={column} className="whitespace-nowrap px-3 py-2 text-gray-700">
                    {row[column] as ReactNode}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
