# EventFlowOS

Self-hosted event-flow operating system for work items, personal tasks, projects, calendar reminders, outbound webhooks, and agent-native MCP access.

## What It Is

- A personal operations system for capturing tasks, work items, projects, reminders, calendar feeds, and lightweight agent proposals.
- A FastAPI backend with PostgreSQL migrations, reminder and webhook workers, and an MCP server for agent-native access.
- A React/Vite web client designed for a single operator's self-hosted deployment.

## What It Is Not

- Not a hosted SaaS product.
- Not yet reviewed for multi-tenant isolation, organization administration, billing, or public user registration.
- Not a place to store secrets in the repository; runtime secrets belong outside git.

## Project Status

EventFlowOS is an early-preview, self-hosted, single-user application. It is suitable for personal deployments where the operator controls the runtime environment, database, and reverse proxy. It is not yet hardened or reviewed as a multi-tenant SaaS product.

## Repository Layout

- `backend/` - FastAPI API, PostgreSQL migrations, reminder/webhook workers, and MCP server.
- `frontend/` - React/Vite web client.
- `infra/` - Dockerfiles, compose files, Nginx config, and guarded server deploy script.
- `openapi/` - OpenAPI contract snapshot.
- `docs/` - Aegis design and implementation notes.

See `docs/deployment.md` for the production boundary, security checklist, and backup/restore runbook.
See `docs/open-source-readiness.md` for the current release-candidate readiness notes and residual risks.

## Local Development

```bash
cd backend
uv sync --all-extras --locked
uv run personal-affairs-migrate
uv run personal-affairs-api
cd ..

npm ci --prefix frontend
npm run dev --prefix frontend
```

For a full local stack with PostgreSQL:

```bash
docker compose -f infra/docker-compose.dev.yml up --build
```

Default local ports:

- Web: `http://127.0.0.1:18110`
- API: `http://127.0.0.1:18098`
- PostgreSQL: `127.0.0.1:15444`

## Verification

```bash
cd backend
uv run pytest -q
uv run ruff check src tests
uv run pyright
cd ..
npm test --prefix frontend
npm audit --prefix frontend --audit-level=moderate
npm run lint --prefix frontend
npm run build --prefix frontend
docker compose -f infra/docker-compose.dev.yml config
PERSONAL_AFFAIRS_RUNTIME_ENV_FILE=<absolute-path-to-runtime-env-or-env-example> docker compose -f infra/docker-compose.server.yml config
```

## Runtime Configuration

Runtime configuration is supplied through environment variables. Keep real secrets outside git.

Start from `infra/.env.example` for local or server runtime variables. At minimum, configure:

- `PERSONAL_AFFAIRS_APP_ENV`
- `PERSONAL_AFFAIRS_DATABASE_URL`
- `PERSONAL_AFFAIRS_DEFAULT_TIMEZONE`
- `PERSONAL_AFFAIRS_API_DOCS_ENABLED`
- `PERSONAL_AFFAIRS_ALLOWED_HOSTS`
- `PERSONAL_AFFAIRS_BOOTSTRAP_USERNAME`
- `PERSONAL_AFFAIRS_BOOTSTRAP_PASSWORD`

Production API docs and OpenAPI JSON are disabled by default. Set `PERSONAL_AFFAIRS_API_DOCS_ENABLED=true` only for trusted environments or when the route is protected at the edge.

Set `PERSONAL_AFFAIRS_ALLOWED_HOSTS` to a comma-separated list of accepted Host header values in production, for example `tasks.example.com` or `tasks.example.com,*.internal.example.com`. Production startup fails if this value is empty.

The API includes a small in-process rate limiter for login, personal access token creation, and webhook creation. For internet-facing deployments, keep the application limits enabled and add equivalent limits at the reverse proxy or load balancer because in-process limits are per process.

- `PERSONAL_AFFAIRS_RATE_LIMIT_ENABLED`
- `PERSONAL_AFFAIRS_RATE_LIMIT_WINDOW_SECONDS`
- `PERSONAL_AFFAIRS_LOGIN_RATE_LIMIT_ATTEMPTS`
- `PERSONAL_AFFAIRS_TOKEN_CREATE_RATE_LIMIT_ATTEMPTS`
- `PERSONAL_AFFAIRS_WEBHOOK_CREATE_RATE_LIMIT_ATTEMPTS`

Optional delivery adapters:

- `PERSONAL_AFFAIRS_FEISHU_WEBHOOK_URL`
- `PERSONAL_AFFAIRS_NTFY_TOPIC_URL`

Outbound webhook subscriptions reject localhost, private, link-local, reserved, and other non-public destinations by default. Set `PERSONAL_AFFAIRS_WEBHOOK_ALLOWED_HOSTS` to narrow public destinations further; it accepts exact hosts plus suffix entries such as `.example.com` or `*.example.com`. Set `PERSONAL_AFFAIRS_WEBHOOK_ALLOW_PRIVATE_URLS=true` only when the runtime is intentionally allowed to call trusted internal targets.

Optional Feishu IM text ingestion is disabled by default and only accepts passive text callback events. It does not read history, poll chats, or process images, files, or voice messages.

- Feishu callback URL: `<public-base-url>/api/v1/integrations/feishu/im/events`
- Enable only after configuring `PERSONAL_AFFAIRS_FEISHU_IM_ENABLED=true`.
- Configure `PERSONAL_AFFAIRS_FEISHU_IM_VERIFICATION_TOKEN` and, if enabled in Feishu, `PERSONAL_AFFAIRS_FEISHU_IM_ENCRYPT_KEY` from the runtime secret store.
- Set exactly one default EventFlowOS owner through `PERSONAL_AFFAIRS_FEISHU_IM_DEFAULT_USER_ID` or `PERSONAL_AFFAIRS_FEISHU_IM_DEFAULT_USERNAME`.
- Before production enablement, send Feishu URL verification and one test text event from a test app, then confirm the callback creates one pending proposal and duplicate delivery does not create another proposal.

Optional Tencent Meeting completion through `tmeet` is backend-only, read-only, and disabled by default.

- Enable with `PERSONAL_AFFAIRS_TMEET_ENABLED=true` only on a server where the `tmeet` CLI is installed and authenticated.
- Keep `PERSONAL_AFFAIRS_TMEET_ALLOWED_COMMANDS=meeting:get`; no create, update, cancel, recording, minutes, or report command is allowed in V1.
- Use `PERSONAL_AFFAIRS_TMEET_HOME` for the CLI authorization directory when the runtime user needs a dedicated config path.
- The adapter assumes a read command shaped like `tmeet meeting get --meeting-id <id> --format json` or `--meeting-code <code>`; verify the actual installed CLI contract before enabling it outside a test environment.

Do not commit real passwords, webhook URLs, personal access tokens, session secrets, OAuth credentials, private keys, or full production connection strings.

## Security and Contributions

- Report vulnerabilities privately using `SECURITY.md`.
- Use `CONTRIBUTING.md` before opening pull requests.
- CI runs backend tests, static checks, dependency audits, compose validation, Docker build validation, frontend build checks, CodeQL, and secret scanning.

## Deployment Boundary

The guarded deployment entrypoint is:

```bash
PERSONAL_AFFAIRS_RUNTIME_ENV_FILE=<absolute-runtime-env-path> bash infra/deploy_to_server.sh --confirm-production
```

Production deployment or promotion requires explicit operator confirmation because it can write PostgreSQL schema, start services, bind ports, consume runtime secrets, switch cookie security behavior, or enable external notifications.
