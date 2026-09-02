# Release Process

EventFlowOS releases are beta-quality artifacts for single-user self-hosted deployments. They are not SaaS readiness claims.

## Release Gate

Before tagging any release candidate, run the strict gate from a fresh clone:

```bash
export PERSONAL_AFFAIRS_TEST_DATABASE_URL=postgresql://personal_affairs:personal_affairs@127.0.0.1:5432/personal_affairs
make verify-release
```

The release gate requires:

- backend tests, Ruff, Pyright, Python dependency audit;
- frontend type check, Vitest tests, production build, npm audit, Playwright smoke E2E;
- development and server compose config validation;
- full-history gitleaks scan;
- PostgreSQL integration tests against `PERSONAL_AFFAIRS_TEST_DATABASE_URL`.

Record the final command output summary in the GitHub Release notes.

## v0.1.0-beta.1 Checklist

- Confirm `main` branch protection is enabled and required CI checks are green.
- Confirm private vulnerability reporting, secret scanning, push protection, Dependabot alerts, and Dependabot security updates are enabled where available.
- Confirm no open maintainer PR blocks the release branch.
- Confirm runtime defaults still match the single-user self-hosted boundary.
- Confirm `infra/.env.example`, `docs/deployment.md`, and `docs/threat-model.md` match the release behavior.
- Create an annotated tag named `v0.1.0-beta.1` only after the gate passes.
- Publish a GitHub Release marked as prerelease with known limitations and upgrade/rollback notes.

## Known Limitations

- EventFlowOS is reviewed for single-user self-hosted use only.
- Multi-tenant isolation, public registration, organization administration, billing, and shared hosted operation are out of scope.
- In-process rate limits are per process and reset on restart; public deployments need edge rate limits.
- Webhook delivery is at-least-once; receivers must be idempotent.
- MCP access must stay bound to loopback or a trusted private network unless an operator adds a separate authenticated edge.
- Internal package names, command names, image names, and `PERSONAL_AFFAIRS_*` environment variables remain for compatibility.

## Upgrade Notes

- Back up PostgreSQL before pulling a new release or running migrations.
- Review `infra/.env.example` for newly introduced required or security-sensitive variables.
- Run migrations once with the target release image or local backend environment.
- Restart API, reminder worker, webhook worker, MCP server, and web frontend together after migration.
- Confirm `/api/v1/ready`, `/api/v1/reminders/health`, and `/api/v1/webhooks/health` after restart.

## Rollback Notes

- Prefer restoring the pre-upgrade PostgreSQL backup into a fresh database over relying on reverse migrations.
- Roll back containers or source checkout to the previous release tag.
- Point `PERSONAL_AFFAIRS_DATABASE_URL` at the restored database and restart services.
- Re-run the readiness checks before re-enabling external notification or webhook delivery.
