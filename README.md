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

Optional Feishu IM text ingestion is disabled by default and only accepts passive text callback events. It does not read history, poll chats, or process images, files, or voice messages.

- Feishu callback URL: `<public-base-url>/api/v1/integrations/feishu/im/events`
- Enable only after configuring `PERSONAL_AFFAIRS_FEISHU_IM_ENABLED=true`.
- Configure `PERSONAL_AFFAIRS_FEISHU_IM_VERIFICATION_TOKEN` and, if enabled in Feishu, `PERSONAL_AFFAIRS_FEISHU_IM_ENCRYPT_KEY` from the runtime secret store.
- Set exactly one default Personal Affairs owner through `PERSONAL_AFFAIRS_FEISHU_IM_DEFAULT_USER_ID` or `PERSONAL_AFFAIRS_FEISHU_IM_DEFAULT_USERNAME`.
- Before production enablement, send Feishu URL verification and one test text event from a test app, then confirm the callback creates one pending proposal and duplicate delivery does not create another proposal.

Optional Tencent Meeting completion through `tmeet` is backend-only, read-only, and disabled by default.

- Enable with `PERSONAL_AFFAIRS_TMEET_ENABLED=true` only on a server where the `tmeet` CLI is installed and authenticated.
- Keep `PERSONAL_AFFAIRS_TMEET_ALLOWED_COMMANDS=meeting:get`; no create, update, cancel, recording, minutes, or report command is allowed in V1.
- Use `PERSONAL_AFFAIRS_TMEET_HOME` for the CLI authorization directory when the runtime user needs a dedicated config path.
- The adapter assumes a read command shaped like `tmeet meeting get --meeting-id <id> --format json` or `--meeting-code <code>`; verify the actual installed CLI contract before enabling it outside a test environment.

Do not commit real passwords, webhook URLs, personal access tokens, session secrets, OAuth credentials, private keys, or full production connection strings.

## Deployment Boundary

The guarded deployment entrypoint is:

```bash
PERSONAL_AFFAIRS_RUNTIME_ENV_FILE=<absolute-runtime-env-path> bash infra/deploy_to_server.sh --confirm-production
```

Production deployment or promotion requires explicit operator confirmation because it can write PostgreSQL schema, start services, bind ports, consume runtime secrets, switch cookie security behavior, or enable external notifications.
