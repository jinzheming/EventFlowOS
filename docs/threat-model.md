# Threat Model

This threat model describes the current beta boundary for EventFlowOS as a single-user self-hosted application.

## Assets

- Personal tasks, work items, projects, calendar data, tags, people metadata, focus sessions, and habit history.
- Session cookies, CSRF tokens, personal access tokens, webhook signing secrets, push notification keys, and integration verification tokens.
- PostgreSQL data, backups, runtime `.env` files, and reverse proxy configuration.
- Agent-facing MCP access and agent proposal payloads.

## Trust Boundaries

- Browser to API: authenticated through HttpOnly session cookies plus CSRF on cookie-authenticated writes.
- Agent to API/MCP: authenticated through personal access tokens or a private MCP runtime boundary.
- API to PostgreSQL: trusted server-side connection; database URLs must stay outside git.
- API/worker to outbound webhooks: untrusted public internet destinations unless explicitly allowlisted.
- Optional Feishu and Tencent Meeting integrations: disabled by default and treated as external systems.
- Reverse proxy to containers: proxy configuration must preserve host validation, TLS termination, body limits, and rate limits.

## Primary Risks and Controls

- Session theft: HttpOnly cookies, conservative production docs defaults, and required operator-controlled TLS boundary.
- CSRF: cookie-authenticated write routes require `x-csrf-token`; PAT writes require explicit `write` scope.
- PAT misuse: tokens are scoped, can expire, and should be rotated if logs or clients are exposed.
- Webhook SSRF: subscription URLs are normalized, credentials/fragments are rejected, private/non-global resolved addresses are rejected by default, redirects are blocked, and destinations are revalidated before delivery.
- Webhook abuse: delivery has timeout, response body capture limit, retry/dead-letter state, signing secrets, and health visibility.
- MCP exposure: intended for loopback or trusted private network use; do not expose without an authenticated edge and rate limits.
- Integration spoofing: Feishu IM is disabled by default and must verify token/signature before accepting passive text events.
- Dependency compromise: CI runs dependency audits, CodeQL, Dependabot, and secret scanning.

## Non-Goals for v0.1.0-beta.1

- Multi-tenant isolation or organization-level authorization.
- Public self-service registration.
- Hosted SaaS operation.
- Cross-user data sharing.
- Reverse migrations for every schema change.

## Operator Responsibilities

- Keep runtime secrets and backups outside git.
- Enable branch protection, Dependabot alerts, secret scanning, push protection, and private vulnerability reporting on GitHub.
- Add edge rate limits for login, token creation, webhook creation, and any internet-facing expensive routes.
- Test restore from backup before relying on production data.
- Keep MCP and backend listeners private unless deliberately exposed behind a trusted access layer.
