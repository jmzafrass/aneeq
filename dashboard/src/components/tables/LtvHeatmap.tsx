'use client';

import { classNames, formatUsd, aedToUsd, calculateCacUsd, findBreakEvenMonth } from "@/lib/analytics/utils";

import type { HeatmapRow } from "./RetentionHeatmap";

interface LtvHeatmapProps {
  rows: HeatmapRow[];
  maxMonth: number;
  maxValue: number;
  cellColor: (value: number | undefined, max: number) => string;
  marketingSpend?: Record<string, number>;
}

export function LtvHeatmap({ rows, maxMonth, maxValue, cellColor, marketingSpend }: LtvHeatmapProps) {
  const showCac = marketingSpend && Object.keys(marketingSpend).length > 0;

  return (
    <div className="bg-white rounded-xl shadow overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50">
            <th className="px-4 py-2 text-left">Cohort</th>
            <th className="px-2 py-2 text-center">Size</th>
            {showCac && (
              <>
                <th className="px-2 py-2 text-center" title="Customer Acquisition Cost = Marketing Spend / New Customers">
                  CAC
                </th>
                <th className="px-2 py-2 text-center" title="Month when cumulative LTV exceeds CAC">
                  Break-even
                </th>
              </>
            )}
            {Array.from({ length: maxMonth + 1 }, (_, index) => (
              <th key={index} className="px-3 py-2 text-center">
                M{index}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const spendAed = marketingSpend?.[row.cohortMonth];
            const cacUsd = calculateCacUsd(spendAed, row.cohortSize);
            const breakEvenMonth = findBreakEvenMonth(row.values, cacUsd, maxMonth);

            return (
              <tr key={row.cohortMonth} className="border-b hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">{row.cohortMonth}</td>
                <td className="px-2 py-2 text-center">
                  <span className="inline-block px-2 py-0.5 bg-gray-100 rounded text-xs">n={row.cohortSize}</span>
                </td>
                {showCac && (
                  <>
                    <td className="px-2 py-2 text-center">
                      {cacUsd !== undefined ? (
                        <span
                          className="inline-block px-2 py-0.5 bg-amber-100 text-amber-800 rounded text-xs font-medium"
                          title={`Spend: ${spendAed?.toLocaleString()} AED / ${row.cohortSize} customers`}
                        >
                          ${cacUsd.toFixed(0)}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-2 py-2 text-center">
                      {breakEvenMonth !== undefined ? (
                        <span
                          className="inline-block px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs font-medium"
                          title={`LTV exceeds CAC at month ${breakEvenMonth}`}
                        >
                          M{breakEvenMonth}
                        </span>
                      ) : cacUsd !== undefined ? (
                        <span className="text-gray-400" title="LTV has not yet exceeded CAC">
                          —
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                  </>
                )}
                {Array.from({ length: maxMonth + 1 }, (_, month) => {
                  const value = row.values[month];
                  const ltvUsd = value !== undefined ? aedToUsd(value) : undefined;
                  const isBreakEven = cacUsd !== undefined && ltvUsd !== undefined && ltvUsd >= cacUsd;

                  return (
                    <td key={month} className="px-3 py-2 text-center">
                      {value !== undefined ? (
                        <span
                          className={classNames(
                            "inline-block px-2 py-1 rounded text-xs font-medium",
                            isBreakEven ? "ring-2 ring-green-500 ring-offset-1" : "",
                            cellColor(value, maxValue),
                          )}
                          title={`M${month}: ${formatUsd(value)} (n=${row.cohortSize})${isBreakEven ? " ✓ Break-even" : ""}`}
                        >
                          {formatUsd(value)}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
          {!rows.length && (
            <tr>
              <td className="px-4 py-8 text-center text-gray-500" colSpan={maxMonth + 3 + (showCac ? 2 : 0)}>
                No data loaded or filters exclude all rows.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
