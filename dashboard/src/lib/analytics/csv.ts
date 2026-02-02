import Papa from "papaparse";

export function parseCsv<T>(text: string) {
  return new Promise<T[]>((resolve, reject) => {
    Papa.parse<T>(text, {
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (result) => {
        const rows = (result.data || []).filter(Boolean) as T[];
        resolve(rows);
      },
      error: (err: unknown) => reject(err),
    });
  });
}
