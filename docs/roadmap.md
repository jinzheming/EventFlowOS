# Roadmap

EventFlowOS is moving toward a public beta for single-user self-hosted deployments.

## v0.1.0-beta.1

- Establish release gate through `make verify-release`.
- Add frontend Vitest coverage and Playwright smoke E2E.
- Add PostgreSQL integration tests for migrations, item persistence, and webhook outbox health.
- Document the threat model, deployment boundary, upgrade notes, and rollback notes.
- Keep multi-user and multi-tenant claims explicitly out of scope.

## v0.1.x Stabilization

- Expand E2E coverage for project review, calendar feeds, recycle-bin recovery, and agent proposal approval.
- Improve webhook retry diagnostics and operator-visible failure summaries.
- Add import/export examples for personal backup workflows.
- Continue dependency updates in grouped, reviewed batches.

## Later Candidates

- Evaluate stronger distributed rate limiting for internet-facing installs.
- Evaluate DNS pinning or delivery-time IP binding for stricter webhook SSRF protection.
- Evaluate multi-user support only after a separate authorization and isolation review.
- Consider internal renaming from `personal_affairs` to EventFlowOS after compatibility planning.

## Good First Issues

- Add frontend tests for existing components with clear UI states.
- Improve troubleshooting entries in `docs/deployment.md` from real installation failures.
- Add screenshots or short terminal transcripts that do not expose personal data or private hostnames.
- Improve copy in issue templates and release notes without changing runtime behavior.
