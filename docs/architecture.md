# Architecture

The customer storefront is a Next.js application in `src/web`. It calls the FastAPI API under `/api/v1` and adapts product responses for the catalog and product detail components. The React/Vite application in `src/brand-portal` uses authenticated brand endpoints for product, order and financial workflows. Shared UI tokens are in `src/shared`.

The Python backend in `src/backend/app` separates HTTP routes, schemas, service logic, provider integrations, authorization and infrastructure clients. PostgreSQL is the persistent store; Alembic migrations live in `src/backend/alembic`. Redis supports caching and authentication rate limiting. Celery task modules support email, delivery and SLA processing, but the local catalog demo does not start workers or contact those external providers.

Product publication follows brand portal form submission, authenticated brand API authorization, product/variant database writes, cache invalidation, public catalog API reads and storefront rendering. The browser publication test verifies the same product across these layers, including stock changes and archival visibility.

`compose.demo.yml` starts only an isolated PostgreSQL and Redis instance. Backend and frontends run as local development processes. No production hosting configuration or production credentials are bundled.
