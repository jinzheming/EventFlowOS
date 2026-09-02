#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"
docker compose -f infra/docker-compose.dev.yml config >/dev/null
PERSONAL_AFFAIRS_RUNTIME_ENV_FILE="$ROOT/infra/.env.example" docker compose -f infra/docker-compose.server.yml config >/dev/null
