# EventFlowOS 开发说明（Handoff）

> 面向接手这个仓库的开发者或 agent。
> 写作时间：2026-11-02。代码基线：`HEAD = 6670222`（`docs(deploy): document event context and fix compose project`）
> **加上 2026-11-02 到 11-03 这一批已上线验证并已提交的改动**（当前线上镜像 `20261102232030`），逐条清单见 13.6。
>
> 本文只讲「怎么在这个代码库里干活」。产品边界、需求清单、部署安全清单分别见
> `docs/development-status.md`、`docs/development-requirements.md`、`docs/deployment.md`。
> 与 WorkBuddy 的 MCP 接入与验收记录见 `docs/workbuddy-handoff.md`。

---

## 0. 先读这三段

1. **这是一个单用户、自托管系统。** 没有租户、没有注册、没有计费。`users` 表里通常只有一行，
   bootstrap 出来的那个账号。任何"为多租户考虑"的设计都是超纲。
2. **它是 5 个常驻进程，不是一个 web 应用。** api、mcp、web（nginx）、reminder worker、webhook worker
   各自独立运行，靠同一个 Postgres 通信。这一点决定了它没法塞进 serverless 平台（见 `docs/workbuddy-handoff.md` 的结论）。
3. **迁移是全量重放的。** 每次部署都会把 `backend/migrations/*.sql` 从 001 到 028 全部重新执行一遍，
   没有版本门控。所以**每个迁移文件必须幂等**。这条不是风格建议，是硬约束。

---

## 1. 系统全景

### 1.1 进程与端口

| 进程 | 启动命令 | 监听 | 职责 |
|---|---|---|---|
| api | `personal-affairs-api`（uvicorn） | `127.0.0.1:18098` | REST `/api/v1/*`，会话与 PAT 认证，所有业务写操作 |
| mcp | `personal-affairs-mcp` | `127.0.0.1:18099` | MCP Streamable HTTP `/mcp`，32 个 `pa_*` 工具 |
| web | nginx（`personal-affairs-web` 镜像） | `0.0.0.0:18110` | 托管前端静态产物；反代 `/api/` → 18098、`/mcp` → 18099 |
| worker | `personal-affairs-worker` | 无端口 | 轮询 `reminders`，到点投递通知，写 `reminder_deliveries` |
| webhook | `personal-affairs-webhook-worker` | 无端口 | 轮询 `event_outbox`，向外部订阅者投递事件 |

生产编排：`infra/docker-compose.server.yml`，全部 `network_mode: host`，
所以端口就是宿主机端口，容器之间不经过 docker 网络。

**线上镜像快照**（2026-11-03 10:55 核对，见 12.2）：

| 容器 | 镜像 |
|---|---|
| 全部 5 个 | `personal-affairs-api:20261102232030` / `personal-affairs-web:20261102232030` |

此前为了快速验证曾只重建单个容器（mcp 跑过 `20261102-agent-actor` 等临时 tag）。
自 2026-11-02 12:39 起改为每次完整部署，四个后端服务 + web 始终对齐到同一 tag；
**换 tag 后记得回来改这三处提示**（本节、第 5 节镜像说明、附录回滚示例）。

### 1.2 公网链路

```
公网 ──HTTPS──▶ Cloudflare 边缘 ──(出站 Tunnel)──▶ cloudflared（宿主机 systemd）
                                                        │
                                            127.0.0.1:18110  nginx
                                                        ├── /         → frontend/dist
                                                        ├── /api/     → 127.0.0.1:18098
                                                        └── /mcp      → 127.0.0.1:18099
```

公网域名 `tag.eventflowos.com`，Cloudflare Tunnel 为 token 托管模式（ingress 规则在 Cloudflare 面板，
仓库里看不到）。宿主机不开任何入站端口。

**关键设计**：web 和 api 同域名，所以 session cookie 可以 `samesite=lax`、CSP 可以 `connect-src 'self'`。
任何把它拆成两个域名的改动，都会连带要求改 CORS、CSP、cookie 三处——目前全仓库**没有 CORSMiddleware**。

### 1.3 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.12、FastAPI、psycopg 3（同步 + `ConnectionPool`）、pydantic-settings、uv 管理依赖 |
| 数据库 | PostgreSQL（扩展：`pgcrypto`、`citext`），单 schema `personal_affairs` |
| 前端 | React + TypeScript + Vite，npm |
| MCP | `mcp` Python SDK，Streamable HTTP 传输 |
| 部署 | Docker 多阶段构建 + docker compose + nginx |

包名与镜像名仍是 `personal-affairs` / `PERSONAL_AFFAIRS_*`，这是历史遗留，**刻意保持不变**（见 `development-status.md` 的兼容边界）。

---

## 2. 上手：把本地环境跑起来

### 2.1 前置

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- 一个能连的 PostgreSQL（本地 docker 起一个就够）

### 2.2 方式 A：整套容器（推荐，最接近生产）

```bash
cd /path/to/eventflowos
docker compose -f infra/docker-compose.dev.yml up --build
```

映射关系（宿主 → 容器）：

| 服务 | 地址 |
|---|---|
| Web | `127.0.0.1:18110` → 容器 80 |
| API | `127.0.0.1:18098` → 容器 **8080** |
| PostgreSQL | `127.0.0.1:15444` → 容器 5432 |

### 2.3 方式 B：本地直跑（改后端最快）

```bash
# 1. 起数据库
docker run -d --name pa-pg -p 127.0.0.1:15444:5432 \
  -e POSTGRES_USER=personal_affairs -e POSTGRES_PASSWORD=personal_affairs \
  -e POSTGRES_DB=personal_affairs postgres:16

# 2. 装依赖 + 迁移 + 起 API
cd backend
uv sync --all-extras --locked
uv run personal-affairs-migrate
uv run personal-affairs-api          # 监听 0.0.0.0:8080

# 3. 前端（另开一个终端）
npm ci --prefix frontend
npm run dev --prefix frontend
```

### 2.4 两个必知的端口陷阱

1. **`personal-affairs-api` 直跑时监听的是 8080，不是 18098。** 18098 是生产 compose 里
   `uvicorn --port 18098` 显式指定的。`uvicorn.run()` 在 `api/app.py` 里写死 `port=8080`。
2. **`frontend/vite.config.ts` 的 dev proxy 指向 `127.0.0.1:8080`。** 如果你在本地用
   18098 起 API（比如手动 `uvicorn --port 18098`），开发服务器会 502，需要改这一行或加 `--port 8080`。

### 2.5 首次登录

`PERSONAL_AFFAIRS_BOOTSTRAP_USERNAME` / `PERSONAL_AFFAIRS_BOOTSTRAP_PASSWORD` 只在库里没有用户时生效，
首次启动会创建账号。生产库已有账号，这两个变量改了不起作用。

### 2.6 确认跑通了

```bash
curl -s http://127.0.0.1:18098/api/v1/health     # {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18110/
```

---

## 3. 代码地图

### 3.1 后端分层（`backend/src/personal_affairs/`）

依赖方向严格单向：`api` / `mcp` / `workers` → `application` → `domain` + `storage`。
`domain` 不 import 任何具体实现。

| 目录 | 文件数 | 职责 | 改动频率 |
|---|---|---|---|
| `api/app.py` | — | 应用装配、中间件、路由注册、`main()` | 低 |
| `api/routes/` | 21 | HTTP 端点，只做参数解析 → 调 application → 转 schema | **中高** |
| `api/dependencies.py` | — | `db_conn`、`current_session`（cookie/PAT 双通道）、`require_csrf`、`if_match_version` | 低（改动风险高） |
| `api/middleware.py` | — | TrustedHost、限流、请求上下文 | 低 |
| `api/schemas.py` | — | 全部 Pydantic 请求/响应模型 | 中 |
| `application/` | 17 | 业务用例，事务边界在这里，**业务规则写这一层** | **高** |
| `domain/` | 5 | 枚举、实体、领域错误、纯策略函数（`policies.py`、`reminder_state.py`） | 中 |
| `storage/repositories/` | 18 | 每个聚合一个仓储，裸 SQL（psycopg，`dict_row`） | 中高 |
| `storage/database.py` | — | `ConnectionPool` 单例 + `connection()` 上下文管理器 | 低 |
| `storage/migrations.py` | — | 迁移执行器（全量重放，见第 5 节） | 低 |
| `workers/` | 2 | reminder / webhook 两个轮询循环 | 中 |
| `mcp/server.py` | — | MCP 服务 + 32 个工具 + PAT 校验 + 身份归属 | **高** |
| `notifications/adapters.py` | — | 通知渠道适配（`in_app` / `feishu` / `ntfy`） | 低 |

### 3.2 前端（`frontend/src/`）

| 目录 | 职责 |
|---|---|
| `api/client.ts` | 单一 API 客户端：全部 TypeScript 类型定义 + fetch 封装 + CSRF 头处理 |
| `app/` | 路由与布局 |
| `pages/` | 9 个页面：`TodayPage`、`InboxPage`、`WorkItemsPage`、`PersonalItemsPage`、`ProjectsPage`、`CalendarPage`、`ReviewPage`、`TagsPage`、`SettingsPage` |
| `components/` | 复用组件 |
| `hooks/` | 数据获取与交互 hook |
| `styles/` | CSS |

类型只在 `client.ts` 里定义一次，页面不重复声明。改 API 契约时先改这里。

### 3.3 仓库其他目录

- `infra/` — `Dockerfile.api`、`Dockerfile.web`、`docker-compose.{dev,server}.yml`、`nginx.server.conf`、`deploy_to_server.sh`、`.env.example`
- `openapi/` — OpenAPI 契约快照，改接口后需要同步
- `docs/` — 本文及其他文档
- `backend/migrations/` — 27 个 SQL 迁移

---

## 4. 两条请求链路

### 4.1 REST 写请求（浏览器）

```
浏览器
  │  POST /api/v1/items  + Cookie: pa_session + X-CSRF-Token
  ▼
nginx (18110)  ── CSP/安全头，限流（login/token/webhook 三个端点单独限流）
  ▼
FastAPI (18098)
  ├─ current_session：先查 cookie session，失败再试 Bearer PAT
  ├─ require_csrf：cookie 走 CSRF 校验；PAT 走 write scope 校验
  ├─ 路由函数 → ItemService（application 层）
  ├─ ItemService → ItemsRepository（裸 SQL）+ ActivityRepository（写 activity_events）
  └─ 返回 schema，db_conn 依赖负责 commit / rollback
```

事务边界在 `api/dependencies.py:db_conn()`：正常结束 commit，异常 rollback 后抛出。
**不要在 route 或 repository 里自己 commit。**

### 4.2 MCP 工具调用（agent）

```
agent（WorkBuddy 等）
  │  POST /mcp  + Authorization: Bearer pa_xxx
  ▼
nginx → 127.0.0.1:18099
  ▼
mcp/server.py
  ├─ _PersonalAccessTokenVerifier：校验 PAT，返回 AccessToken(scopes=[...])
  ├─ _user_id()：用同一 token 查库解析 (user_id, token_name)，token_name 存进 ContextVar
  ├─ 工具函数 pa_xxx()
  └─ 直接调 application 层的 service（与 REST 共用同一套 service）
```

MCP 工具**绕过 FastAPI 的依赖注入**，自己建连接、自己 commit。所以：
REST 侧的任何鉴权/审计逻辑，在 MCP 侧不会自动生效，需要显式补。这一点踩过坑（见 13.6），
所以现在 MCP 侧有一套平行的 `_user_id(require_write=...)` + `_agent_source()` 实现。

---

## 5. 数据层

### 5.1 Schema 与表

单 schema `personal_affairs`，34 张表（`public` 下没有表）。按用途分组：

| 分组 | 表 |
|---|---|
| 身份 | `users`、`sessions`、`personal_access_tokens` |
| 核心 | `items`、`item_tags`、`item_people`、`item_relations`、`projects`、`project_groups`、`milestones`、`project_updates`、`tags`、`people` |
| 时间 | `reminders`、`reminder_deliveries`、`push_subscriptions`、`digest_log` |
| Agent | `agent_proposals`、`agent_ingest_events`、`create_requests`（幂等键）、`event_outbox`、`write_targets` |
| 集成 | `external_bindings`、`external_profiles`、`llm_bindings`、`llm_profiles`、`webhook_subscriptions` |
| 其他 | `activity_events`、`user_preferences`、`saved_views`、`focus_sessions`、`habit_checkins`、`worker_heartbeats`、`schema_migrations` |

### 5.2 迁移机制（重要）

`storage/migrations.py` 现在是**带版本门控**的（2026-11-02 改）：

```python
cur.execute("SELECT to_regclass('personal_affairs.schema_migrations') IS NOT NULL")
tracking_exists = ...                      # 表不存在 = 全新库
for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
    if tracking_exists and 已登记(version):
        continue                           # 跳过已应用的
    cur.execute(path.read_text())
    cur.execute("INSERT INTO ...schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING")
    tracking_exists = True
```

`version` 取文件名去扩展名（`001_initial`）。有对应测试：`backend/tests/test_migrations.py`
（覆盖"记录并跳过"与"补齐历史缺口"两种场景）。

**但幂等仍然是硬约束，不能因为有了门控就放松。** 原因有两个：

1. **首次跑新执行器的库会全量重放一次。** 老版本只执行 SQL、不写登记表，
   所以升级后第一次运行会认为"一条都没应用过"，把全部迁移重跑一遍来补登记。
   本项目生产库已经走过这一步（现在 28 条记录 / 28 个文件，一一对应），但任何从旧版本升级的环境都会遇到。
2. **登记表被清空或重建时同样退化。** 门控只是性能与安全网，不是幂等性的替代品。

由此仍有四条铁律：

1. **新迁移必须幂等。** 用 `CREATE TABLE IF NOT EXISTS`、`ADD COLUMN IF NOT EXISTS`、
   `CREATE INDEX IF NOT EXISTS`、`CREATE SCHEMA IF NOT EXISTS`。当前 28 个文件 100% 遵守。
2. **不要写 `DO $$ ... $$` 之类的块。** 现在一个都没有（0/28），保持这样最省事。
3. **不要修改已上线的迁移文件。** 改了不会重放（有门控），但会让"文件内容"和"生产库实际状态"
   悄悄分叉，且新环境会跑出不同结果。要改结构，新增文件。
4. **编号缺口不代表可以随便补。** 当前序列缺 `027`（026 之后直接 028、029）。按文件名字典序执行，
   缺口本身无害；但如果补一个 `027_xxx.sql`，它会排在 028 **之前**执行——
   若它依赖 028 引入的列，就会在已有库上失败。补缺口前先确认依赖方向。

新增迁移的流程：

```bash
# 1. 取当前最大编号 +1（注意有没有缺口，见铁律 4）
ls backend/migrations/*.sql | tail -1
# 2. 写幂等 SQL
# 3. 跑两遍：第一遍执行，第二遍应输出 0 条 applied
./.venv/bin/python -m personal_affairs.storage.migrations
./.venv/bin/python -m personal_affairs.storage.migrations
```

### 5.3 已清理：5 张僵尸表与 5 条孤儿登记（2026-11-02）

历史上生产库里有 5 张表**仓库中没有任何迁移创建它们**：

```
external_bindings  external_profiles  llm_bindings  llm_profiles  write_targets
```

它们来自早期"agent native handoff"那一版设计（两套并行的 profile/binding 加一个 write_targets），
后来 `028_integration_settings` 把活下来的配置项搬到了 `user_preferences` 上，这 5 张表就再没被写过：
建表至今**全部 0 行**，`backend/src` 与 `frontend/src` 里引用数 **0**。
对应的迁移文件也早从仓库删了，但 `schema_migrations` 里留着 5 条记录
（`023_item_history_indexes`、`024_write_targets`、`025_llm_profiles`、`026_external_profiles`、
`027_event_location`），形成"32 条记录 / 27 个文件"的错位。

`029_drop_legacy_tables.sql` 一并处理掉：先删子表（`*_bindings` 有外键指向 `*_profiles`，
所以不用 `CASCADE`），再删父表，最后 `DELETE` 那 5 条孤儿登记。现在记录数 = 文件数。

**决策依据（已实测）**：起空库跑全部迁移得到 29 张表；与生产库比对，差的 70 个列全部落在这 5 张表内，
**核心业务表（items / reminders / projects / people / …）表与列完全一致**。
也就是说这 5 张表对 schema 一致性没有任何贡献，删掉后空库与生产库仍然同构。
删除前做了 `pg_dump -n personal_affairs -Fc` 全量备份（`/srv/backups/personal_affairs_pre029_*.dump`）。

**结论**：不再有偏差，空库与生产库可以直接比对。以后不要在迁移目录外手工建表。


### 5.4 核心约定

| 约定 | 实现位置 | 说明 |
|---|---|---|
| 乐观锁 | `items.version`、`If-Match: v3` / MCP `if_match` | 版本不匹配返回 `Item version is stale`，不写入 |
| 幂等创建 | `create_requests` 表 + `client_request_id` | 同一 id 重复提交返回同一条，`version` 不变 |
| 软删除 | `items.deleted_at`、`cancelled_at` | MCP 没有"删除事项"工具，只有置 `cancelled` |
| 时间 | 全部 `timestamptz`，业务时区 `Asia/Shanghai` | API 用 UTC 字符串，展示层转本地 |
| 枚举 | `domain/enums.py`（StrEnum） | 前端同名类型在 `client.ts` 手抄，**不是自动生成** |

---

## 6. 认证与授权

### 6.1 双通道

`api/dependencies.py:current_session()` 按顺序尝试：

1. **Cookie session** — `pa_session`，查 `sessions` 表。返回 `auth_method="cookie"`。
2. **Bearer PAT** — `Authorization: Bearer pa_xxx`，查 `personal_access_tokens`。
   返回 `auth_method="pat"` 和 `pat_scopes`。

都失败 → `401 AUTH_REQUIRED`。

### 6.2 写操作门禁（`require_csrf`）

这个函数名字有误导性，它同时守两条路：

| 调用方 | 校验内容 | 失败 |
|---|---|---|
| `auth_method == "cookie"` | `X-CSRF-Token` 必须与 session 里的 `csrf_token` 一致 | `403 CSRF_REQUIRED` |
| `auth_method == "pat"` | `pat_scopes` 必须含 `write` | `403 PAT_SCOPE_FORBIDDEN` |

**重点：REST 层是强制 scope 的。** 一个 `scopes:["read"]` 的 PAT 调 `POST /api/v1/items` 会被 403 拦住。

### 6.3 MCP 层的 scope 门禁（独立实现，已对齐）

MCP 工具不走 FastAPI 依赖注入，所以 `require_csrf` 对它不生效。MCP 有一套自己的等价实现：

```python
async def _user_id(*, require_write: bool) -> UUID:
    # 一次查询解析出 (user_id, token_name, scopes)
    if require_write and "write" not in scopes:
        raise DomainError(ErrorCode.PAT_SCOPE_FORBIDDEN, "This personal access token lacks the write scope.", 403)
```

所有工具都经 `_authed(fn, require_write=...)` 进入，15 个写工具全部标 `require_write=True`，
14 个读工具标 `False`，1 个纯解析工具（`pa_parse_meeting_invite`，不碰数据库）不经过 `_authed`。

实测确认（2026-11-02）：用 `scopes:["read"]` 的 PAT 调 `pa_create_item` 返回
`isError: true` + "lacks the write scope"，且**库内无写入**。

**新增写工具时，`require_write=True` 是必须的**，漏标就等于开了一个写口子。

### 6.4 agent 身份归属

写操作有两个 actor 字段（`items.created_by_actor` / `updated_by_actor`），取值见 `ActorType`：
`human` / `agent` / `system`。

- REST 路由**不传** actor → 落库为默认值 `human`。
- MCP 的四个写工具（`pa_create_item`、`pa_create_calendar_event`、`pa_update_item`、`pa_complete_item`）
  显式传 `actor = "agent"`，并把令牌名写进 `source_context`：

```json
{"surface": "mcp", "agent_token": "workbuddy-mcp"}
```

`source_context` 是 `items` 上的 jsonb 列，用来区分"哪个 agent"。
令牌名来自 `TokensRepository.get_by_token()` 多取的一列 `t.name`，经 `ContextVar` 传递，不额外查库。

**注意**：`activity_events` 表没有 actor 列，审计流水只能看到"改了哪个字段"，看不到"谁改的"。

---

## 7. MCP 层

### 7.1 服务配置

```python
_MCP_HOST = os.environ.get("PERSONAL_AFFAIRS_MCP_HOST", "127.0.0.1")
_MCP_PORT = int(os.environ.get("PERSONAL_AFFAIRS_MCP_PORT", "18099"))
_MCP_ISSUER_URL = ...      # 默认 https://<ALLOWED_HOSTS 第一个>
_MCP_RESOURCE_URL = ...    # 默认 {issuer}/mcp
```

传输方式由 `PERSONAL_AFFAIRS_MCP_TRANSPORT=streamable-http` 决定（compose 里已设）。
stdio 模式下改用 `PERSONAL_AFFAIRS_MCP_TOKEN` 环境变量鉴权。

未认证请求返回 `401` + `WWW-Authenticate: Bearer error="invalid_token"` +
`resource_metadata`，并暴露 `/.well-known/oauth-protected-resource/mcp`。这是 MCP 规范要求，不要动。

Codex CLI 可用 `codex mcp add eventflowos --url https://<host>/mcp --bearer-token-env-var PERSONAL_AFFAIRS_MCP_TOKEN` 登记连接。PAT 只通过启动 Codex 时的环境变量提供，不写入 MCP 配置；未设置该变量时连接不能完成 Bearer 认证。

### 7.2 32 个工具

| 类别 | 工具 |
|---|---|
| 事项（7） | `pa_list_items`、`pa_get_item`、`pa_create_item`、`pa_update_item`、`pa_complete_item`、`pa_set_item_relations`、`pa_get_project_context` |
| 建议流（3） | `pa_propose_item`、`pa_approve_proposal`、`pa_reject_proposal` |
| 提醒（8） | `pa_set_reminder`、`pa_get_reminder`、`pa_delete_reminder`、`pa_list_deliveries`、`pa_ack_delivery`、`pa_snooze_delivery`、`pa_retry_delivery`、`pa_reminder_health` |
| 调度（6） | `pa_assess_schedule_feasibility`、`pa_prepare_event`、`pa_find_free_slots`、`pa_get_schedule_summary`、`pa_list_calendar`、`pa_create_calendar_event` |
| 人员（3） | `pa_list_people`、`pa_create_person`、`pa_update_person` |
| 解析与其他（5） | `pa_parse_meeting_invite`、`pa_parse_meeting_input`、`pa_resolve_offline_location`、`pa_get_executive_briefing`、`pa_get_channels` |

`pa_prepare_event` 用于把 Agent 从聊天记录提取的结构化候选事件做地点解析、重叠检查和公交/驾车路线预检；`pa_find_free_slots` 支持线上/线下和地点；`pa_get_schedule_summary` 提供日期范围内的基础统计。交通预计时间按路线 ETA 的 1.5 倍预留。`pa_create_calendar_event` 会在写入前重新预检，遇到重叠、两种路线均不可行或地点歧义时不会静默创建；紧张或路线未知需要 `confirm_schedule_risks=true`。

**没有删除事项的工具。** 清理测试数据只能 `pa_update_item(status="cancelled")`。

### 7.3 新增一个 MCP 工具

```python
@mcp.tool()
async def pa_do_something(item_id: str, note: str | None = None) -> dict:
    """一句话说明用途（会作为工具描述暴露给 agent，写清楚）。"""

    def _run(conn, uid):
        item, _ = ItemService(ItemsRepository(conn), ActivityRepository(conn)).do(
            uid, UUID(item_id), note,
            updated_by_actor=_AGENT_ACTOR,        # 写操作才需要
        )
        return item

    return await _authed(_run, require_write=True)   # 写=True，读=False
```

`_authed` 负责三件事：解析身份、校验 scope、把同步 DB 调用放到线程池里跑并管理事务。
**不要自己 `with connection()` 再手写 commit** —— 只有 `pa_reminder_health` 这种全局健康检查
是例外（它不涉及用户数据）。

四条纪律：

1. **写工具必须 `require_write=True`。** 漏标 = 只读令牌也能写，等于白加了一层安全网。
   写完后必须把工具名加进 `test_mcp_contract.py` 的 `WRITE_TOOLS` 表，
   否则 `test_mcp_tool_surface_is_fully_classified` 会因为"服务端有未分类工具"直接失败。
2. **写工具必须传 actor。** `created_by_actor=_AGENT_ACTOR` 或 `updated_by_actor=_AGENT_ACTOR`，
   并带 `source_context=_agent_source()`。漏了就会落成 `human`。
3. **每加一个参数，都要确认它进了下游的 `fields` / `patch_fields` 字典。**
   这里出过一个真实 bug：`pa_create_item` 收了 `notes` 参数但没放进 `fields`，静默丢弃（见 13.6）。
   同类问题现在的护栏是 `test_mcp_create_item_forwards_notes_and_agent_identity`，
   新增写工具时建议照抄一个"参数是否到达 request 对象"的断言。
4. **不要在工具里自己写 SQL。** 走 `application/` 的 service，和 REST 共用一套业务规则。


### 7.4 客户端侧已知要求（WorkBuddy）

`~/.workbuddy/mcp.json` 里 `type` 必须是 `"http"`（不是 `streamableHttp`），
且该文件只在应用启动时读取一次，改完要重启应用。完整验收记录见 `docs/workbuddy-handoff.md`。

---

## 8. 后台任务

### 8.1 两个 worker 形状相同

| | reminder | webhook |
|---|---|---|
| 入口 | `workers/reminder_worker.py` | `workers/webhook_worker.py` |
| 轮询间隔 | `reminder_poll_seconds`（5s） | `webhook_poll_seconds`（5s） |
| 批大小 | `reminder_batch_size`（20） | `webhook_batch_size`（20） |
| 租约 | `reminder_lease_seconds`（60） | `webhook_lease_seconds`（60） |
| 最大尝试 | `reminder_max_attempts`（6） | `webhook_max_attempts`（6） |

租约靠 `FOR UPDATE SKIP LOCKED` 取活，多实例安全。心跳写 `worker_heartbeats`，
`pa_reminder_health` 工具的 `worker_seen_recently` 就是读这张表。

### 8.2 排障顺序

"到点不响"按这个顺序查，别跳步：

```bash
# 1. worker 活着吗（最常见的失败）
docker ps --filter name=personal-affairs --format '{{.Names}}\t{{.Status}}'
docker logs personal-affairs-worker-1 --tail 50

# 2. 心跳新不新
docker exec -i <pg> psql -U <user> -d personal_affairs -c \
  "SELECT * FROM personal_affairs.worker_heartbeats ORDER BY seen_at DESC LIMIT 3;"

# 3. 提醒是否到期未投递
SELECT r.id, r.next_run_at, d.status, d.attempt_count
FROM personal_affairs.reminders r
LEFT JOIN personal_affairs.reminder_deliveries d ON d.reminder_id = r.id
WHERE r.active AND r.next_run_at < now() - interval '2 minutes';

# 4. 投递终态
SELECT status, channel, attempt_count, error_code, delivered_at
FROM personal_affairs.reminder_deliveries ORDER BY created_at DESC LIMIT 10;
```

历史上出过一次 `psycopg_pool.PoolTimeout: couldn't get a connection after 30.00 sec`，
worker 退出后没被拉起，提醒停摆一周。现在有三层防护（2026-11-02 起）：

1. **单次迭代异常不再杀死进程。** `run_forever()` 的主循环包了 `try/except`：
   打日志 `Reminder worker iteration failed; retrying` + `close_pool()` 重建连接池，
   然后照常 sleep 进入下一轮。数据库重启、网络抖动都不再需要人工重建容器。
2. **连接池参数显式收敛。** compose 里每个服务都设了
   `DATABASE_MAX_SIZE=10` / `POOL_TIMEOUT=10` / `RECONNECT_TIMEOUT=60`。
3. **启动顺序受控。** worker / webhook 依赖 `api: condition: service_healthy`，避免 api 尚未就绪时抢连接。

`restart: unless-stopped` 只在进程非 0 退出时重启，所以第 1 条才是根本——进程不退出，就不依赖重启策略。


### 8.3 通知渠道

`DeliveryChannel` 只有三个值：`in_app`、`feishu`、`ntfy`。
`in_app` 不需要外部依赖（直接写投递记录，前端 briefing 读未读）。
`feishu` / `ntfy` 走 `notifications/adapters.py`，超时由 `notification_provider_timeout_seconds`（8s）控制。

---

## 9. 前端

### 9.1 构建与产物

`infra/Dockerfile.web` 是 node 构建 + nginx 运行两阶段，产物在 `/usr/share/nginx/html`。
`frontend/dist` 是构建产物，不要手改，也不要提交改动（除非明确要发快照）。

### 9.2 CSP 是硬约束

`nginx.server.conf` 里写死：

```
connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:
```

意味着：不能引外部 CDN、不能内联 `<script>`、不能 fetch 第三方域名。
要加外部资源，先改 CSP 再做，否则线上静默失败（控制台报 CSP 违规，页面功能不报错）。

### 9.3 与后端契约

类型手写在 `api/client.ts`（不生成）。改 schema 时**两边都要改**：
`api/schemas.py` + `frontend/src/api/client.ts`，然后同步 `openapi/` 快照。

---

## 10. 配置

所有配置前缀 `PERSONAL_AFFAIRS_`，定义在 `config.py`（`pydantic-settings`，读环境变量）。

### 10.1 必须关注的

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql://...@127.0.0.1:15444/personal_affairs` | 唯一数据源 |
| `APP_ENV` | `development` | `production` 时收紧 cookie（secure）与文档暴露 |
| `ALLOWED_HOSTS` | 空 | **TrustedHost 白名单，逗号分隔。漏了域名会直接 400** |
| `BOOTSTRAP_USERNAME` / `_PASSWORD` | 空 | 仅首次建号生效 |
| `DEFAULT_TIMEZONE` | `Asia/Shanghai` | briefing、日程、提醒的基准时区 |
| `API_DOCS_ENABLED` | 跟随 APP_ENV | 生产默认关 `/docs` |
| `RATE_LIMIT_ENABLED` | `true` | 配合 nginx 三层限流 |
| `WEBHOOK_ALLOW_PRIVATE_URLS` | `false` | SSRF 防护，别随手开 |

### 10.2 连接池（曾有事故，别乱改）

`DATABASE_MIN_SIZE=1`、`DATABASE_MAX_SIZE=10`（compose 显式设为 10）、
`DATABASE_POOL_TIMEOUT_SECONDS=10`、`DATABASE_RECONNECT_TIMEOUT_SECONDS=60`。

5 个进程共用同一个 Postgres，每个进程都有自己的池。**调大之前先算总连接数**：
`5 × max_size` 不能超过 PG 的 `max_connections`。

### 10.3 生产运行时配置在哪

不在仓库里。生产 env 文件是：

```
/srv/secrets/personal-affairs/runtime.env
```

compose 通过 `PERSONAL_AFFAIRS_RUNTIME_ENV_FILE` 引用它，该变量没设时 compose 会直接报错退出
（`${VAR:?set ...}`）。这是故意的，防止拿空配置启动。

---

## 11. 测试与质量门

```bash
cd backend
./.venv/bin/python -m pytest -q   # 17 个测试文件，当前 121 passed
uv run ruff check src tests
uv run pyright

npm test --prefix frontend
npm run lint --prefix frontend
npm audit --prefix frontend --audit-level=moderate
```

> 前端两条 `npm` 命令在本机跑不了（服务器没有 node），只在 Docker 构建阶段执行。
> 所以改前端后**必须走一次完整部署**才能确认类型通过。

有价值的测试文件（改对应模块时必跑）：

| 测试 | 覆盖 |
|---|---|
| `test_mcp_contract.py` | MCP 工具契约：32 个工具全量分类 + 逐个校验 `require_write` 字面值 + 只读令牌被拒 + `notes` 透传 + agent 身份 |
| `test_event_planning_service.py` | 邀约预检、全天冲突、交通 1.5 倍缓冲和会议空档 |
| `test_migrations.py` | 迁移门控：记录并跳过、补齐历史缺口 |
| `test_webhook_contract.py` | 出站 webhook 契约 |
| `test_api_smoke.py` | API 冒烟 |
| `test_idempotency.py` | `client_request_id` 幂等 |
| `test_rate_limit.py` | 限流 |
| `test_agent_proposal_service.py` | 建议流 |
| `test_schedule_feasibility.py` / `test_location_service.py` / `test_meeting_invite_parser.py` | 调度、地点、会议解析 |

迁移测试用的是 FakeConnection 打的桩，验证的是**控制流**（该跳过的跳过、该补登记的不漏），
不验证 SQL 能否跑通。所以加迁移时仍然要真跑两次 `personal-affairs-migrate`。


---

## 12. 构建与部署

### 12.1 标准部署

```bash
cd /home/jkiter/eventflowos
PERSONAL_AFFAIRS_RUNTIME_ENV_FILE=/srv/secrets/personal-affairs/runtime.env \
  bash infra/deploy_to_server.sh --confirm-production
```

脚本做的事（顺序固定）：

1. 无 `--confirm-production` 直接退出（防误触）
2. 校验 runtime env 可读
3. `docker compose config` 校验编排
4. build API 镜像 → tag `personal-affairs-api:<release_tag>`（默认 UTC 时间戳）
5. build Web 镜像 → tag `personal-affairs-web:<release_tag>`
6. **`docker run --rm ... personal-affairs-migrate`** ← 全量重放 27 个迁移
7. `docker compose up -d`

### 12.2 只改后端时的快速路径

```bash
docker build -f infra/Dockerfile.api \
  --build-arg PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.12-slim \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  -t personal-affairs-api:<tag> .

PERSONAL_AFFAIRS_RUNTIME_ENV_FILE=/srv/secrets/personal-affairs/runtime.env \
PERSONAL_AFFAIRS_API_IMAGE=personal-affairs-api:<tag> \
PERSONAL_AFFAIRS_WEB_IMAGE=personal-affairs-web:<既有 tag> \
  docker compose -p personal-affairs -f infra/docker-compose.server.yml up -d --no-deps mcp
```

`--no-deps` 只重建指定服务，其它容器不动。改 MCP 工具时这是最快的验证路径（约 10 秒）。

### 12.3 踩过的坑

| 坑 | 现象 | 处理 |
|---|---|---|
| Docker Hub 不可达 | `auth.docker.io ... i/o timeout` | `--build-arg PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.12-slim`（脚本已默认） |
| 镜像烤源码 | 改 `backend/src` 后容器内代码不变 | 必须重建镜像，没有源码挂载 |
| 构建期代理残留 | worker 通知被代理劫持 | Dockerfile 末尾显式 `ENV HTTP_PROXY=` 清空，别删这几行 |
| 镜像 tag 不一致 | 四个后端容器跑不同版本 | 用完整 `deploy_to_server.sh` 对齐；临时单容器部署要记下用了哪个 tag |

### 12.4 回滚

```bash
# 代码级
docker compose -p personal-affairs -f infra/docker-compose.server.yml \
  up -d --no-deps mcp   # 配合 PERSONAL_AFFAIRS_API_IMAGE=<上一个 tag>

# 文件级备份（这两天的补丁都留在）
ls /home/jkiter/backups/eventflowos/patches/
```

**数据库迁移没有自动回滚。** 迁移只做加法（`ADD COLUMN IF NOT EXISTS`），
但真要回滚 schema 只能手工写反向 SQL。部署前先 `pg_dump`：

```bash
docker exec <pg> pg_dump -U <user> -d personal_affairs -Fc > /backup/pa-$(date +%F).dump
```

当前库只有 11 MB，秒级完成，没有理由不做。

### 12.5 编排的环境变量契约

`docker-compose.server.yml` 依赖三个外部变量，缺一个就 `config` 失败：

| 变量 | 用途 |
|---|---|
| `PERSONAL_AFFAIRS_RUNTIME_ENV_FILE` | 必需，runtime env 路径 |
| `PERSONAL_AFFAIRS_API_IMAGE` | api / mcp / worker / webhook 四个服务共用 |
| `PERSONAL_AFFAIRS_WEB_IMAGE` | web 服务 |

---

## 13. 已知问题

按"该不该现在修"排序。每条都附了定位方式和影响面。

### 13.1 【审计 · 中】`activity_events` 没有 actor

审计流水只记录"哪个字段从什么改成什么"，不记录操作者。
所以 `items` 行上的 actor 只能回答"最后是谁碰的"，回答不了"这三次修改分别是谁"。

**修法**：给 `activity_events` 加 actor 列 + 把 actor 贯穿到 service 层所有 `activity.record` 调用。
REST 与 MCP 共用 service，两条路会一起变，改动面比 13.6 里那些都大。建议单独一轮做。

### 13.2 【安全 · 中高】bootstrap 口令强度无约束

`APP_ENV=production` 下 cookie 有 `secure`，但 bootstrap 口令没有任何长度/复杂度校验。
当前生产口令是 6 位纯数字，明文躺在 `/srv/secrets/personal-affairs/runtime.env` 里，
而服务已经通过 Cloudflare Tunnel 暴露到公网。

**建议**：换强口令（20 位随机），并在 bootstrap 路径加最小长度校验。改口令本身是运维动作，
加校验是代码动作，两件事分开做。

### 13.3 【行为 · 中】AMap 未启用时，线下事件一律要显式确认

`user_preferences.amap_enabled` 当前是 `false`（也没配 key）。`resolve_event_location`
在这种情况下返回 `{"status": "disabled"}`，`_mark_location_uncertainty` 随即把整体评估
改写成 `travel_unknown`；而 `pa_create_calendar_event` 对 `travel_unknown` 的处理是
**不给 `confirm_schedule_risks=true` 就不创建**。

实测（2026-11-03，走公网 MCP）：

```
pa_create_calendar_event(event_format="offline", location_name="上海中心大厦")
  → {"created": false, "requires_confirmation": true, "assessment": {"status": "travel_unknown"}}
  → 库内 0 写入
同一请求补 confirm_schedule_risks=true → 正常创建，schedule_assessment 一并返回
```

问题在于**"无法评估"被当成了"有风险"**：provider 没启用不是路程风险，却让所有带地点的
线下事件变成需要二次确认。任何没带这个新参数的 agent / 自动化，会静默拿到 `created:false`。

**两条路，选一条**：
- 运维：把 AMap key 配上并开启（settings → 集成），行为立刻符合设计；
- 代码：把"provider 未启用 / 路线不可得"从 `travel_unknown` 拆出来（例如 `not_assessed`），
  只影响提示不影响写入；真正需要拦的仍是 `conflict` / `travel_blocked` / `location_ambiguous`。

在此之前，写线下事件要么带地点坐标（`status: resolved`，走真实路线判断），
要么显式传 `confirm_schedule_risks=true`。

### 13.4 【运维 · 低】Cloudflare 拦截默认 Python UA

`User-Agent: Python-urllib/3.x` 请求 `/api/v1/auth/login` 会在边缘返回 `403`，
换成 `curl` 或浏览器 UA 就正常。任何脚本/agent 直连 REST API 都要显式设 UA。

### 13.5 【未验证】Cloudflare Access 策略

`tag.eventflowos.com` 目前**没有** Access 拦截（无 cookie 请求拿到的是应用自己的 401）。
如果将来给这个 hostname 加 Access 策略，MCP 的非浏览器客户端会被拦在门外，
届时需要配 service token（或在 MCP 专用 hostname 上单独放行）。改之前先确认 agent 侧能带 Access 头。

### 13.6 【已修 · 记录备查】

全部带防回归测试，不是一次性修补。

| 问题 | 修法 | 验证 / 防回归 |
|---|---|---|
| `pa_create_item` 静默丢弃 `notes`（参数收了但没进 `fields` 字典） | `fields` 里补一行 `"notes": notes` | 在线查库 `length(notes)=30`；`test_mcp_create_item_forwards_notes_and_agent_identity` |
| MCP 层不校验 PAT scope（只读令牌可写） | `_user_id(require_write=...)` + 15 个写工具标 `True` | 只读令牌调 `pa_create_item` → `isError`，库内 0 写入；15+14 个工具逐个断言 `require_write` 字面值 |
| agent 写入归属为 `human`，与人工无法区分 | `created_by_actor="agent"` + `source_context.agent_token` | 在线查库见 `agent` / jsonb provenance；`test_mcp_pat_write_scope_enforced` 断言令牌名进 contextvar |
| `run_migrations()` 全量重放、无版本门控 | 读 `schema_migrations` 跳过已应用 | 空库跑出全量 applied；第二次执行 0 条；`test_migrations.py` 两例 |
| 5 张僵尸表 + 5 条孤儿迁移登记 | `029_drop_legacy_tables.sql`：先删子表再删父表，并 `DELETE` 孤儿登记 | 迁移后 `schema_migrations` 记录数 = 文件数，5 张表已不存在，items 行数不变 |
| 前端生成的 MCP 片段缺 `"type": "http"` | `SettingsPage.tsx` 片段补该字段 | WorkBuddy 实测：不带 `type` 条目静默不加载 |
| 工作区 17 个改动未提交 | 按主题拆 commit 推 `origin/codex/eventflowos-development-status` | `git log --oneline` |

#### 13.6.1 测试面的改动（值得单独说明）

`test_mcp_contract.py` 原来只断言"工具名存在"，且只对 3 个 proposal 工具验过写权限。
现在改成**表驱动 + 静态校验**：

- 文件顶部三张常量表 `WRITE_TOOLS` / `READ_TOOLS` / `PURE_TOOLS` 是唯一事实来源；
- `test_mcp_tool_surface_is_fully_classified` 断言三张表的并集**等于**服务端实际工具集
  （多一个或少一个都失败），并锁住 15/14 的数量；
- `test_mcp_tool_declares_expected_scope` 对每个工具 `ast` 解析其源码，读 `_authed` / `_user_id`
  调用的 `require_write=` **字面值**，与所属表比对。忘标的写工具当场失败，不需要真连数据库；
- `test_mcp_pure_tool_never_authenticates` 保证 `pa_parse_meeting_invite` 不做任何鉴权。

这样新增工具时的流程是：写实现 → 往对应表里加名字 → 跑测试。忘了加名字，分类测试先红。


---

## 14. 约定与易踩坑

### 14.1 编码约定

- 后端分层不要越界：route 不写 SQL，repository 不写业务规则，domain 不 import 具体实现。
- 事务由 `db_conn()` / MCP 侧显式 `commit()` 管，route 和 repository 里不要 commit。
- 枚举改 `domain/enums.py` 后，同步 `frontend/src/api/client.ts`。
- 新增写操作时问自己三件事：要不要幂等键？要不要乐观锁？要不要记 actor？
- MCP 工具的描述字符串是给 agent 看的，写清楚"什么时候该用"，比写参数说明更有价值。

### 14.2 一批具体的小坑

| 坑 | 说明 |
|---|---|
| `all_day` 默认 `true` | `pa_create_item` 传 `due_at` 时必须显式 `all_day=false`，否则参数冲突 |
| MCP 无删除工具 | 清理数据用 `status="cancelled"` |
| `pa_list_items(status="planned")` 返回空 | 可能真的没有 planned 事项，不一定是 bug |
| `frontend/dist` 是产物 | 别手改，别当源码读 |
| `docs/workbuddy-handoff.md` 未提交 | 内容有效，但还没进 git |
| 迁移缺 027 | 字典序执行，缺口无害；补号前确认依赖（见 5.2） |
| `type` 必须是 `http` | WorkBuddy 的 `mcp.json`，写 `streamableHttp` 静默不生效 |
| 图片/字体不能外链 | CSP `img-src 'self' data:`、`font-src 'self'` |
| 生产 env 不在仓库 | `/srv/secrets/personal-affairs/runtime.env` |

---

## 15. 建议的下一步

2026-11-02 到 11-03 这一轮已经完成：迁移门控、MCP scope 校验 + agent 身份、worker 异常兜底、
镜像统一、僵尸表清理、MCP 片段补 `type`、事件预检 + 日程统计（32 工具）、全量改动提交（13.6）。
剩下的按投入产出排：

1. **决定 AMap 开关走哪条路**（13.3）。现在等于所有带地点的线下事件都要 `confirm_schedule_risks`，
   要么配 key，要么把"未启用/无法评估"从 `travel_unknown` 里拆出去。这是当前最影响日常使用的一条。
2. **bootstrap 换强口令 + 加长度校验**（13.2）。已经公网暴露，6 位数字，别拖。
3. **`activity_events` 补 actor**（13.1）。审计完整性，改动跨 service 层，单独一轮。
4. **给 MCP 写链路补集成测试**。现在写工具的 scope 是静态校验（`require_write` 字面值），
   真正打库的端到端只有手工验收记录（`docs/workbuddy-handoff.md`）。建议用一次性库做一条
   "建事项 → 挂提醒 → worker 投递 → 清理"的自动化用例。
5. **`worker_heartbeats` 按 PID 累积，已 106 行**。worker 每次重启新增一行、旧行不清理，
   看"心跳新不新"时要先取 `max(last_seen_at)`。顺手加个启动时清理旧 PID 的逻辑。
6. **确认 Cloudflare Access 边界**（13.5）。现在等于没有边缘鉴权，靠应用自身 401 + PAT。

---

## 附：一页速查

```bash
# 代码在哪
ssh home-server-ts
cd /home/jkiter/eventflowos

# 谁在跑
docker ps --filter name=personal-affairs --format '{{.Names}}\t{{.Status}}\t{{.Image}}'

# 健康
curl -s -H 'Host: 127.0.0.1' http://127.0.0.1:18098/api/v1/health

# 日志
docker logs personal-affairs-api-1 --tail 100
docker logs personal-affairs-worker-1 --tail 100

# 进数据库
docker exec -it 1Panel-postgresql-4GCF psql -U jkiter -d personal_affairs

# 改完后端后的最快验证
docker build -f infra/Dockerfile.api \
  --build-arg PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.12-slim \
  -t personal-affairs-api:trial . && \
PERSONAL_AFFAIRS_RUNTIME_ENV_FILE=/srv/secrets/personal-affairs/runtime.env \
PERSONAL_AFFAIRS_API_IMAGE=personal-affairs-api:trial \
PERSONAL_AFFAIRS_WEB_IMAGE=personal-affairs-web:20261102232030 \
  docker compose -p personal-affairs -f infra/docker-compose.server.yml up -d --no-deps mcp
```

注意：`WEB_IMAGE` 必须传当前在用的 tag（`docker ps` 里看 `personal-affairs-web-1`），
写成 `latest` 会把 nginx 换成不存在的版本。
