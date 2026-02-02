"use client";

import { useMemo } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ComputeAllResult } from "@/lib/orders/compute";
import { useFilters } from "./FiltersContext";

function formatMonth(month: string) {
  return month?.slice(0, 7) ?? month;
}

export function WaterfallCard({ data }: { data: ComputeAllResult }) {
  const { category } = useFilters();

  const rows = useMemo(() => {
    const target = category === "all" ? "all" : category;
    return data.waterfall
      .filter((row) => row.category.toLowerCase() === target)
      .sort((a, b) => a.month.localeCompare(b.month));
  }, [data.waterfall, category]);

  if (!rows.length) return null;

  const chartData = rows.map((row) => ({
    month: formatMonth(row.month),
    start_active: row.start_active,
    new_active: row.new_active,
    reactivated: row.reactivated,
    churned: row.churned * -1,
    end_active: row.end_active,
  }));

  return (
    <section className="rounded-xl border bg-white p-4">
      <div className="mb-2 text-sm font-semibold">
        Active base waterfall {category === "all" ? "(all categories)" : `(${category})`}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="new_active" name="New active" stackId="delta" fill="#22c55e" />
          <Bar dataKey="reactivated" name="Reactivated" stackId="delta" fill="#0ea5e9" />
          <Bar dataKey="churned" name="Churned" stackId="delta" fill="#ef4444" />
          <Line dataKey="end_active" name="End of month" stroke="#1d4ed8" dot />
        </ComposedChart>
      </ResponsiveContainer>
    </section>
  );
}
