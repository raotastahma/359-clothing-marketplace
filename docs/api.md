# API guide

Run the local backend and visit `/docs` for the generated OpenAPI interface, or `/openapi.json` for the full schema. `/health` reports API process health, not a complete external dependency readiness check.

Core route groups under `/api/v1` include `products`, `brands`, `categories`, `auth`, `users`, `cart`, `orders`, `payments`, `delivery`, `brand-portal` and `admin`. Authentication uses bearer access/refresh tokens with server-side user and role checks. Brand product operations enforce product ownership. Administrative operations require the admin scope.

The local demo uses `POST /brand-portal/auth/login` for its fictional brand account. Product creation and editing use `/brand-portal/products`; public catalog reads use `/products`. The exact request schemas and status codes are generated directly from the included source.

Payment webhooks, signed order-action links, storage uploads and delivery adapters require separate configuration. Automated unit/API tests inject fake providers; no live payment or delivery request is needed for the catalog demo.
