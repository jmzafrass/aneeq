'use client';

import { classNames, formatUsd } from "@/lib/analytics/utils";

import type { HeatmapRow } from "./RetentionHeatmap";

interface LtvHeatmapProps {
  rows: HeatmapRow[];
  maxMonth: number;
  maxValue: number;
  cellColor: (value: number | undefined, max: number) => string;
}

export function LtvHeatmap({ rows, maxMonth, maxValue, cellColor }: LtvHeatmapProps) {
  return (
    <div className="bg-white rounded-xl shadow overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50">
            <th className="px-4 py-2 text-left">Cohort</th>
            <th className="px-2 py-2 text-center">Size</th>
            {Array.from({ length: maxMonth + 1 }, (_, index) => (
              <th key={index} className="px-3 py-2 text-center">
                M{index}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.cohortMonth} className="border-b hover:bg-gray-50">
              <td className="px-4 py-2 font-medium">{row.cohortMonth}</td>
              <td className="px-2 py-2 text-center">
                <span className="inline-block px-2 py-0.5 bg-gray-100 rounded text-xs">n={row.cohortSize}</span>
              </td>
              {Array.from({ length: maxMonth + 1 }, (_, month) => {
                const value = row.values[month];
                return (
                  <td key={month} className="px-3 py-2 text-center">
                    {value !== undefined ? (
                      <span
                        className={classNames(
                          "inline-block px-2 py-1 rounded text-xs font-medium",
                          cellColor(value, maxValue),
                        )}
                        title={`M${month}: ${formatUsd(value)} (n=${row.cohortSize})`}
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
          ))}
          {!rows.length && (
            <tr>
              <td className="px-4 py-8 text-center text-gray-500" colSpan={maxMonth + 3}>
                No data loaded or filters exclude all rows.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
