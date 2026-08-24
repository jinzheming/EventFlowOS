#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--confirm-production" ]]; then
  echo "Refusing to deploy without --confirm-production."
  echo "Before running, confirm production DB/schema writes, runtime secrets, Tailnet port binding, backup/rollback, and notification boundaries."
  exit 2
fi

TASK_COMPOSE_FILE="infra/docker-compose.server.yml"
TASK_ENV_FILE="${PERSONAL_AFFAIRS_RUNTIME_ENV_FILE:?set PERSONAL_AFFAIRS_RUNTIME_ENV_FILE}"
TASK_RELEASE_TAG="${PERSONAL_AFFAIRS_RELEASE_TAG:-$(date -u +%Y%m%d%H%M%S)}"
TASK_PYTHON_IMAGE="${PERSONAL_AFFAIRS_PYTHON_IMAGE:-public.ecr.aws/docker/library/python:3.12-slim}"
TASK_NODE_IMAGE="${PERSONAL_AFFAIRS_NODE_IMAGE:-node:20-bookworm-slim}"
TASK_NGINX_IMAGE="${PERSONAL_AFFAIRS_NGINX_IMAGE:-nginx:1.27-alpine}"
TASK_PIP_INDEX_URL="${PERSONAL_AFFAIRS_PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
TASK_UV_INDEX_URL="${PERSONAL_AFFAIRS_UV_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
TASK_NPM_REGISTRY="${PERSONAL_AFFAIRS_NPM_REGISTRY:-https://registry.npmmirror.com}"

# Optional egress proxy for the image builds (set PERSONAL_AFFAIRS_HTTP(S)_PROXY
# when direct downloads to files.pythonhosted.org / registry.npmjs.org hang).
TASK_PROXY_ARGS=()
if [[ -n "${PERSONAL_AFFAIRS_HTTP_PROXY:-}" ]]; then
  TASK_PROXY_ARGS+=(--build-arg HTTP_PROXY="$PERSONAL_AFFAIRS_HTTP_PROXY")
fi
if [[ -n "${PERSONAL_AFFAIRS_HTTPS_PROXY:-}" ]]; then
  TASK_PROXY_ARGS+=(--build-arg HTTPS_PROXY="$PERSONAL_AFFAIRS_HTTPS_PROXY")
fi

if [[ ! -r "$TASK_ENV_FILE" ]]; then
  echo "Runtime env file is missing or unreadable: $TASK_ENV_FILE"
  exit 1
fi

export PERSONAL_AFFAIRS_RUNTIME_ENV_FILE="$TASK_ENV_FILE"
export PERSONAL_AFFAIRS_API_IMAGE="personal-affairs-api:$TASK_RELEASE_TAG"
export PERSONAL_AFFAIRS_WEB_IMAGE="personal-affairs-web:$TASK_RELEASE_TAG"

docker compose -f "$TASK_COMPOSE_FILE" config >/dev/null

docker build \
  "${TASK_PROXY_ARGS[@]}" \
  -f infra/Dockerfile.api \
  --build-arg PYTHON_IMAGE="$TASK_PYTHON_IMAGE" \
  --build-arg PIP_INDEX_URL="$TASK_PIP_INDEX_URL" \
  --build-arg UV_INDEX_URL="$TASK_UV_INDEX_URL" \
  -t "$PERSONAL_AFFAIRS_API_IMAGE" \
  .
docker build \
  "${TASK_PROXY_ARGS[@]}" \
  -f infra/Dockerfile.web \
  --build-arg NODE_IMAGE="$TASK_NODE_IMAGE" \
  --build-arg NGINX_IMAGE="$TASK_NGINX_IMAGE" \
  --build-arg NPM_REGISTRY="$TASK_NPM_REGISTRY" \
  --build-arg NGINX_CONF=infra/nginx.server.conf \
  -t "$PERSONAL_AFFAIRS_WEB_IMAGE" \
  .

docker run --rm --network host --env-file "$TASK_ENV_FILE" "$PERSONAL_AFFAIRS_API_IMAGE" personal-affairs-migrate
docker compose -f "$TASK_COMPOSE_FILE" up -d

for TASK_ATTEMPT in {1..20}; do
  if curl -fsS http://127.0.0.1:18098/api/v1/health >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS http://127.0.0.1:18098/api/v1/health >/dev/null
curl -fsS http://127.0.0.1:18110/ >/dev/null

echo "Personal affairs service deployed and health checks passed."
echo "API image: $PERSONAL_AFFAIRS_API_IMAGE"
echo "Web image: $PERSONAL_AFFAIRS_WEB_IMAGE"
