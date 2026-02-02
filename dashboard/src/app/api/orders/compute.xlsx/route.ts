import { promises as fs } from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import { buildOrdersWorkbook } from "@/lib/orders/excel";
import { computeCatalogueSummary } from "@/lib/orders/catalogue";
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
        return new NextResponse("file_required", { status: 400 });
      }

      buffer = Buffer.from(await file.arrayBuffer());
    }

    const result = processOrdersCSV(buffer);
    const catalogue = computeCatalogueSummary(result.processedOrders);
    const workbook = await buildOrdersWorkbook(result.momOrders, result.momOrdersByVertical, catalogue);
    const bytes = Uint8Array.from(workbook);

    return new NextResponse(bytes, {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": "attachment; filename=\"mom_orders_outputs.xlsx\"",
      },
    });
  } catch (error: unknown) {
    console.error("orders/compute.xlsx", error);
    return new NextResponse("processing_failed", { status: 500 });
  }
}
