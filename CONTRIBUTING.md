# Contributing

Thanks for improving EventFlowOS. This project is currently optimized for self-hosted personal deployments, so changes should preserve conservative defaults and avoid assumptions about public multi-tenant operation.

## Development Setup

```bash
make verify
```

For release-candidate verification, provide a PostgreSQL test database and run:

```bash
export PERSONAL_AFFAIRS_TEST_DATABASE_URL=postgresql://personal_affairs:personal_affairs@127.0.0.1:5432/personal_affairs
make verify-release
```

## Pull Request Expectations

- Keep pull requests focused and explain the user-visible behavior change.
- Use labels from `.github/labels.yml`; maintainers should group dependency PRs before release review.
- Security-sensitive paths are covered by `.github/CODEOWNERS` and require maintainer review.
- Add or update tests for backend behavior, storage migrations, frontend state transitions, and security-sensitive changes.
- Do not commit real `.env` files, credentials, tokens, private hostnames, personal data exports, generated build output, or dependency caches.
- Do not widen CORS, disable CSRF, allow arbitrary outbound URLs, or weaken cookie flags without a documented security rationale.
- Use migration files for database changes and keep migrations forward-only.

## Security-Sensitive Changes

Treat authentication, authorization, CSRF, personal access tokens, webhooks, outbound HTTP, deployment scripts, and runtime configuration as security-sensitive. Prefer narrow allowlists, explicit defaults, and tests that show the protected failure mode.


## Merge Policy

- `main` should require pull requests, green CI, conversation resolution, no force pushes, and no branch deletion.
- Releases require the stricter `make verify-release` gate from a fresh clone.
- Dependabot PRs should be reviewed in small batches after CI passes; avoid leaving unrelated dependency PRs open across a beta release.
