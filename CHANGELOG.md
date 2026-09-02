# Changelog

All notable changes to EventFlowOS will be documented in this file.

The format is based on Keep a Changelog, and this project uses semantic versioning once tagged releases begin.

## [0.1.0-beta] - Unreleased

### Added

- Open-source governance files: security policy, contribution guide, issue templates, pull request template, and code of conduct.
- GitHub CI for backend tests, static checks, dependency audits, frontend build checks, compose validation, Docker image build validation, CodeQL, and secret scanning.
- Deployment runbook covering production configuration, host/header/body limits, rate limiting, webhook boundaries, backups, and release checks.
- Open-source readiness note summarizing verification evidence and residual risks.
- Release process, threat model, roadmap, CODEOWNERS, label catalog, and unified verification scripts.
- Frontend Vitest coverage, Playwright smoke E2E, and PostgreSQL integration tests for release gating.

### Changed

- Public project branding now uses EventFlowOS while internal package, command, and environment-variable names remain compatible with the existing `personal_affairs` runtime.
- Production OpenAPI and interactive docs are disabled by default.
- Production API startup now requires explicit Host header allowlisting through `PERSONAL_AFFAIRS_ALLOWED_HOSTS`.
- Nginx examples include security headers, request body limits, and edge rate limits for login, token creation, and webhook creation paths.
- CI now calls shared verification scripts and runs database-backed integration tests.

### Security

- Outbound webhook URLs are validated before storage and before delivery, with private, local, link-local, reserved, and otherwise non-public destinations rejected by default. Redirects are blocked and failed response body capture is bounded.
- Login, personal access token creation, and webhook creation have in-process rate limits.
- Frontend dependency pins were refreshed and `nanoid` is overridden to a patched version.

### Deferred

- Full internal rename from `personal_affairs` to EventFlowOS.
- Distributed rate limiting, stronger DNS rebinding defenses for webhooks, release tagging, container publishing, and multi-tenant SaaS hardening.
