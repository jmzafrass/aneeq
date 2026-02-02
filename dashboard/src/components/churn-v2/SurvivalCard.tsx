"use client";

import { useMemo } from "react";
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

import type { ComputeAllResult } from "@/lib/orders/compute";
import { useFilters } from "./FiltersContext";

function formatCohort(cohort: string) {
  return cohort?.slice(0, 7) ?? cohort;
}

export function SurvivalCard({ data }: { data: ComputeAllResult }) {
  const { category } = useFilters();
  const isSubscriptionCategory = category === "pom hl" || category === "pom bg";

  const cohorts = useMemo(() => {
    if (!isSubscriptionCategory) return [];
    const source = data.survival.filter((row) => row.category.toLowerCase() === category);
    const cohortKeys = Array.from(new Set(source.map((row) => row.cohort_month))).sort();
    const monthOffsets = Array.from(new Set(source.map((row) => row.m))).sort((a, b) => a - b);

    return cohortKeys.map((cohortMonth) => {
      const row: Record<string, number | string> = { cohort: formatCohort(cohortMonth) };
      monthOffsets.forEach((offset) => {
        const match = source.find((entry) => entry.cohort_month === cohortMonth && entry.m === offset);
        const value = match ? Number(match.survival_rate ?? 0) * 100 : null;
        if (value != null) row[`M${offset}`] = value;
      });
      return row;
    });
  }, [category, data.survival, isSubscriptionCategory]);

  if (!isSubscriptionCategory || !cohorts.length) return null;

  const lines = Object.keys(cohorts[0]).filter((key) => key !== "cohort");

  return (
    <section className="rounded-xl border bg-white p-4">
      <div className="mb-2 text-sm font-semibold">Subscriber survival ({category})</div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={cohorts}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="cohort" />
          <YAxis tickFormatter={(value) => `${value.toFixed(0)}%`} />
          <Tooltip formatter={(value: number) => [`${value.toFixed(2)}%`, "Survival"]} />
          <Legend />
          {lines.map((key) => (
            <Line key={key} type="monotone" dataKey={key} name={key} dot={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-gray-500">
        Cohorts are defined by first delivery month within the subscription category. Survival is calculated using coverage
        windows.
      </p>
    </section>
  );
}
