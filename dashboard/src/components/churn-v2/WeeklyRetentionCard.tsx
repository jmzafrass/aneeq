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

type SegmentOption = Segment | "all";

const SEGMENTS: Segment[] = ["subscribers", "onetime", "total"];
type WeeklyRow = ComputeAllResult["churn"]["weeklyRetention"][number];

function formatPercent(value: number) {
  return `${value.toFixed(2)}%`;
}

export function WeeklyRetentionCard({ data }: { data: ComputeAllResult }) {
  const [segment, setSegment] = useState<SegmentOption>("all");
  const [showRaw, setShowRaw] = useState(false);

  const chartData = useMemo(() => {
    const keep: Segment[] = segment === "all" ? SEGMENTS : [segment];

    const bySegment = new Map<Segment, WeeklyRow[]>();
    SEGMENTS.forEach((label) => {
      const series = data.churn.weeklyRetention
        .filter((row) => row.label === label)
        .sort((a, b) => a.week.localeCompare(b.week));
      bySegment.set(label, series);
    });

    const weightedSMA = (series: WeeklyRow[]) => {
      const window: Array<{ rate: number; weight: number }> = [];
      let sumWeights = 0;
      let sumWeightedRates = 0;
      const output = new Map<string, number | undefined>();

      series.forEach((row) => {
        const weight = row.prevActive;
        const rate = row.retentionRate;
        window.push({ rate, weight });
        sumWeights += weight;
        sumWeightedRates += rate * weight;

        if (window.length > 4) {
          const removed = window.shift()!;
          sumWeights -= removed.weight;
          sumWeightedRates -= removed.rate * removed.weight;
        }

        const value = sumWeights > 0 ? (sumWeightedRates / sumWeights) * 100 : undefined;
        output.set(row.week, value);
      });

      return output;
    };

    const smoothed = new Map<Segment, Map<string, number | undefined>>();
    SEGMENTS.forEach((label) => {
      const series = bySegment.get(label) ?? [];
      smoothed.set(label, weightedSMA(series));
    });

    const weeks = Array.from(new Set(data.churn.weeklyRetention.map((row) => row.week))).sort();
    return weeks.map((week) => {
      const row: Record<string, number | string | undefined> = { week };
      SEGMENTS.forEach((label) => {
        if (!keep.includes(label)) return;
        const series = bySegment.get(label) ?? [];
        const match = series.find((entry) => entry.week === week);
        if (showRaw) {
          row[`${label}_raw`] = match ? match.retentionRate * 100 : undefined;
        } else {
          row[`${label}_smooth`] = smoothed.get(label)?.get(week);
        }
      });
      return row;
    });
  }, [data.churn.weeklyRetention, segment, showRaw]);

  if (!chartData.length) return null;

  return (
    <section className="rounded-xl border bg-white p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm font-semibold">
        <span>Weekly retention {showRaw ? "(raw)" : "(4-week weighted average)"}</span>
        <div className="ml-auto flex flex-wrap gap-2 text-xs">
          {(["all", ...SEGMENTS] as SegmentOption[]).map((option) => {
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
          <button
            type="button"
            onClick={() => setShowRaw((value) => !value)}
            className="rounded-full border border-gray-300 bg-gray-100 px-2 py-1 text-gray-700"
          >
            {showRaw ? "Show 4-week avg" : "Show raw"}
          </button>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week" minTickGap={20} />
          <YAxis domain={[0, 100]} tickFormatter={(value) => `${value.toFixed(0)}%`} />
          <Tooltip formatter={(value: number) => [formatPercent(value), "Retention"]} />
          <Legend />
          {(segment === "all" || segment === "subscribers") && (
            <Line
              type="monotone"
              dataKey={showRaw ? "subscribers_raw" : "subscribers_smooth"}
              name="Subscribers"
              stroke="#1d4ed8"
              dot={false}
              connectNulls
            />
          )}
          {(segment === "all" || segment === "onetime") && (
            <Line
              type="monotone"
              dataKey={showRaw ? "onetime_raw" : "onetime_smooth"}
              name="One-time"
              stroke="#f97316"
              dot={false}
              connectNulls
            />
          )}
          {(segment === "all" || segment === "total") && (
            <Line
              type="monotone"
              dataKey={showRaw ? "total_raw" : "total_smooth"}
              name="Total"
              stroke="#16a34a"
              dot={false}
              connectNulls
            />
          )}
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-gray-500">
        Active in week = active on any day (Mon-Sun). Retention compares consecutive weeks.
        Weighted average uses the previous week&apos;s active base to reduce noise from thin weeks.
      </p>
    </section>
  );
}
