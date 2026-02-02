"use client";

import { useFilters } from "./FiltersContext";

export function FiltersBar({ categories }: { categories: string[] }) {
  const { category, setCategory, segment, setSegment, metric, setMetric, categoryMode, setCategoryMode } = useFilters();

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-white p-3 text-sm">
      <label className="flex items-center gap-2">
        <span className="text-xs uppercase tracking-wide text-gray-500">Category</span>
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value as typeof category)}
          className="rounded-md border px-2 py-1 text-sm"
        >
          <option value="all">ALL</option>
          {categories.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2">
        <span className="text-xs uppercase tracking-wide text-gray-500">Segment</span>
        <select
          value={segment}
          onChange={(event) => setSegment(event.target.value as typeof segment)}
          className="rounded-md border px-2 py-1 text-sm"
        >
          <option value="total">Total</option>
          <option value="subscribers">Subscribers</option>
          <option value="onetime">One-time</option>
        </select>
      </label>

      <div className="ml-auto flex flex-wrap items-center gap-3 text-xs">
        <label className="flex items-center gap-2">
          <span className="uppercase tracking-wide text-gray-500">Metric</span>
          <select
            value={metric}
            onChange={(event) => setMetric(event.target.value as typeof metric)}
            className="rounded-md border px-2 py-1 text-sm"
          >
            <option value="any">Any</option>
            <option value="same">Same</option>
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="uppercase tracking-wide text-gray-500">Mode</span>
          <select
            value={categoryMode}
            onChange={(event) => setCategoryMode(event.target.value as typeof categoryMode)}
            className="rounded-md border px-2 py-1 text-sm"
          >
            <option value="first">First purchase</option>
            <option value="ever">Ever purchased</option>
          </select>
        </label>
      </div>
    </div>
  );
}
