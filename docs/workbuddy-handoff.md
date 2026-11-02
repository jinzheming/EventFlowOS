# EventFlowOS to WorkBuddy Handoff

Date: 2026-11-02

## Request

Connect the WorkBuddy cloud agent to the EventFlowOS remote MCP server. Add it
as a remote Streamable HTTP MCP server and enable the agent to call its tools.

## Connection

- MCP endpoint: `https://tag.eventflowos.com/mcp`
- Transport: Streamable HTTP
- Authentication: HTTP Bearer token
- Header: `Authorization: Bearer <EVENTFLOWOS_PAT>`
- PAT scopes: `read` and `write` if the agent needs both read and mutation tools

Create the PAT in EventFlowOS Settings and enter it directly into WorkBuddy's
credential field. Do not put the PAT in this file, source control, prompts, or
chat messages.

Example server configuration:

```json
{
  "mcpServers": {
    "eventflowos": {
      "url": "https://tag.eventflowos.com/mcp",
      "headers": {
        "Authorization": "Bearer <EVENTFLOWOS_PAT>"
      }
    }
  }
}
```

Use WorkBuddy's equivalent fields if it does not accept this JSON format:

- Name: `eventflowos`
- URL: `https://tag.eventflowos.com/mcp`
- Authentication/header: Bearer token supplied as `Authorization`
- Transport: Streamable HTTP

## Server Routing

- Cloudflare public hostname: `tag.eventflowos.com`
- Cloudflare Tunnel origin service: `http://127.0.0.1:18110`
- `/api/...` is proxied by Nginx to the EventFlowOS API.
- `/mcp` and `/.well-known/oauth-protected-resource/mcp` are proxied by
  Nginx to the loopback-only MCP listener on port `18099`.
- The MCP listener is not directly exposed on a public interface.
- The Cloudflare Tunnel connector currently uses HTTP/2.

Cloudflare Access was not independently verified. If an Access policy is
enabled for this hostname, WorkBuddy must be able to satisfy it without an
interactive browser login. Configure a compatible service-token policy and
headers, or a suitable non-interactive Access policy. Keep the EventFlowOS PAT
header as a separate credential.

## Verification and Known Issue

Verified on 2026-11-02:

- The Tunnel was active with four registered HTTP/2 connections.
- `https://tag.eventflowos.com/api/v1/health` returned
  `{"status":"ok"}` in successful probes.
- Unauthenticated requests to `/mcp` returned HTTP `401` with a Bearer
  authentication challenge, as expected.
- The protected-resource metadata URL returned JSON with the MCP resource URL
  and Bearer-header authentication method.

The server-side Tunnel and service are connected, but public probes from the
server were intermittently slow or timed out. The most recent batch had one
timeout in three API probes; all three unauthenticated MCP probes returned
`401`. Test from WorkBuddy's cloud environment and report the complete
connection error and timestamp if it still times out.

## WorkBuddy Acceptance Test

1. Save the remote MCP server configuration and test the connection.
2. Confirm MCP initialization succeeds with the PAT.
3. Confirm the tool list is returned.
4. Call a read-only EventFlowOS tool first.
5. Only test write tools if the PAT has `write` scope and the action is
   explicitly intended.

Do not include the PAT in test output or diagnostic logs.

## Acceptance Result (WorkBuddy side)

Tested 2026-11-02 from a network outside the server LAN (macOS client, Cloudflare anycast edge).

| Step | Result |
|---|---|
| DNS / TLS | `tag.eventflowos.com` → 104.21.20.42 / 172.67.191.83, HTTP/2 200, `server: cloudflare` |
| `/api/v1/health` | 200, 5/5 probes, TTFB 0.96–1.24 s — no timeouts observed this round |
| Cloudflare Access | **Not intercepting.** Browserless request returned the app's own `401`, not a 302 to a login page. No service token is required. |
| Unauthenticated `/mcp` | `401` + `WWW-Authenticate: Bearer error="invalid_token"` + `resource_metadata` — spec-compliant |
| Protected-resource metadata | `{"resource":"https://tag.eventflowos.com/mcp","authorization_servers":[...],"bearer_methods_supported":["header"]}` |
| `initialize` with PAT | 200, `text/event-stream`, `Mcp-Session-Id` issued, protocol `2025-06-18` |
| `serverInfo` | `Personal Affairs` `1.29.1` |
| `tools/list` | 30 tools returned (`pa_list_items`, `pa_get_executive_briefing`, `pa_set_reminder`, …) |
| Read-only call `pa_reminder_health` | `worker_seen_recently: true`, pending/retry/dead = 0/0/0 |
| Read-only call `pa_list_items` | Real records returned |

No write tool was exercised, and the PAT used for the test was not written into this file.

### Open issue — PAT scopes are not enforced on the MCP surface

`_PersonalAccessTokenVerifier.verify_token()` puts `scopes` into the returned `AccessToken`,
but no tool body checks them; `_user_id()` only resolves `user_id` from the token. A PAT
created with `scopes: ["read"]` can therefore call `pa_create_item`, `pa_update_item`,
`pa_delete_reminder`, and every other write tool. The "PAT scopes: read and write if the agent
needs both" line above should be read as advisory, not as an enforced boundary.

Until this is fixed, treat any PAT handed to an agent as full read+write over the account, and
rely on revocation for containment.

## Client-Side Setup Notes (WorkBuddy)

Two client-side facts, both found by inspection rather than guesswork:

1. **`type` must be `http`, not `streamableHttp`.** WorkBuddy reads `~/.workbuddy/mcp.json`
   once at application start; a server added while the app is running is invisible until the
   app is restarted. The working entry is:

   ```json
   "eventflowos": {
     "type": "http",
     "url": "https://tag.eventflowos.com/mcp",
     "headers": { "Authorization": "Bearer <PAT>" },
     "timeout": 60000
   }
   ```

2. **Cloudflare rejects default Python clients.** `POST /api/v1/auth/login` with
   `User-Agent: Python-urllib/3.13` returns `403` at the edge; the same request with a `curl`
   or browser UA succeeds. If an agent or script is going to call the REST API directly, set an
   explicit User-Agent instead of relying on the library default.

### Credentials in use

| Token | Scope | Expiry | Status |
|---|---|---|---|
| `workbuddy-mcp` | read, write | none | active — used by the WorkBuddy MCP entry |
| `mcp-server` | read, write | none | active — pre-existing, unchanged |
| `workbuddy-acceptance` | read | 30 d | **revoked** (test-only) |

Because scopes are not enforced on the MCP surface (see open issue above), all three are
effectively read+write at the tool layer. Revoke `workbuddy-mcp` from EventFlowOS Settings if
the WorkBuddy entry is ever retired.

## Round 2 Acceptance — native MCP client (WorkBuddy)

Tested 2026-11-02 10:14–10:17 CST, driven by WorkBuddy's own MCP client (not manual HTTP),
after the app restart that loaded the `eventflowos` entry.

### Read path — all OK

| Tool | Result |
|---|---|
| `pa_get_executive_briefing` | 200, `timezone: Asia/Shanghai`, window honoured |
| `pa_list_items` | Real records returned (5/5) |
| `pa_list_items` (status=planned) | Empty — correct, no planned items exist |
| `pa_get_item` | Full record incl. tags/people/relations |
| `pa_get_project_context` | Project `港股` + items + relations |
| `pa_list_people` | 10 people |
| `pa_list_calendar` (11-01…11-08) | Empty — correct, no events that week |
| `pa_reminder_health` | `worker_seen_recently: true`, 0/0/0 |

### Write path — end-to-end verified

Sequence: `pa_create_item` → `pa_set_reminder` → worker delivery → `pa_get_executive_briefing`
shows it under `unread_reminders` → `pa_ack_delivery` → `pa_delete_reminder` →
`pa_update_item status=cancelled`.

| Property | Observed |
|---|---|
| Idempotency | Same `client_request_id` re-submitted → same item id, `version` still 1, no duplicate row |
| Reminder delivery | scheduled `02:16:00Z`, delivered `02:16:04Z` — **+4 s worker latency** |
| Channel | `in_app`, `attempt_count: 1`, no error codes |
| Optimistic locking | `pa_update_item` with stale `if_match=v1` → `Item version is stale` (rejected, no write) |
| Cleanup | item `cancelled`, reminder inactive, briefing back to all-zero |

### Bug — `pa_create_item` silently drops `notes`

`notes` is declared in the tool signature (`mcp/server.py:315`) but is **absent from the
`fields` dict** that builds `ItemCreate` (around `mcp/server.py:348-378`). Result: the argument is
accepted, no error is raised, and the column stays NULL. `pa_update_item` *does* include `notes`
in `patch_fields`, so the two paths disagree.

Workaround until fixed: create the item, then patch `notes` in a second `pa_update_item` call.
Verified working (v2 → v3, notes persisted).

### Minor — actor attribution

Items created through the MCP surface carry `created_by_actor: "human"` and
`updated_by_actor: "human"`, so agent-originated writes are indistinguishable from the user's own
in the activity trail.

## Fix — `pa_create_item` notes dropped (2026-11-02)

### Change

One line added to the `fields` dict in `pa_create_item` (`backend/src/personal_affairs/mcp/server.py`):

```python
     fields = {
         "title": title,
+        "notes": notes,
         "scope": ItemScope(scope),
```

`ItemCreate` inherits `notes` from `ItemBase` (`api/schemas.py`), so no schema change was needed.
`pa_create_calendar_event` already passed `notes` correctly and is unaffected.

### Deploy

The image bakes the source (`COPY backend/src /app/src`), so a rebuild was required.

```
docker build -f infra/Dockerfile.api \
  --build-arg PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.12-slim \
  -t personal-affairs-api:20261102-notes-fix .
docker compose -p personal-affairs -f infra/docker-compose.server.yml up -d --no-deps mcp
```

Only `personal-affairs-mcp-1` was recreated. `api`, `worker`, `webhook` still run
`personal-affairs-api:20261101-final`; the next full `deploy_to_server.sh` run will align all four
on a fresh tag.

**Build note:** the Dockerfile default `PYTHON_IMAGE=python:3.12-slim` resolves through Docker Hub,
which times out from this host (`auth.docker.io … i/o timeout`). Always pass
`PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.12-slim`, as `deploy_to_server.sh` already does.

### Verification

| Check | Result |
|---|---|
| Image contains the change | `inspect.getsource(pa_create_item)` inside the image shows `"notes": notes` |
| MCP container | `Up`, image `20261102-notes-fix`, listening on `127.0.0.1:18099` |
| Create with notes | Returned `notes` in the payload |
| Database truth | `notes IS NULL = false`, `length(notes) = 30`, `version = 1` |
| Re-read via `pa_get_item` | `notes` returned from a fresh read, not request echo |
| Cleanup | test item `cancelled`, briefing back to all-zero |

Rollback: previous file preserved at
`/home/jkiter/backups/eventflowos/patches/server.py.bak-20261102-102122`;
fallback image is `personal-affairs-api:20261101-final`.

Still open: agent-originated writes are attributed to `human` (`created_by_actor` /
`updated_by_actor`), and PAT scopes remain unenforced on the MCP surface.

## Fix — agent writes now carry a separate identity (2026-11-02)

### Design

Two layers, because "it was an agent" and "which agent" are different questions:

| Field | Value | Purpose |
|---|---|---|
| `created_by_actor` / `updated_by_actor` | `agent` | Matches the existing `ActorType` enum (`human` / `agent` / `system`); filterable |
| `source_context` | `{"surface": "mcp", "agent_token": "<PAT name>"}` | Names the token that made the call, so multiple agents stay distinguishable |

`ActorType.AGENT` already existed and `AgentProposalService` already wrote `agent`; the MCP surface
simply never passed it, so every MCP-originated row fell back to the `human` default.

### Changes

1. `storage/repositories/tokens.py` — `get_by_token()` now also selects `t.name AS token_name`.
   The column is additive; the REST auth path ignores it.
2. `mcp/server.py`:
   - `_AGENT_ACTOR = "agent"` and a `ContextVar` holding the resolved token name.
   - `_user_id()` resolves `(user_id, token_name)` in the single query it already ran, then stores
     the name in the context var — no extra round trip.
   - `_agent_source()` builds the provenance dict.
   - Wired into the four write tools: `pa_create_item`, `pa_create_calendar_event`
     (`created_by_actor` + `source_context`), `pa_update_item`, `pa_complete_item`
     (`updated_by_actor`).

REST routes deliberately untouched: they never pass an actor, so session-authenticated writes keep
defaulting to `human`.

### Verification

| Check | Result |
|---|---|
| MCP create | `created_by_actor: agent`, `source_context: {"surface":"mcp","agent_token":"workbuddy-mcp"}` |
| MCP update | `updated_by_actor: agent`, `version` 1 → 2 |
| Database truth | row shows `agent` / `agent` / provenance jsonb, not just an API echo |
| Historical rows | 93 × `human` unchanged; the test row was the only `agent` |
| REST path | routes do not pass an actor → still `human` (verified by inspection) |
| Cleanup | test row `cancelled` |

Deployed as `personal-affairs-api:20261102-agent-actor`, mcp container only.
Rollback: `server.py.bak-20261102-110441` / `tokens.py.bak-20261102-110441` under
`/home/jkiter/backups/eventflowos/patches/`.

### Still open

- `activity_events` records no actor at all — the audit trail cannot answer "who changed this"
  independently of the item row. Fixing it means threading the actor into the `activity.record`
  calls in the service layer, which the REST path shares.
- PAT scopes are still not enforced on the MCP surface (unchanged).
