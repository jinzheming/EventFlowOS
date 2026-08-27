# Deployment and Operations

This runbook describes the safe baseline for running EventFlowOS as a self-hosted personal application.

## Production Boundary

- Run the API, workers, MCP server, PostgreSQL, and web frontend in an environment controlled by the operator.
- Terminate TLS at a reverse proxy, load balancer, or trusted edge before traffic reaches the containers.
- Keep the backend API and MCP listener bound to private or loopback interfaces unless intentionally exposed behind authentication and rate limits.
- Treat browser-delivered frontend configuration as public; never place secrets in the frontend bundle.

## Required Runtime Configuration

Start from `infra/.env.example` and store the real runtime file outside git.

- `PERSONAL_AFFAIRS_APP_ENV=production`
- `PERSONAL_AFFAIRS_DATABASE_URL=<runtime secret>`
- `PERSONAL_AFFAIRS_DEFAULT_TIMEZONE=<iana-time-zone>`
- `PERSONAL_AFFAIRS_BOOTSTRAP_USERNAME=<initial operator>`
- `PERSONAL_AFFAIRS_BOOTSTRAP_PASSWORD=<runtime secret>`
- `PERSONAL_AFFAIRS_ALLOWED_HOSTS=<public hostnames>`

The API fails to start in production if `PERSONAL_AFFAIRS_ALLOWED_HOSTS` is empty. Use exact hostnames and only add wildcard suffixes when the reverse-proxy boundary is understood.

The server compose healthcheck connects over loopback but sends the first configured allowed host as the HTTP `Host` header. Keep that first value as a concrete hostname, not a wildcard-only entry.

Keep `PERSONAL_AFFAIRS_API_DOCS_ENABLED=false` unless the docs route is protected by a trusted network boundary or separate authentication.

## Host, Header, and Body Limits

- Configure `PERSONAL_AFFAIRS_ALLOWED_HOSTS` with the exact production hostnames accepted by the app.
- Keep the Nginx security headers enabled for the SPA shell, static assets, and API responses.
- Keep `client_max_body_size` low unless a feature explicitly requires larger request bodies.
- If running behind another proxy, configure forwarded-header trust there; do not trust arbitrary `X-Forwarded-*` headers from the open internet.

## Rate Limiting

The app includes in-process limits for login, personal access token creation, and webhook creation. These reduce accidental abuse and simple online guessing, but they are per process and reset on restart.

For internet-facing deployments, add edge limits for at least:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/tokens`
- `POST /api/v1/webhooks`
- any future file upload, import, AI, or expensive search endpoints

The bundled Nginx examples define conservative `limit_req` zones for login, token creation, and webhook creation paths. Tune these values at the outermost public edge if another proxy or tunnel sits in front of Nginx.

Cookie-authenticated write endpoints require a CSRF token. SameSite cookies and edge checks are defense in depth; do not disable the token requirement for browser clients.

## Outbound Webhooks

Webhook subscriptions reject localhost, private, link-local, reserved, and other non-public destinations by default. Prefer setting `PERSONAL_AFFAIRS_WEBHOOK_ALLOWED_HOSTS` to a comma-separated allowlist of public callback hosts. The allowlist accepts exact hosts plus suffix entries such as `.example.com` or `*.example.com`.

Only set `PERSONAL_AFFAIRS_WEBHOOK_ALLOW_PRIVATE_URLS=true` when internal callbacks are an explicit deployment requirement and the runtime network is trusted.

## Backups

Create a database backup before deploys, migrations, dependency upgrades, or public exposure:

```bash
pg_dump "$PERSONAL_AFFAIRS_DATABASE_URL" --format=custom --file personal_affairs-$(date +%Y%m%d-%H%M%S).dump
```

Restore into a fresh database before relying on a backup:

```bash
createdb personal_affairs_restore_test
pg_restore --dbname personal_affairs_restore_test --clean --if-exists personal_affairs-YYYYMMDD-HHMMSS.dump
```

Keep backups encrypted at rest, separate from the server, and covered by the same access controls as production secrets.

## Release Checklist

- Run backend tests, Ruff, Pyright, frontend lint/build, dependency audits, compose config validation, and secret scanning.
- Confirm real secrets are not present in current files or git history.
- Confirm `PERSONAL_AFFAIRS_ALLOWED_HOSTS` matches the production hostname.
- Confirm API docs are disabled or protected.
- Confirm webhook private URL access is disabled unless explicitly needed.
- Confirm a restorable PostgreSQL backup exists before running migrations.
- Confirm branch protection, secret scanning, Dependabot alerts, and private vulnerability reporting are enabled before public release.
