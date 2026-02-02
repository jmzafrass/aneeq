import ExcelJS from "exceljs";

import type { CatalogueSummary, MomOrdersByVerticalRow, MomOrdersRow } from "./types";

export async function buildOrdersWorkbook(
  headline: MomOrdersRow[],
  byVertical: MomOrdersByVerticalRow[],
  catalogue?: CatalogueSummary,
): Promise<Buffer> {
  const workbook = new ExcelJS.Workbook();
  workbook.created = new Date();

  const s1 = workbook.addWorksheet("MoM Orders (Delivered)");
  s1.columns = [
    { header: "month", key: "month", width: 14 },
    { header: "orders", key: "orders", width: 12 },
    { header: "orders_mom_abs", key: "orders_mom_abs", width: 16 },
    { header: "orders_mom_pct", key: "orders_mom_pct", width: 16 },
    { header: "ado", key: "ado", width: 12 },
    { header: "ado_pacing", key: "ado_pacing", width: 14 },
    { header: "is_partial", key: "is_partial", width: 12 },
  ];
  headline.forEach((row) => s1.addRow(row));
  s1.getColumn("month").numFmt = "yyyy-mm-dd";
  s1.getColumn("orders_mom_pct").numFmt = "0.00%";
  s1.getColumn("ado").numFmt = "0.000";
  s1.getColumn("ado_pacing").numFmt = "0.000";
  s1.views = [{ state: "frozen", ySplit: 1 }];
  s1.autoFilter = "A1:G1";

  const s2 = workbook.addWorksheet("MoM by Vertical (Delivered)");
  s2.columns = [
    { header: "month", key: "month", width: 14 },
    { header: "vertical", key: "vertical", width: 12 },
    { header: "orders", key: "orders", width: 12 },
    { header: "orders_mom_abs", key: "orders_mom_abs", width: 16 },
    { header: "orders_mom_pct", key: "orders_mom_pct", width: 16 },
    { header: "ado_vertical", key: "ado_vertical", width: 16 },
    { header: "ado_vertical_pacing", key: "ado_vertical_pacing", width: 20 },
    { header: "is_partial", key: "is_partial", width: 12 },
  ];
  byVertical.forEach((row) => s2.addRow(row));
  s2.getColumn("month").numFmt = "yyyy-mm-dd";
  s2.getColumn("orders_mom_pct").numFmt = "0.00%";
  s2.getColumn("ado_vertical").numFmt = "0.000";
  s2.getColumn("ado_vertical_pacing").numFmt = "0.000";
  s2.views = [{ state: "frozen", ySplit: 1 }];
  s2.autoFilter = "A1:H1";

  if (catalogue) {
    const sheet = workbook.addWorksheet("Catalogue Summary");
    sheet.columns = [
      { header: "Category", key: "category", width: 14 },
      { header: "SKU", key: "sku", width: 20 },
      { header: "Units", key: "units", width: 10 },
      { header: "Avg price", key: "avgPrice", width: 14 },
      { header: "Revenue", key: "revenue", width: 16 },
      { header: "CoGS / unit", key: "cogsPerUnit", width: 14 },
      { header: "CoGS total", key: "cogsTotal", width: 16 },
      { header: "Take rate", key: "takeRate", width: 12 },
      { header: "Notes", key: "notes", width: 18 },
    ];

    catalogue.rows.forEach((row) => {
      sheet.addRow({
        category: row.category,
        sku: row.sku,
        units: row.units,
        avgPrice: row.avgPrice,
        revenue: row.revenue,
        cogsPerUnit: row.cogsPerUnit,
        cogsTotal: row.cogsTotal,
        takeRate: row.takeRate,
        notes: row.marginLabel,
      });
    });

    sheet.addRow({});
    sheet.addRow({
      category: "Totals",
      units: catalogue.totals.units,
      revenue: catalogue.totals.revenue,
      cogsTotal: catalogue.totals.cogs,
      takeRate: catalogue.totals.takeRate,
    });

    sheet.getColumn("avgPrice").numFmt = '"Dh" #,##0.00';
    sheet.getColumn("revenue").numFmt = '"Dh" #,##0.00';
    sheet.getColumn("cogsPerUnit").numFmt = '"Dh" #,##0.00';
    sheet.getColumn("cogsTotal").numFmt = '"Dh" #,##0.00';
    sheet.getColumn("takeRate").numFmt = "0.00%";
    sheet.getColumn("units").numFmt = "0";
    sheet.views = [{ state: "frozen", ySplit: 1 }];
    sheet.autoFilter = "A1:I1";
  }

  const buffer = await workbook.xlsx.writeBuffer();
  return Buffer.from(buffer);
}
