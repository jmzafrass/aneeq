'use client';

import { useEffect, useMemo, useState } from "react";

import type { CatalogueSummary } from "@/lib/orders/types";

interface CatalogueResponse {
  catalogue: CatalogueSummary;
}

export function CatalogueDashboard() {
  const [data, setData] = useState<CatalogueSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchCatalogue() {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch("/api/orders/compute?source=default", { method: "POST" });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Request failed");
      }
      const payload = (await response.json()) as CatalogueResponse;
      setData(payload.catalogue);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchCatalogue();
  }, []);

  type CatalogueRowTable = Record<string, string | number>;

  const formattedRows = useMemo(() => {
    if (!data) return [] as CatalogueRowTable[];
    const formatCurrency = (value: number) => `Dh ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    const formatPct = (value: number) => `${(value * 100).toFixed(2)}%`;

    const rows: CatalogueRowTable[] = data.rows.map((row) => ({
      Category: row.category,
      SKU: row.sku,
      Units: row.units,
      "Avg price": formatCurrency(row.avgPrice),
      Revenue: formatCurrency(row.revenue),
      "CoGS / unit": formatCurrency(row.cogsPerUnit),
      "CoGS total": formatCurrency(row.cogsTotal),
      "Take rate": formatPct(row.takeRate),
      Notes: row.marginLabel,
    }));

    rows.push({
      Category: "Totals",
      Units: data.totals.units,
      Revenue: formatCurrency(data.totals.revenue),
      "CoGS total": formatCurrency(data.totals.cogs),
      "Take rate": formatPct(data.totals.takeRate),
    } as CatalogueRowTable);

    return rows;
  }, [data]);

  return (
    <div className="space-y-5">
      <section className="flex flex-wrap items-center gap-3">
        <button
          className="px-4 py-2 rounded-md bg-blue-600 text-white disabled:opacity-60"
          onClick={() => fetchCatalogue()}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh catalogue"}
        </button>
        {error && <span className="text-sm text-red-600">{error}</span>}
        <span className="text-xs text-gray-500">
          Delivered orders only • Magenta COGS applied from July 2025 onward.
        </span>
      </section>

      {data && (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="mb-4">
            <div className="text-sm font-semibold text-slate-900">Totals</div>
            <div className="text-xs text-gray-600">
              Units: {data.totals.units.toLocaleString()} · Revenue: Dh {data.totals.revenue.toLocaleString(undefined, { maximumFractionDigits: 2 })} ·
              CoGS: Dh {data.totals.cogs.toLocaleString(undefined, { maximumFractionDigits: 2 })} · Take rate: {(data.totals.takeRate * 100).toFixed(2)}%
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead>
                <tr>
                  {formattedRows.length > 0 &&
                    Object.keys(formattedRows[0]).map((column) => (
                      <th
                        key={column}
                        className="whitespace-nowrap bg-gray-50 px-3 py-2 text-left font-medium text-gray-600"
                      >
                        {column}
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {formattedRows.map((row, index) => (
                  <tr key={`${row["SKU"] ?? row["Category"] ?? index}-${index}`} className="hover:bg-gray-50">
                    {Object.entries(row).map(([column, value]) => (
                      <td key={`${column}-${index}`} className="whitespace-nowrap px-3 py-2 text-gray-700">
                        {value}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
