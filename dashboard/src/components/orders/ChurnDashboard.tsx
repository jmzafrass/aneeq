'use client';

import { useEffect, useMemo, useState } from "react";
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

import type { ChurnByCategoryRow, ChurnSummary } from "@/lib/orders/types";

const CATEGORY_COLORS = [
  "#1d4ed8",
  "#0ea5e9",
  "#f97316",
  "#16a34a",
  "#a855f7",
  "#f43f5e",
  "#64748b",
];

interface ChurnResponse {
  churn: ChurnSummary;
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

export function ChurnDashboard() {
  const [data, setData] = useState<ChurnSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSeries, setSelectedSeries] = useState<
    "all" | "subscribers_churn" | "onetime_churn" | "total_churn"
  >("all");
  const [selectedDaily, setSelectedDaily] = useState<
    "all" | "subscribers_ret" | "onetime_ret" | "total_ret"
  >("all");

  async function fetchChurn() {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch("/api/orders/compute?source=default", { method: "POST" });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Request failed");
      }
      const payload = (await response.json()) as ChurnResponse;
      setData(payload.churn);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchChurn();
  }, []);

  const overviewRows = useMemo(() => {
    if (!data) return [] as Array<Record<string, string | number>>;
    return data.overview.map((row) => ({
      Month: row.month,
      Segment: row.label,
      "Prev active": row.prevActive,
      Retained: row.retained,
      Churned: row.churned,
      "Churn rate": formatPercent(row.churnRate),
      Reactivated: row.reactivated,
    }));
  }, [data]);

  const categoryRows = useMemo(() => {
    if (!data) return [] as Array<Record<string, string | number>>;
    return data.byCategory.map((row: ChurnByCategoryRow) => ({
      Month: row.month,
      Category: row.category,
      "Prev active": row.prevActive,
      Retained: row.retained,
      Churned: row.churned,
      "Churn rate": formatPercent(row.churnRate),
      Reactivated: row.reactivated,
    }));
  }, [data]);

  const churnChartData = useMemo(() => {
    if (!data) return [] as Array<Record<string, number | string>>;
    const map = new Map<string, Record<string, number | string>>();
    data.overview.forEach((row) => {
      const bucket = map.get(row.month) ?? { month: row.month };
      bucket[`${row.label}_churn`] = row.churnRate * 100;
      map.set(row.month, bucket);
    });
    return Array.from(map.values()).sort((a, b) => String(a.month).localeCompare(String(b.month)));
  }, [data]);

  const isSeriesVisible = (key: "subscribers_churn" | "onetime_churn" | "total_churn") =>
    selectedSeries === "all" || selectedSeries === key;

  const dailyChartData = useMemo(() => {
    if (!data) return [] as Array<Record<string, number | string>>;
    return data.daily.map((row) => ({
      date: row.date,
      subscribers: row.subscribers,
      onetime: row.onetime,
      total: row.total,
    }));
  }, [data]);

  const categoryChartData = useMemo(() => {
    if (!data) return [] as Array<Record<string, number | string>>;
    const map = new Map<string, Record<string, number | string>>();
    data.byCategory.forEach((row) => {
      const bucket = map.get(row.month) ?? { month: row.month };
      bucket[row.category] = row.churnRate * 100;
      map.set(row.month, bucket);
    });
    return Array.from(map.values()).sort((a, b) => String(a.month).localeCompare(String(b.month)));
  }, [data]);

  const categorySet = useMemo(() => {
    if (!data) return [] as string[];
    return Array.from(new Set(data.byCategory.map((row) => row.category))).sort();
  }, [data]);

  const dailyRetentionChartData = useMemo(() => {
    if (!data) return [] as Array<Record<string, number | string>>;
    const map = new Map<string, Record<string, number | string>>();
    data.dailyRetention.forEach((row) => {
      const bucket = map.get(row.date) ?? { date: row.date };
      bucket[`${row.label}_ret`] = row.retentionRate * 100;
      map.set(row.date, bucket);
    });
    return Array.from(map.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [data]);

  const isDailyVisible = (key: "subscribers_ret" | "onetime_ret" | "total_ret") =>
    selectedDaily === "all" || selectedDaily === key;

  return (
    <div className="space-y-5">
      <section className="flex flex-wrap items-center gap-3">
        <button
          className="px-4 py-2 rounded-md bg-blue-600 text-white disabled:opacity-60"
          onClick={() => fetchChurn()}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh churn"}
        </button>
        {error && <span className="text-sm text-red-600">{error}</span>}
        <span className="text-xs text-gray-500">
          Delivered orders only • Subscriptions defined as POM HL & POM BG coverage windows.
        </span>
      </section>

      {data && (
        <div className="space-y-5">
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="mb-2 text-sm font-semibold text-slate-900">Monthly churn rates</div>
            <div className="mb-3 flex flex-wrap gap-2 text-xs">
              {[
                { key: "all" as const, label: "All" },
                { key: "subscribers_churn" as const, label: "Subscribers" },
                { key: "onetime_churn" as const, label: "One-time" },
                { key: "total_churn" as const, label: "Total" },
              ].map((option) => {
                const active = selectedSeries === option.key;
                return (
                  <button
                    key={option.key}
                    type="button"
                    onClick={() => setSelectedSeries(option.key)}
                    aria-pressed={active}
                    className={`rounded-full border px-3 py-1 transition-colors ${
                      active ? "border-blue-600 bg-blue-600 text-white" : "border-gray-200 bg-gray-100 text-gray-700"
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={churnChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" interval={0} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(value) => `${value.toFixed(1)}%`} />
                <Tooltip formatter={(value: number) => [`${value.toFixed(2)}%`, "Churn"]} />
                <Legend />
                {isSeriesVisible("subscribers_churn") && (
                  <Line type="monotone" dataKey="subscribers_churn" name="Subscribers" stroke="#1d4ed8" dot />
                )}
                {isSeriesVisible("onetime_churn") && (
                  <Line type="monotone" dataKey="onetime_churn" name="One-time" stroke="#f97316" dot />
                )}
                {isSeriesVisible("total_churn") && (
                  <Line type="monotone" dataKey="total_churn" name="Total" stroke="#16a34a" dot />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="mb-2 text-sm font-semibold text-slate-900">Daily retention rate</div>
            <div className="mb-3 flex flex-wrap gap-2 text-xs">
              {[
                { key: "all" as const, label: "All" },
                { key: "subscribers_ret" as const, label: "Subscribers" },
                { key: "onetime_ret" as const, label: "One-time" },
                { key: "total_ret" as const, label: "Total" },
              ].map((option) => {
                const active = selectedDaily === option.key;
                return (
                  <button
                    key={option.key}
                    type="button"
                    onClick={() => setSelectedDaily(option.key)}
                    aria-pressed={active}
                    className={`rounded-full border px-3 py-1 transition-colors ${
                      active ? "border-blue-600 bg-blue-600 text-white" : "border-gray-200 bg-gray-100 text-gray-700"
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={dailyRetentionChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" minTickGap={20} />
                <YAxis tickFormatter={(value) => `${value.toFixed(1)}%`} />
                <Tooltip formatter={(value: number) => [`${value.toFixed(2)}%`, "Retention"]} />
                <Legend />
                {isDailyVisible("subscribers_ret") && (
                  <Line type="monotone" dataKey="subscribers_ret" name="Subscribers" stroke="#1d4ed8" dot={false} />
                )}
                {isDailyVisible("onetime_ret") && (
                  <Line type="monotone" dataKey="onetime_ret" name="One-time" stroke="#f97316" dot={false} />
                )}
                {isDailyVisible("total_ret") && (
                  <Line type="monotone" dataKey="total_ret" name="Total" stroke="#16a34a" dot={false} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="mb-2 text-sm font-semibold text-slate-900">Daily active coverage (customers)</div>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={dailyChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" minTickGap={20} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="subscribers" name="Subscribers" stackId="one" stroke="#1d4ed8" fill="#bfdbfe" />
                <Area type="monotone" dataKey="onetime" name="One-time" stackId="one" stroke="#f97316" fill="#fed7aa" />
                <Area type="monotone" dataKey="total" name="Total" stroke="#16a34a" fill="#bbf7d0" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="mb-2 text-sm font-semibold text-slate-900">Monthly churn by category</div>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={categoryChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" interval={0} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(value) => `${value.toFixed(1)}%`} />
                <Tooltip formatter={(value: number) => [`${value.toFixed(2)}%`, "Churn"]} />
                <Legend />
                {categorySet.map((category, index) => (
                  <Line
                    key={category}
                    type="monotone"
                    dataKey={category}
                    stroke={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <DataTable title="Logo churn overview" rows={overviewRows} />
          <DataTable title="Churn by category" rows={categoryRows} />
        </div>
      )}
    </div>
  );
}

function DataTable({ title, rows }: { title: string; rows: Array<Record<string, string | number>> }) {
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
              <tr key={`${row[columns[0]]}-${index}`} className="hover:bg-gray-50">
                {columns.map((column) => (
                  <td key={`${column}-${index}`} className="whitespace-nowrap px-3 py-2 text-gray-700">
                    {row[column]}
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
