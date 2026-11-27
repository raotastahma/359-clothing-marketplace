# 359 Clothing Marketplace

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/359-logo-white.png">
  <img src="assets/359-logo.png" alt="359 Clothing" width="190">
</picture>

I built 359 Clothing from scratch using AI throughout development. It includes a customer storefront, a brand portal and a backend for managing products and orders. It is ready for catalog and content entry.

This repository contains the full primary application source: a Next.js customer storefront, a React/Vite brand portal, a FastAPI backend, shared design tokens, database migrations, background tasks, provider adapters and automated tests. Some portal settings are currently local UI state rather than persisted backend settings. The original product targets a Russian-speaking market, so its interface still contains Russian copy. This portfolio documentation is in English.

## Visit the storefront

[Open the 359 Clothing catalog](https://359-shop.raotastahma.ru/shop). Browse the collection or select **New** or **Sale** from the storefront. For the brand experience, the local setup below lets you create a product, publish it to the storefront and update its stock.

## What is implemented

- Public product and brand catalog, search/filtering, product variants, favorites and cart.
- Customer phone sign-in with a development SMS adapter, plus checkout screens, order history and order actions. A production SMS provider is still needed.
- Brand account login, product/variant editing, publication, order management and financial views.
- Backend authorization, PostgreSQL persistence, Redis caching, payment webhooks and asynchronous jobs.
- Provider adapters for payments, delivery, email and object storage. The catalog demo runs locally. Live checkout still needs order-cancellation fixes, payment-provider verification and a production SMS adapter.

The verified demo creates a fictional product in the actual brand portal, checks its API and storefront visibility, changes its stock, then archives it and checks that it disappears from the public catalog. It uses a fresh local database and no live service credentials. Payment, delivery, email, external media upload and production operation are not claimed by this demonstration.

## Run the local demo

Requirements: Node.js 20.9+, Python 3.12+, `uv`, Docker Compose and Chromium for Playwright (`npx playwright install chromium` from `src/web`). The Compose project is isolated as `portfolio-359-demo`; published ports bind only to loopback.

From the repository root:

```sh
node scripts/configure-demo.mjs
docker compose --env-file .env.demo -f compose.demo.yml up -d --wait
cd src/backend
uv sync --extra dev --frozen
set -a
source .env
set +a
uv run alembic upgrade head
uv run python scripts/seed.py
uv run uvicorn app.main:app --host 127.0.0.1 --port 18000
```

The configuration helper generates random local secrets without printing them. It refuses to overwrite existing configuration. The seed accepts only a loopback development database and requires an explicit demo password. It creates fictional `brand@example.invalid` and `admin@example.invalid` records plus a synthetic catalog item. No production database export is included.

In a second terminal:

```sh
cd src/brand-portal
npm ci
VITE_API_URL=http://127.0.0.1:18000/api/v1 npm run dev -- --host 127.0.0.1 --port 3201
```

In a third terminal:

```sh
cd src/web
npm ci
NEXT_PUBLIC_API_URL=http://127.0.0.1:18000/api/v1 npm run dev -- --hostname 127.0.0.1 --port 3200
```

Open [storefront](http://127.0.0.1:3200), [brand portal](http://127.0.0.1:3201) or [API docs](http://127.0.0.1:18000/docs). The brand email is `brand@example.invalid`; its random password is the `DEMO_BRAND_PASSWORD` in your ignored local backend configuration. Use a local disposable password only. The placeholder product image is an original SVG, not a third-party photograph.

## Verification

Backend:

```sh
cd src/backend
uv run ruff check .
uv run ruff format --check .
uv run mypy . --strict
uv run pytest tests/ -q
```

Frontends: run `npm run lint` and `npm run build` in both frontend directories, plus `npx tsc --noEmit` in `src/web`.

For browser tests, stop the development frontend servers first. Playwright starts production preview servers on ports 3200 and 3201. Keep the demo backend running:

```sh
cd src/web
set -a
source ../backend/.env
set +a
STI_008_FULL_STACK=1 npx playwright test --project=chromium --reporter=line
```

Without `STI_008_FULL_STACK=1`, the database-backed tests are skipped and the remaining UI tests use mocked API responses. The fictional catalog publication test is in `src/web/tests/e2e/bp-catalog-publication.spec.ts`.

Stop only this demo's infrastructure from the repository root:

```sh
docker compose --env-file .env.demo -f compose.demo.yml down
```

The named demo database volume is retained. Delete it only when you deliberately want to reset your fictional demo data.

## Portfolio preparation

The complete primary application directories are retained. Private Git history, server deployment files, production environment files, operational tasks, personal/legal documents and production catalogs are excluded. Contact domains and seed accounts were made fictional. The local demo uses placeholder artwork for campaign and catalog imagery. This page shows the original storefront wordmark. Dependencies were refreshed after advisory checks, and the documented CORS environment parsing was corrected with regression coverage.

See [architecture](docs/architecture.md), [API guide](docs/api.md), [security notes](docs/security.md) and [verification](docs/verification.md). No open-source license has been selected.
