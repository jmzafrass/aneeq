'use client';

import { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";

import type { ActiveUsersRow } from "@/lib/analytics/types";
import { classNames } from "@/lib/analytics/utils";

interface UsersDashboardProps {
  rows: ActiveUsersRow[];
  isLoading: boolean;
  error?: Error | null;
  usingFallback: boolean;
}

interface GrowthPoint {
  period: string;
  monthLabel: string;
  inc: number;
  pct: number;
}

interface SpendSlice {
  name: string;
  value: number;
  cac: number;
}

interface ConversionSlice {
  name: string;
  value: number;
}

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#22c55e"];

const USD_SUMMARY = [
  {
    channel: "Paid Social (Facebook/Meta)",
    new_customers: 253,
    spend_dollars: 78597.2752,
    cac_dollars: 310.6611668,
  },
  {
    channel: "Paid Search (Google)",
    new_customers: 62,
    spend_dollars: 13999.90191,
    cac_dollars: 225.8048695,
  },
  { channel: "Organic", new_customers: 170, spend_dollars: 0, cac_dollars: 0 },
  { channel: "Referral/Affiliate", new_customers: 34, spend_dollars: 0, cac_dollars: 0 },
] as const;

const CAC_BLENDED_RAW: { month: string; blended_cac_total: number }[] = [
  { month: "2024-10-01", blended_cac_total: 275.56766576666666 },
  { month: "2024-11-01", blended_cac_total: 574.6594005714286 },
  { month: "2024-12-01", blended_cac_total: 194.76552415789473 },
  { month: "2025-01-01", blended_cac_total: 335.84883309130436 },
  { month: "2025-02-01", blended_cac_total: 263.3434845294118 },
  { month: "2025-03-01", blended_cac_total: 164.09049624242425 },
  { month: "2025-04-01", blended_cac_total: 121.94869867816092 },
  { month: "2025-05-01", blended_cac_total: 157.03377477906977 },
  { month: "2025-06-01", blended_cac_total: 153.2031486688889 },
  { month: "2025-07-01", blended_cac_total: 160.63289575 },
  { month: "2025-08-01", blended_cac_total: 166.23776364814816 },
];

function formatCurrency(value: number) {
  return `$ ${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function UsersDashboard({ rows, isLoading, error, usingFallback }: UsersDashboardProps) {
  const [userTab, setUserTab] = useState<"active" | "cac">("active");

  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => String(a.month).localeCompare(String(b.month)));
  }, [rows]);

  const chartData = useMemo(() => {
    return sorted.map((row) => ({
      month: String(row.month).slice(0, 7),
      Total: row.active_total,
      Subscribers: row.active_subscribers,
      OneTime: row.active_onetime,
      isProjected: Number(row.is_future_vs_today ?? 0) === 1,
    }));
  }, [sorted]);

  const actualRows = useMemo(() => {
    return sorted.filter((row) => Number(row.is_future_vs_today ?? 0) === 0);
  }, [sorted]);

  const headline = useMemo(() => {
    const last = actualRows.at(-1);
    if (!last) {
      return { current: 0, subsShare: 0 };
    }
    const subsShare = last.active_total ? (last.active_subscribers / last.active_total) * 100 : 0;
    return { current: last.active_total, subsShare };
  }, [actualRows]);

  const growthSeries = useMemo(() => {
    const points: GrowthPoint[] = [];
    for (let i = 1; i < actualRows.length; i += 1) {
      const prev = actualRows[i - 1];
      const curr = actualRows[i];
      const inc = curr.active_total - prev.active_total;
      const pct = prev.active_total ? (inc / prev.active_total) * 100 : 0;
      const prevLabel = String(prev.month).slice(0, 7);
      const currLabel = String(curr.month).slice(0, 7);
      points.push({
        period: `${prevLabel} → ${currLabel}`,
        monthLabel: currLabel,
        inc,
        pct,
      });
    }
    return points;
  }, [actualRows]);

  const cacBlended = useMemo(() => {
    return CAC_BLENDED_RAW.map((entry) => ({
      month: String(entry.month).slice(0, 7),
      blended: Number(entry.blended_cac_total || 0),
    }));
  }, []);

  const projectedCount = chartData.filter((d) => d.isProjected).length;

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <button
          className={classNames(
            "px-4 py-2 rounded-lg text-sm font-medium",
            userTab === "active" ? "bg-blue-600 text-white" : "bg-gray-200",
          )}
          onClick={() => setUserTab("active")}
        >
          Active Users
        </button>
        <button
          className={classNames(
            "px-4 py-2 rounded-lg text-sm font-medium",
            userTab === "cac" ? "bg-blue-600 text-white" : "bg-gray-200",
          )}
          onClick={() => setUserTab("cac")}
        >
          CAC Overview
        </button>
      </div>

      {userTab === "active" ? (
        <div className="space-y-5">
          <div className="bg-white p-4 rounded-xl shadow">
            <div className="text-sm font-medium mb-1">Active users data source</div>
            <div className="text-xs text-gray-600 break-all">
              {usingFallback ? "Embedded fallback sample" : "Computed from delivered orders"}
            </div>
            <div className="text-[11px] text-gray-500 mt-1">Parsed rows: {rows.length}</div>
            {projectedCount > 0 && (
              <div className="text-[11px] text-gray-500">Projected months: {projectedCount}</div>
            )}
            {error && <div className="mt-2 text-xs text-red-600">{String(error)}</div>}
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl shadow">
              <div className="text-sm text-gray-600">Current Active Users</div>
              <div className="text-2xl font-bold text-blue-600">{headline.current}</div>
              <div className="text-xs text-gray-500">Latest actual month</div>
            </div>
            <div className="bg-white p-4 rounded-xl shadow">
              <div className="text-sm text-gray-600">Subscriber Share</div>
              <div className="text-2xl font-bold text-emerald-600">{headline.subsShare.toFixed(1)}%</div>
              <div className="text-xs text-gray-500">of total active users</div>
            </div>
            <div className="bg-white p-4 rounded-xl shadow">
              <div className="text-sm text-gray-600">Data Health</div>
              <div className="text-xs text-gray-700">
                Rows loaded: {rows.length} {usingFallback ? "(fallback)" : ""}
              </div>
              {isLoading && <div className="text-xs text-gray-500 mt-1">Loading active users…</div>}
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl shadow">
            <h3 className="text-lg font-medium mb-2">Monthly Active Users</h3>
            <div className="text-xs text-gray-500 mb-3">
              Blue markers indicate actuals; gray markers indicate projected months from the source data.
            </div>
            <ResponsiveContainer width="100%" height={360}>
              <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" angle={-45} textAnchor="end" height={60} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="Total"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={(props) => (
                    <circle
                      key={props.index}
                      cx={props.cx}
                      cy={props.cy}
                      r={3.5}
                      fill={props.payload.isProjected ? "#9ca3af" : "#3b82f6"}
                    />
                  )}
                />
                <Line
                  type="monotone"
                  dataKey="Subscribers"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={(props) => (
                    <circle
                      key={props.index}
                      cx={props.cx}
                      cy={props.cy}
                      r={3}
                      fill={props.payload.isProjected ? "#9ca3af" : "#10b981"}
                    />
                  )}
                />
                <Line
                  type="monotone"
                  dataKey="OneTime"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={(props) => (
                    <circle
                      key={props.index}
                      cx={props.cx}
                      cy={props.cy}
                      r={3}
                      fill={props.payload.isProjected ? "#9ca3af" : "#f59e0b"}
                    />
                  )}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white p-6 rounded-xl shadow">
            <h3 className="text-lg font-medium mb-2">Month-over-Month Growth (actuals)</h3>
            <div className="text-xs text-gray-500 mb-3">
              Calculated across every consecutive actual month available in the dataset.
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={growthSeries} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="monthLabel" />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" />
                <Tooltip
                  formatter={(value: number, name) => {
                    if (name === "inc") {
                      return [`${value >= 0 ? "+" : ""}${Math.round(value)}`, "Absolute Growth"];
                    }
                    return [`${value >= 0 ? "+" : ""}${value.toFixed(1)}%`, "Growth %"];
                  }}
                  labelFormatter={(label: string, payload) => {
                    const entry = payload?.[0]?.payload as GrowthPoint | undefined;
                    return entry?.period ?? label;
                  }}
                />
                <Legend formatter={(value) => (value === "inc" ? "Absolute Growth" : "Growth %")} />
                <Bar yAxisId="left" dataKey="inc" fill="#3b82f6" name="inc" />
                <Bar yAxisId="right" dataKey="pct" fill="#10b981" name="pct" />
              </BarChart>
            </ResponsiveContainer>

            <div className="overflow-x-auto mt-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-left py-2 px-3">Period</th>
                    <th className="text-right py-2 px-3">Increment</th>
                    <th className="text-right py-2 px-3">Growth %</th>
                  </tr>
                </thead>
                <tbody>
                  {growthSeries.map((row) => (
                    <tr key={row.period} className="border-b hover:bg-gray-50">
                      <td className="py-2 px-3">{row.period}</td>
                      <td className="py-2 px-3 text-right text-blue-600 font-medium">
                        {row.inc >= 0 ? "+" : ""}
                        {Math.round(row.inc)}
                      </td>
                      <td className="py-2 px-3 text-right text-emerald-600 font-medium">
                        {row.pct >= 0 ? "+" : ""}
                        {row.pct.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                  {!growthSeries.length && (
                    <tr>
                      <td className="py-4 px-3 text-center text-gray-500" colSpan={3}>
                        Not enough actual data to compute growth.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white p-4 rounded-xl shadow">
              <div className="text-sm font-medium mb-2">Spend share by channel</div>
              <ResponsiveContainer width="100%" height={320}>
                <PieChart>
                  <Pie
                    data={USD_SUMMARY.filter((d) => d.spend_dollars > 0).map((d) => ({
                      name: d.channel,
                      value: d.spend_dollars,
                      cac: d.cac_dollars,
                    }))}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={70}
                    outerRadius={110}
                    paddingAngle={2}
                  >
                    {USD_SUMMARY.filter((d) => d.spend_dollars > 0).map((entry, index) => (
                      <Cell key={entry.channel} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number, _name, tooltipPayload) => {
                      const slice = tooltipPayload?.payload as SpendSlice | undefined;
                      const cac = slice && Number.isFinite(slice.cac) ? formatCurrency(slice.cac) : "—";
                      return [formatCurrency(Number(value)), `${slice?.name ?? ""} (CAC: ${cac})`];
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white p-4 rounded-xl shadow">
              <div className="text-sm font-medium mb-2">Conversion share by channel</div>
              <ResponsiveContainer width="100%" height={320}>
                <PieChart>
                  <Pie
                    data={USD_SUMMARY.filter((d) => d.new_customers > 0).map((d) => ({
                      name: d.channel,
                      value: d.new_customers,
                    }))}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={70}
                    outerRadius={110}
                    paddingAngle={2}
                  >
                    {USD_SUMMARY.filter((d) => d.new_customers > 0).map((entry, index) => (
                      <Cell key={entry.channel} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number, _name, tooltipPayload) => {
                      const slice = tooltipPayload?.payload as ConversionSlice | undefined;
                      return [`${Number(value).toLocaleString()}`, slice?.name ?? ""];
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl shadow">
            <h3 className="text-lg font-medium mb-2">Blended CAC — Month over Month</h3>
            <div className="text-xs text-gray-500 mb-3">Bars show blended CAC across all channels (USD).</div>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={cacBlended} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip formatter={(value: number) => [formatCurrency(Number(value)), "Blended CAC"]} />
                <Legend />
                <Bar dataKey="blended" fill="#3b82f6" name="Blended CAC" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white p-6 rounded-xl shadow">
            <h3 className="text-lg font-medium mb-3">Channel Summary (USD)</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-left py-2 px-3">Channel</th>
                    <th className="text-right py-2 px-3">New Customers</th>
                    <th className="text-right py-2 px-3">Spend (USD)</th>
                    <th className="text-right py-2 px-3">CAC (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {USD_SUMMARY.map((row) => (
                    <tr key={row.channel} className="border-b hover:bg-gray-50">
                      <td className="py-2 px-3">{row.channel}</td>
                      <td className="py-2 px-3 text-right">{row.new_customers.toLocaleString()}</td>
                      <td className="py-2 px-3 text-right">{formatCurrency(row.spend_dollars)}</td>
                      <td className="py-2 px-3 text-right">{formatCurrency(row.cac_dollars)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
