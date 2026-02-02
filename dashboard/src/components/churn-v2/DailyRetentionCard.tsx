"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ComputeAllResult, Segment } from "@/lib/orders/compute";

type FilterSegment = Segment | "all";

export function DailyRetentionCard({ data }: { data: ComputeAllResult }) {
  const [segment, setSegment] = useState<FilterSegment>("all");

  const chartRows = useMemo(() => {
    const labels: Segment[] = ["subscribers", "onetime", "total"];
    const activeLabels = segment === "all" ? labels : ([segment] as Segment[]);

    const sorted = [...data.churn.dailyRetention].sort((a, b) => a.date.localeCompare(b.date));
    const byLabel = new Map<Segment, typeof sorted>();
    labels.forEach((label) => {
      byLabel.set(label, sorted.filter((row) => row.label === label));
    });

    const rollingMaps = new Map<Segment, Map<string, number>>();
    activeLabels.forEach((label) => {
      const entries = byLabel.get(label) ?? [];
      const window: number[] = [];
      let sum = 0;
      const map = new Map<string, number>();
      entries.forEach((row) => {
        const value = row.retentionRate ?? 0;
        window.push(value);
        sum += value;
        if (window.length > 7) {
          sum -= window.shift() ?? 0;
        }
        const average = window.length ? sum / window.length : 0;
        map.set(row.date, average * 100);
      });
      rollingMaps.set(label, map);
    });

    const map = new Map<string, Record<string, number | string>>();
    sorted.forEach((row) => {
      if (!activeLabels.includes(row.label)) return;
      const bucket = map.get(row.date) ?? { date: row.date };
      bucket[`${row.label}_7d`] = rollingMaps.get(row.label)?.get(row.date) ?? 0;
      map.set(row.date, bucket);
    });

    return Array.from(map.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [data.churn.dailyRetention, segment]);

  if (!chartRows.length) return null;

  return (
    <section className="rounded-xl border bg-white p-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <span>Daily retention (7-day rolling)</span>
        <div className="ml-auto flex gap-2 text-xs">
          {(["all", "subscribers", "onetime", "total"] as FilterSegment[]).map((option) => {
            const active = segment === option;
            return (
              <button
                key={option}
                type="button"
                onClick={() => setSegment(option)}
                className={`rounded-full border px-2 py-1 ${
                  active ? "border-blue-600 bg-blue-600 text-white" : "border-gray-300 bg-gray-100 text-gray-700"
                }`}
              >
                {option}
              </button>
            );
          })}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={chartRows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" minTickGap={20} />
          <YAxis tickFormatter={(value) => `${value.toFixed(0)}%`} />
          <Tooltip formatter={(value: number) => [`${value.toFixed(2)}%`, "Retention (7d)"]} />
          <Legend />
          {(segment === "all" || segment === "subscribers") && (
            <Line type="monotone" dataKey="subscribers_7d" name="Subscribers (7d)" stroke="#1d4ed8" dot={false} />
          )}
          {(segment === "all" || segment === "onetime") && (
            <Line type="monotone" dataKey="onetime_7d" name="One-time (7d)" stroke="#f97316" dot={false} />
          )}
          {(segment === "all" || segment === "total") && (
            <Line type="monotone" dataKey="total_7d" name="Total (7d)" stroke="#16a34a" dot={false} />
          )}
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-gray-500">
        Derived from coverage windows; reflects the share of active customers retained day-over-day. The 7-day average smooths
        out cadence-driven steps.
      </p>
    </section>
  );
}
