export const SKU_CATEGORY_MAP: Record<string, string> = {
  "ultimate revival": "POM HL",
  "power regrowth": "POM HL",
  "essential boost": "POM HL",
  "oral mix": "POM HL",
  "oral minoxidil": "POM HL",
  "vital recharge": "POM SH",
  "max power": "POM SH",
  "delay spray": "OTC SH",
  "essential routine": "OTC SK",
  "advanced routine": "OTC SK",
  cleanser: "OTC SK",
  "moisturizer spf": "OTC SK",
  moisturizer: "OTC SK",
  "eye cream": "OTC SK",
  serum: "OTC SK",
  shampoo: "OTC HL",
  conditioner: "OTC HL",
  "regrowth hair pack": "OTC HL",
  "regrowth pack": "OTC HL",
  "beard growth serum": "POM BG",
};

export const SUBSCRIPTION_CATEGORIES = new Set(["POM HL", "POM BG"]);

export const MAGENTA_START_KEY = "2025-07-01";

// Dynamic: last day of the most recently completed calendar month
function computeChurnCutoff(): string {
  const today = new Date();
  const endOfLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
  const y = endOfLastMonth.getFullYear();
  const m = String(endOfLastMonth.getMonth() + 1).padStart(2, "0");
  const d = String(endOfLastMonth.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export const CHURN_CUTOFF_KEY = computeChurnCutoff();
