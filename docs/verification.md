# Verification

Checked on 2026-11-25 on macOS with Python 3.12 and Node.js 25.9. The private primary source baseline was inspected from a temporary clone. The public candidate contains the full primary application directories, not a rewritten sample. The original worktree and live services were not edited.

| Check | Primary baseline | Portfolio candidate |
|---|---|---|
| Backend automated tests | 332 passed | 337 passed |
| Backend Ruff lint | Pass | Pass |
| Backend Ruff format | Pass, 135 files | Pass |
| Strict mypy | Pass, 135 files | Pass, 137 files |
| Storefront lint and TypeScript | Pass | Pass |
| Storefront production build | Pass | Pass |
| Brand portal lint/type/build | Pass | Pass |
| Six Alembic migrations on fresh local PostgreSQL | Not run on private data | Pass |
| Fictional seed on isolated database | Not run on private data | Pass |
| Chromium UI, API/CORS and real publication flow | Not run on private services | 13 passed |
| npm audit, storefront | 21 reported advisories | No known vulnerabilities |
| npm audit, brand portal | 18 reported advisories | No known vulnerabilities |
| pip-audit, backend environment | Advisories in 17 packages | No known vulnerabilities |
| Redacted Gitleaks clean directory and fresh history | Not a publication baseline | Pass |

The five added backend regression cases cover CSV/JSON CORS environment values and three seed safety conditions. Synthetic order-action tokens were normalized to low-entropy deterministic UUIDs after three Gitleaks false positives. No scan exclusions were added. One existing order-service test now fixes its frontend URL explicitly instead of inheriting unrelated local demo configuration. The image test was adapted to the portfolio's original SVG placeholder while preserving the remote image URL assertions. The publication test now waits for the catalog heading before navigating again, so it does not cancel the authentication bootstrap. An internal-link test checks the homepage's local links.

The real catalog browser test creates a fictional product through the brand portal, verifies its public API record and customer storefront card/detail page, changes its stock and archives it. Other browser smoke tests use mocked providers/API responses for checkout, account views and upload retry behavior. They do not establish live provider integration success.

No real payment, SMS, delivery, email, storage upload, production deployment, customer dataset, live credentials or public publication was exercised. Production operations, external integration credentials and real catalog content remain separate work.
