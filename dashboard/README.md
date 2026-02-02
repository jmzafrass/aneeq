## Customer Analytics Dashboard

Interactive cohort dashboard for Aneeq investors built with Next.js 15, TypeScript, Tailwind CSS, and SWR. It renders retention and lifetime-value heatmaps directly from the CSV exports maintained by the analytics pipeline.

### Data Sources

- `public/data/purchase_retention.csv`
- `public/data/ltv_by_category_sku.csv`

These files are bundled with the app and fetched client-side; updating either file and redeploying refreshes the dashboard automatically. When a fetch fails, the UI falls back to a small hard-coded sample so layout still loads.

### Local Development

```bash
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to explore the dashboard. Filters update heatmaps instantly, and the Refresh button refetches the CSVs.

### Quality Checks

- `npm run lint` – ESLint
- `npm test` – Vitest unit tests for core analytics helpers
- `npm run build` – Next.js production build

### Deployment

The project is ready for Vercel. Set up a project pointing at this repository and each push to `main` will build the static site (CSV assets are served from `public/`).
