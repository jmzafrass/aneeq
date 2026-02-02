# Aneeq

Monorepo for Aneeq operations: analytics dashboard, data automation scripts, and cloud services.

## Structure

| Directory | What | Stack |
|-----------|------|-------|
| `dashboard/` | Analytics dashboard (orders, retention, LTV, users) | Next.js, TypeScript, Vercel |
| `scripts/` | Data operations & marketing campaigns | Python |
| `services/` | Cloud microservices | FastAPI |
| `docs/` | Documentation | Markdown |

## Quick Start

### Dashboard

```bash
cd dashboard
npm install
npm run dev
```

### Python Scripts

```bash
source .venv/bin/activate
python3 scripts/segmentation/campaign_manager.py --list
```
