# Contributing

Thanks for improving EventFlowOS. This project is currently optimized for self-hosted personal deployments, so changes should preserve conservative defaults and avoid assumptions about public multi-tenant operation.

## Development Setup

```bash
cd backend
uv sync --all-extras
uv run personal-affairs-migrate
uv run pytest -q
uv run ruff check src tests
uv run pyright
cd ..

npm ci --prefix frontend
npm run lint --prefix frontend
npm run build --prefix frontend
```

For compose validation:

```bash
docker compose -f infra/docker-compose.dev.yml config
PERSONAL_AFFAIRS_RUNTIME_ENV_FILE=$PWD/infra/.env.example docker compose -f infra/docker-compose.server.yml config
```

## Pull Request Expectations

- Keep pull requests focused and explain the user-visible behavior change.
- Add or update tests for backend behavior, storage migrations, frontend state transitions, and security-sensitive changes.
- Do not commit real `.env` files, credentials, tokens, private hostnames, personal data exports, generated build output, or dependency caches.
- Do not widen CORS, disable CSRF, allow arbitrary outbound URLs, or weaken cookie flags without a documented security rationale.
- Use migration files for database changes and keep migrations forward-only.

## Security-Sensitive Changes

Treat authentication, authorization, CSRF, personal access tokens, webhooks, outbound HTTP, deployment scripts, and runtime configuration as security-sensitive. Prefer narrow allowlists, explicit defaults, and tests that show the protected failure mode.
