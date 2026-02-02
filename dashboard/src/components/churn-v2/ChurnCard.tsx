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

export function ChurnCard({ data }: { data: ComputeAllResult }) {
  const { category, segment } = useFilters();

  const rows = useMemo(() => {
    if (category === "all") {
      const targetLabel = segment === "total" ? "total" : segment;
      return data.churn.overview
        .filter((row) => row.label === targetLabel)
        .map((row) => ({
          month: formatMonth(row.month),
          churned: row.churned,
          rate: row.churnRate * 100,
        }))
        .sort((a, b) => a.month.localeCompare(b.month));
    }

    return data.churn.byCategory
      .filter((row) => row.category.toLowerCase() === category)
      .map((row) => ({
        month: formatMonth(row.month),
        churned: row.churned,
        rate: row.churnRate * 100,
      }))
      .sort((a, b) => a.month.localeCompare(b.month));
  }, [category, data.churn.byCategory, data.churn.overview, segment]);

  if (!rows.length) return null;

  return (
    <section className="rounded-xl border bg-white p-4">
      <div className="mb-2 text-sm font-semibold">
        Monthly churn {category === "all" ? "(overall)" : `(${category})`} · {segment}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis yAxisId="counts" />
          <YAxis yAxisId="percent" orientation="right" tickFormatter={(value) => `${value.toFixed(0)}%`} />
          <Tooltip
            formatter={(value: number, name: string) =>
              name === "Churn rate" ? [`${value.toFixed(2)}%`, name] : [value, name]
            }
          />
          <Legend />
          <Bar yAxisId="counts" dataKey="churned" name="Churned" fill="#f97316" />
          <Line yAxisId="percent" type="monotone" dataKey="rate" name="Churn rate" stroke="#1d4ed8" dot />
        </ComposedChart>
      </ResponsiveContainer>
    </section>
  );
}
