# Personal Affairs

Self-hosted personal affairs manager for work items, personal tasks, projects, calendar reminders, outbound webhooks, and agent-native MCP access.

## Repository Layout

- `backend/` - FastAPI API, PostgreSQL migrations, reminder/webhook workers, and MCP server.
- `frontend/` - React/Vite web client.
- `infra/` - Dockerfiles, compose files, Nginx config, and guarded server deploy script.
- `openapi/` - OpenAPI contract snapshot.
- `docs/` - Aegis design and implementation notes.

## Local Development

```bash
cd backend
uv sync --all-extras
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
- `PERSONAL_AFFAIRS_BOOTSTRAP_USERNAME`
- `PERSONAL_AFFAIRS_BOOTSTRAP_PASSWORD`

Optional delivery adapters:

- `PERSONAL_AFFAIRS_FEISHU_WEBHOOK_URL`
- `PERSONAL_AFFAIRS_NTFY_TOPIC_URL`

Do not commit real passwords, webhook URLs, personal access tokens, session secrets, OAuth credentials, private keys, or full production connection strings.

## Deployment Boundary

The guarded deployment entrypoint is:

```bash
PERSONAL_AFFAIRS_RUNTIME_ENV_FILE=<absolute-runtime-env-path> bash infra/deploy_to_server.sh --confirm-production
```

Production deployment or promotion requires explicit operator confirmation because it can write PostgreSQL schema, start services, bind ports, consume runtime secrets, switch cookie security behavior, or enable external notifications.
