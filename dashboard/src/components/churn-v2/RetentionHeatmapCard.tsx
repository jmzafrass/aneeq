"use client";

import { useMemo } from "react";

import type { ComputeAllResult } from "@/lib/orders/compute";
import { useFilters } from "./FiltersContext";

function formatMonth(month: string) {
  return month?.slice(0, 7) ?? month;
}

function toPercent(value: string | number): number {
  if (typeof value === "number") return value;
  const trimmed = value.trim();
  if (trimmed.endsWith("%")) {
    const numeric = Number(trimmed.slice(0, -1));
    return Number.isFinite(numeric) ? numeric / 100 : 0;
  }
  const numeric = Number(trimmed);
  return Number.isFinite(numeric) ? numeric : 0;
}

interface HeatmapRow {
  cohort: string;
  size: number;
  values: Map<number, number | undefined>;
}

export function RetentionHeatmapCard({ data }: { data: ComputeAllResult }) {
  const { category, metric } = useFilters();

  const filteredRows = useMemo(() => {
    if (category === "all") {
      return data.retention.filter(
        (row) => row.dimension === "overall" && row.first_value === "ALL" && row.metric === "any",
      );
    }
    return data.retention.filter(
      (row) => row.dimension === "category" && row.first_value.toLowerCase() === category && row.metric === metric,
    );
  }, [category, data.retention, metric]);

  const rows: HeatmapRow[] = useMemo(() => {
    const map = new Map<string, HeatmapRow>();
    filteredRows.forEach((row) => {
      const key = row.cohort_month;
      if (!map.has(key)) {
        map.set(key, { cohort: formatMonth(key), size: row.cohort_size, values: new Map() });
      }
      map.get(key)!.values.set(row.m, toPercent(row.retention));
    });
    return Array.from(map.values()).sort((a, b) => a.cohort.localeCompare(b.cohort));
  }, [filteredRows]);

  const maxMonth = filteredRows.length ? Math.max(...filteredRows.map((row) => row.m ?? 0)) : 0;

  const getCellClass = (value: number | undefined) => {
    if (value === undefined) return "bg-gray-50 text-gray-400";
    if (value >= 0.9) return "bg-sky-600 text-white";
    if (value >= 0.75) return "bg-sky-500 text-white";
    if (value >= 0.6) return "bg-sky-400 text-white";
    if (value >= 0.45) return "bg-sky-300";
    if (value >= 0.3) return "bg-sky-200";
    if (value >= 0.15) return "bg-sky-100";
    return "bg-sky-50";
  };

  if (!rows.length) return null;

  return (
    <section className="rounded-xl border bg-white p-4">
      <div className="mb-2 text-sm font-semibold">
        Retention heatmap {category === "all" ? "(overall · any)" : `(${category} · ${metric})`}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="px-3 py-2 text-left">Cohort</th>
              <th className="px-3 py-2 text-center">Size</th>
              {Array.from({ length: maxMonth + 1 }, (_, index) => (
                <th key={index} className="px-2 py-2 text-center">
                  M{index}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.cohort} className="border-b">
                <td className="px-3 py-1 font-medium">{row.cohort}</td>
                <td className="px-3 py-1 text-center">n={row.size}</td>
                {Array.from({ length: maxMonth + 1 }, (_, index) => {
                  const value = row.values.get(index);
                  return (
                    <td key={index} className="px-2 py-1 text-center">
                      {value !== undefined ? (
                        <span className={`inline-block rounded px-2 py-1 text-xs font-medium ${getCellClass(value)}`}>
                          {(value * 100).toFixed(2)}%
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-gray-500">
        Right-censored at the last full month. “Any” counts any product repurchase; “Same” measures stickiness within the first
        category.
      </p>
    </section>
  );
}
