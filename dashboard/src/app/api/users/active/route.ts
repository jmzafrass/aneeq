import { promises as fs } from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import type { ActiveUsersRow } from "@/lib/analytics/types";
import { buildActiveFallback } from "@/lib/analytics/constants";
import { processOrdersCSV } from "@/lib/orders/processOrders";

async function loadDefaultOrders() {
  const filePath = path.join(process.cwd(), "public", "data", "allorders.csv");
  return fs.readFile(filePath);
}

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const source = searchParams.get("source");

    let buffer: Buffer;

    if (source === "default") {
      buffer = await loadDefaultOrders();
    } else {
      const formData = await request.formData();
      const file = formData.get("file");
      if (!file || !(file instanceof File)) {
        return NextResponse.json({ error: "file_required" }, { status: 400 });
      }

      buffer = Buffer.from(await file.arrayBuffer());
    }

    const result = processOrdersCSV(buffer);
    const rows: ActiveUsersRow[] = result.churn.monthlyActive.map((entry) => ({
      month: entry.month,
      active_subscribers: entry.subscribers,
      active_onetime: entry.onetime,
      active_total: entry.total,
      is_future_vs_today: 0,
    }));

    const body = rows.length ? { rows } : { rows: buildActiveFallback() };

    return NextResponse.json(body);
  } catch (error: unknown) {
    console.error("users/active", error);
    return NextResponse.json({ rows: buildActiveFallback(), error: "processing_failed" }, { status: 500 });
  }
}
