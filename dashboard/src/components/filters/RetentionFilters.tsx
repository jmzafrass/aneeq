'use client';

import type { Dimension, Metric } from "@/lib/analytics/types";

interface RetentionFiltersProps {
  dimension: Dimension;
  metric: Metric;
  firstValue: string;
  startMonth: string;
  endMonth: string;
  months: string[];
  categories: string[];
  skus: string[];
  onDimensionChange: (value: Dimension) => void;
  onMetricChange: (value: Metric) => void;
  onFirstValueChange: (value: string) => void;
  onStartMonthChange: (value: string) => void;
  onEndMonthChange: (value: string) => void;
}

export function RetentionFilters(props: RetentionFiltersProps) {
  const {
    dimension,
    metric,
    firstValue,
    startMonth,
    endMonth,
    months,
    categories,
    skus,
    onDimensionChange,
    onMetricChange,
    onFirstValueChange,
    onStartMonthChange,
    onEndMonthChange,
  } = props;

  const options = dimension === "category" ? categories : skus;

  return (
    <div className="bg-white p-4 rounded-xl shadow grid md:grid-cols-5 gap-3">
      <div>
        <label className="block text-sm mb-1">Dimension</label>
        <select
          value={dimension}
          onChange={(event) => onDimensionChange(event.target.value as Dimension)}
          className="w-full px-3 py-1.5 border rounded-md text-sm"
        >
          <option value="overall">Overall</option>
          <option value="category">Category</option>
          <option value="sku">SKU</option>
        </select>
      </div>

      <div>
        <label className="block text-sm mb-1">
          {dimension === "overall" ? "Value" : dimension === "category" ? "Category" : "SKU"}
        </label>
        {dimension === "overall" ? (
          <input
            disabled
            value="ALL"
            className="w-full px-3 py-1.5 border rounded-md bg-gray-100 text-sm"
          />
        ) : (
          <select
            value={firstValue}
            onChange={(event) => onFirstValueChange(event.target.value)}
            className="w-full px-3 py-1.5 border rounded-md text-sm"
          >
            {options.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        )}
      </div>

      <div>
        <label className="block text-sm mb-1">Metric</label>
        <select
          value={metric}
          onChange={(event) => onMetricChange(event.target.value as Metric)}
          disabled={dimension === "overall"}
          className="w-full px-3 py-1.5 border rounded-md text-sm disabled:bg-gray-100"
        >
          <option value="any">Any (bought anything)</option>
          <option value="same">Same (stickiness)</option>
        </select>
      </div>

      <div>
        <label className="block text-sm mb-1">Start Month</label>
        <select
          value={startMonth}
          onChange={(event) => onStartMonthChange(event.target.value)}
          className="w-full px-3 py-1.5 border rounded-md text-sm"
        >
          {months.map((month) => (
            <option key={month} value={month}>
              {month}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm mb-1">End Month</label>
        <select
          value={endMonth}
          onChange={(event) => onEndMonthChange(event.target.value)}
          className="w-full px-3 py-1.5 border rounded-md text-sm"
        >
          {months.map((month) => (
            <option key={month} value={month}>
              {month}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
