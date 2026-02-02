import { describe, expect, it } from "vitest";

import {
  addMonths,
  monthKeyFromDate,
  monthsDiff,
  normalizeMeasure,
  parseCohortMonthKey,
  parseRetention,
} from "./utils";

describe("parseRetention", () => {
  it("parses numeric strings and percentages", () => {
    expect(parseRetention("0.75")).toBeCloseTo(0.75);
    expect(parseRetention("75%"))
      .toBeCloseTo(0.75);
    expect(parseRetention(0.25)).toBeCloseTo(0.25);
  });

  it("defaults invalid values to zero", () => {
    expect(parseRetention("abc")).toBe(0);
    expect(parseRetention(undefined)).toBe(0);
  });
});

describe("parseCohortMonthKey", () => {
  it("normalizes cohort strings to YYYY-MM", () => {
    const { key, date } = parseCohortMonthKey("2024-02-01 00:00:00");
    expect(key).toBe("2024-02");
    expect(date.getFullYear()).toBe(2024);
    expect(date.getMonth()).toBe(1);
  });
});

describe("monthsDiff", () => {
  it("returns number of months between cohort and last observed", () => {
    expect(monthsDiff("2024-01", "2024-02")).toBe(1);
    expect(monthsDiff("2023-12", "2024-02")).toBe(2);
  });

  it("guards against invalid input", () => {
    expect(monthsDiff("", "2024-01")).toBe(0);
    expect(monthsDiff("2024-01", "")).toBe(0);
  });
});

describe("normalizeMeasure", () => {
  it("maps variants to supported measures", () => {
    expect(normalizeMeasure("GM")).toBe("gm");
    expect(normalizeMeasure("gross margin")).toBe("gm");
    expect(normalizeMeasure("Revenue")).toBe("revenue");
  });
});

describe("date helpers", () => {
  it("adds months and formats keys", () => {
    const start = new Date(2024, 0, 1);
    expect(monthKeyFromDate(addMonths(start, 1))).toBe("2024-02");
  });
});
