export const SKU_CATEGORY_MAP: Record<string, string> = {
  // POM HL — branded kits
  "ultimate revival": "POM HL",
  "power regrowth": "POM HL",
  "essential boost": "POM HL",
  "oral mix": "POM HL",
  "oral minoxidil": "POM HL",
  // POM HL — Mamo / detailed product names
  "oral finasteride + minoxidil": "POM HL",
  "oral finasteride 1mg + minoxidil 2.5mg": "POM HL",
  "oral dutasteride + minoxidil": "POM HL",
  "topical minoxidil + finasteride foam": "POM HL",
  "rx hair loss serum": "POM HL",
  // POM SH
  "vital recharge": "POM SH",
  "max power": "POM SH",
  "oral sildenafil": "POM SH",
  "oral tadalafil": "POM SH",
  "sildenafil 50mg + dapoxetine": "POM SH",
  // POM BG
  "beard growth serum": "POM BG",
  // OTC SH
  "delay spray": "OTC SH",
  // OTC SK
  "essential routine": "OTC SK",
  "advanced routine": "OTC SK",
  "essential skin care routine for men": "OTC SK",
  "advanced skin care routine": "OTC SK",
  cleanser: "OTC SK",
  "face cleanser": "OTC SK",
  "moisturizer spf": "OTC SK",
  "moisturizer spf 50": "OTC SK",
  "moisturizer with spf 50": "OTC SK",
  moisturizer: "OTC SK",
  "eye cream": "OTC SK",
  serum: "OTC SK",
  "vitamin c serum": "OTC SK",
  // OTC HL
  shampoo: "OTC HL",
  "restore shampoo": "OTC HL",
  conditioner: "OTC HL",
  "revive hair conditioner": "OTC HL",
  "revive сonditioner": "OTC HL", // Cyrillic 'с' variant from Airtable
  "regrowth hair pack": "OTC HL",
  "regrowth pack": "OTC HL",
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
