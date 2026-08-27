# Open Source Readiness

This note records the release-candidate checks for opening EventFlowOS as a self-hosted, single-user project. It intentionally avoids production hostnames, private network addresses, secret paths, personal data, and credential material.

## Current Release Boundary

- EventFlowOS is ready to be reviewed as an early `0.1.0-beta` candidate, not as a multi-tenant SaaS platform.
- Public branding uses EventFlowOS; internal Python package names, CLI commands, image names, OpenAPI file names, and `PERSONAL_AFFAIRS_*` environment variables remain stable for compatibility.
- Feishu IM ingestion, Tencent Meeting completion, outbound webhooks, and production deployment remain opt-in and disabled by default.

## Completed Hardening

- Production OpenAPI and interactive docs are disabled unless explicitly enabled.
- Production startup requires `PERSONAL_AFFAIRS_ALLOWED_HOSTS` so Host header validation cannot be accidentally omitted.
- Cookie-authenticated write endpoints require CSRF tokens; personal access tokens require the `write` scope for state-changing routes.
- Webhook subscriptions validate outbound URLs on create and again before delivery; private, local, reserved, and non-public destinations are rejected by default.
- Login, personal access token creation, and webhook creation have application-level rate limits.
- Nginx examples include CSP, `nosniff`, clickjacking protection, referrer policy, permissions policy, body size limits, and edge rate-limit examples.

## Repository Controls

- CI covers backend tests, Ruff, Pyright, Python dependency audit, frontend npm audit, frontend lint/build, compose validation, Docker build validation, CodeQL, and gitleaks.
- Dependabot is configured for GitHub Actions, frontend npm, and backend Python dependency manifests where GitHub supports them.
- Issue templates, pull request template, contribution guide, security policy, and code of conduct are present.

## Verification Evidence

- Backend verification has passed previously with the full test suite, Ruff, and Pyright after P0/P1 security hardening.
- Frontend verification has passed previously with `npm ci`, `npm audit`, `npm run lint`, and `npm run build` after dependency refresh.
- Compose config validation has passed for both dev and server compose files using the example runtime environment.
- High-confidence scans of current files and git history previously found no obvious committed production secrets; repeat the scans from a fresh clone before publishing.

## Residual Risks

- The in-process rate limiter is per process and resets on restart; internet-facing deployments should enforce equivalent limits at the edge.
- Webhook DNS rebinding resistance is basic; the current guard rejects unsafe resolved addresses, but hardened production use should consider pinning resolved IPs through the delivery attempt.
- Multi-user account management and multi-tenant isolation have not been fully reviewed; public messaging must keep the single-user self-hosted boundary.
- Full EventFlowOS internal renaming is deferred to avoid breaking existing runtime commands and deployment configuration.

## Manual GitHub Settings Checklist

- Enable branch protection for `main`: pull requests required, required CI checks, no force pushes, no branch deletion, and conversation resolution required.
- Enable secret scanning, push protection, Dependabot alerts, Dependabot security updates, and private vulnerability reporting when available.
- Set repository description and topics only after README and release notes are reviewed.
- Do not create a public release, tag, package, or container image until the fresh-clone verification is green.
