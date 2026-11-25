# Security and dependency review

This is a portfolio snapshot, not a claim of production certification. Only the isolated local demo and automated tests were exercised. No exploit demonstration or production service test was performed.

## Publication preparation

The repository starts with fresh Git history. Credentials, ignored environment files, browser state, operational logs, private legal documents, real server deployment configuration and external campaign photographs are excluded. Demo records use fictional names and reserved email domains. The local configuration helper creates random credentials in ignored files without printing them. Do not commit or reuse those values for production.

The demo seed rejects production mode, non-loopback database hosts and a missing explicit seed password before opening a database session. Compose exposes only loopback ports under a separate project and volume. Provider credentials are absent; the catalog demo does not start background delivery/email jobs or invoke payment providers.

## Application controls reviewed

The existing backend includes scoped bearer authorization, brand-product ownership checks, production JWT/CORS configuration validation, authentication rate limiting, webhook checks, upload size/type checks and feed URL validation. Automated tests cover these controls with fake providers and local inputs. The portfolio copy corrects CORS environment parsing so both CSV and JSON forms reach the declared validator. JWT encoding/verification now uses PyJWT with an explicit configured algorithm allowlist, replacing the advisory-bearing python-jose dependency and its ecdsa dependency.

The retired `/catalog/upload` path explicitly renders the existing not-found page instead of being interpreted as a product ID. This restores the behavior required by the original publication test without enabling an old bulk-upload route.

## Dependency checks

Both frontend lockfiles were refreshed after npm advisory checks. Next.js, React Router and Vite were updated within their existing major versions. The storefront keeps its original ESLint preset version with patched transitive dependencies, with the original React Hooks plugin version, preserving the baseline lint rules. Python dependencies were refreshed in the lockfile and the JWT library was replaced. See the verification report for final advisory counts and test results.

Dependency scans are time-specific. They do not prove the absence of unpublished vulnerabilities. Production use still requires your own secrets, verified media rights, provider setup, hosting configuration and an operational review appropriate to your deployment.
