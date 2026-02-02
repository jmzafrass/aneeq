import { promises as fs } from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import { computeCatalogueSummary } from "@/lib/orders/catalogue";
import { processOrdersCSV } from "@/lib/orders/processOrders";
import { computeAllFromBuffer } from "@/lib/orders/compute";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const source = searchParams.get("source");

    let buffer: Buffer | null = null;

    if (source !== "default") {
      const formData = await request.formData();
      const file = formData.get("file");
      if (!file || !(file instanceof File)) {
        return NextResponse.json({ error: "file_required" }, { status: 400 });
      }

      buffer = Buffer.from(await file.arrayBuffer());
    }

    if (!buffer) {
      const filePath = path.join(process.cwd(), "public", "data", "allorders.csv");
      buffer = await fs.readFile(filePath);
    }

    const result = processOrdersCSV(buffer);
    const catalogue = computeCatalogueSummary(result.processedOrders);
    const analytics = computeAllFromBuffer(buffer);

    return NextResponse.json({
      momOrders: result.momOrders,
      momOrdersByVertical: result.momOrdersByVertical,
      qa: result.qa,
      catalogue,
      churn: analytics.churn,
      retention: analytics.retention,
      ltv: analytics.ltv,
      survival: analytics.survival,
      waterfall: analytics.waterfall,
      asOfMonth: analytics.asOfMonth,
    });
  } catch (error: unknown) {
    console.error("orders/compute", error);
    return NextResponse.json({ error: "processing_failed" }, { status: 500 });
  }
}
