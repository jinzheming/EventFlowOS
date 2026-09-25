# EventFlowOS 虚拟 Workspace 与时间线分析设计

> 状态：任务聚合模型与前后端方案草案（grill-with-doc 第 2 轮）  
> 日期：2026-09-21  
> 适用范围：`/home/jkiter/eventflowos` 个人事务管理版 EventFlowOS  ；不适用于旧的“事件链拆分”实验项目。

## 1. 一句话定义

Workspace 是一个**以任务（当前数据模型中的工作事项 `item`）为聚合单位的虚拟分析上下文**：它不复制任务或事件数据，只保存任务范围和过滤器；查询时把任务本身、任务活动、专注记录和相关 Agent 证据聚合起来，并把所属项目的更新/里程碑作为项目级上下文返回。

同一个项目可以直接视为一种内置的 Project Workspace：项目下所有符合条件的工作任务自动成为任务组，不需要为每个项目复制创建一条 Workspace。跨项目场景则使用保存的任务集合或任务过滤器。

## 2. 背景与问题

当前 EventFlowOS 已经有项目、事项、里程碑、项目更新、活动事件、专注记录和 Agent proposal，但它们分散在各自的 API 与页面中。完成一次较大的工作时，用户需要人工拼接：

- 需求/事项何时创建、推进、完成或取消；
- 项目更新中记录了哪些判断、风险和下一步；
- 里程碑何时变化；
- 实际投入了哪些专注时间；
- Agent 提案、人工修改和最终落库之间如何衔接；
- 同一个工作是否跨越了多个项目或多个阶段。

本能力要解决的是“**给 Agent 一份可引用、可排序、可控范围的事实材料**”，而不是替 Agent 在数据库内生成没有证据的结论。

## 3. 目标与非目标

### 3.1 目标

1. 把任务作为第一层聚合单位，一个任务下再按时间顺序放置相关证据事件。
2. 把“项目 Workspace”作为内置范围：`project_id → project.items`，不复制项目和任务。
3. 支持跨项目任务集合、显式任务 ID 和任务过滤器的组合。
4. 将项目更新、里程碑和项目快照作为 `project_context` 返回，不重复挂到每个任务组下。
5. 支持标题/正文搜索、来源类型、状态、标签、人员、时间范围等过滤。
6. 通过 MCP 提供只读任务证据包，让外部 Agent 完成综合分析、对比、复盘或下一步建议。
7. 默认遵守当前用户隔离、归档/删除边界、PAT 权限和内容长度限制；REST/UI 只保存定义，不保存结果快照。

### 3.2 非目标（首期明确不做）

- 不引入第二个 EventFlow 产品或旧的“事件链拆分”模型。
- 不新建通用 `events` 大表，也不迁移现有业务实体；用只读适配器统一输出。
- 不在后端内置 LLM、向量数据库或自动生成长篇结论。
- 不自动猜测任务之间的语义关系；跨项目任务需要显式选择或通过确定性的过滤器得到。
- 不把任意事件作为一等 Workspace 成员；事件必须归属于任务，项目级记录只能作为上下文。
- 不让 MCP 在首期直接创建/删除 Workspace 或修改事项，避免把分析权限和写权限混在一起。
- 不读取文件系统、聊天历史、Git 历史或外部项目；除非后续另立集成设计。
- 不替代当前“复盘”页面；Workspace 可以提供证据，但不改变复盘开关和周期模型。
- 不默认把个人事项放进项目分析；个人数据只有用户显式选择时才可加入。

## 4. 术语与边界

| 术语 | 定义 |
|---|---|
| Workspace | 保存名称、范围定义和过滤器的动态视图；每次查询都从当前业务表读取最新内容。 |
| Project Workspace | 以一个项目为范围的内置虚拟 Workspace，任务集合由 `items.project_id` 动态计算。 |
| Task Workspace | 以明确任务集合或任务过滤器为范围的保存/临时 Workspace，可跨项目。 |
| 任务（task） | EventFlowOS 当前 `items` 表中 `scope=work` 的工作事项；它是分析的主聚合单位。 |
| 任务组（task group） | 一个任务的摘要、所属项目以及与该任务直接相关的时间线事件。 |
| 项目上下文（project context） | 项目快照、项目更新和里程碑等不直接归属于某个任务的证据。 |
| 来源类型（source type） | 统一事件的来源，例如 `task`、`activity`、`focus_session`、`agent_proposal`。 |
| 时间线事件（timeline event） | 适配器将现有实体投影为统一的只读事件，不写回原表。 |
| 证据包（evidence pack） | MCP 返回的任务组、项目上下文、统计、截断信息和查询定义，供 Agent 引用和分析。 |
| 综合分析 | MCP 客户端基于证据包生成的结论、对比、风险或下一步；不表示 EventFlowOS 自己调用模型。 |

“事件”在本文中是泛称，不能理解为旧项目中的事件链节点。

## 5. 典型用户路径与应用场景

### 5.1 完成特定工作后的证据分析（核心场景）

用户直接打开“EventFlowOS MCP 增强”的 Project Workspace，或者保存一个跨项目 Task Workspace，搜索“workspace / MCP / 时间线”，时间范围设为最近 90 天。Agent 获取按任务分组、组内升序的证据包后可以回答：

- 每个任务从什么状态开始，经历了哪些决策和阻塞；
- 哪些任务已经完成，哪些任务只是计划或等待；
- 哪些项目级更新改变了任务所处的目标、风险或下一步；
- 实际专注时间与计划事项是否一致；
- 还有哪些证据缺口，下一步应补什么记录。

### 5.2 跨项目复用经验

把“提醒可靠性”“Agent 写入安全”“部署故障”三个项目下选定的任务加入同一个 Task Workspace，搜索“幂等、失败、重试”。Agent 可以按任务比较不同项目的处理方式、重复出现的风险和可复用的解决方案；项目更新只作为各任务所属项目的上下文出现一次。

### 5.3 版本/发布前核对

按项目 + 事项状态 + 时间范围拉取某次发布前的工作证据，检查需求、风险、验证记录和项目更新是否闭环。首期只输出事实与缺口，不自动把发布标记为完成。

### 5.4 故障与变更追踪

将故障相关事项、项目更新、活动记录和专注记录放入 Workspace，按升序查看“发现—判断—修复—验证—跟进”的时间序列，用于事后分析。

### 5.5 交接与上下文恢复

用户长时间没有维护某项目时，Agent 读取最近 30/90 天的证据包，生成“当前状态、已知风险、未完成事项、最近决策、建议第一步”。

### 5.6 个人工作方法分析（明确边界）

如果用户显式把个人事项或专注记录加入 Workspace，可以分析时间投入、等待时长和任务切换；默认不跨越工作/个人边界，避免无意暴露个人内容。

## 6. 设计原则

1. **不复制数据**：Workspace 只保存引用和过滤器，源数据更新后查询自然反映最新状态。
2. **来源可追溯**：每条事件带 `source_type`、`source_id`、`project_id`、`occurred_at`、`time_basis`，Agent 能引用原始记录。
3. **确定性优先**：同一查询、同一数据快照下返回顺序和去重规则稳定；不依赖模型猜测。
4. **分析与写入分离**：MCP 首期只读；涉及修改事项或项目的动作仍走既有 API/审批链路。
5. **渐进增强**：先做 SQL/ILIKE 过滤和规范化时间线，后续再评估全文索引、语义检索和分析运行历史。
6. **安全默认**：只返回当前 PAT 对应用户的数据；默认排除软删除、归档和个人事项，敏感 JSON 字段采用安全模式裁剪。

## 7. 数据模型

### 7.1 `workspaces`：只保存虚拟范围定义

新增迁移建议命名为 `024_virtual_workspaces.sql`（若已有更高版本，以实际迁移序号为准）。Workspace 表不保存任务快照，也不保存 timeline 结果，只保存一个可复算的查询定义。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | 主键 |
| `user_id` | uuid | 所有者，级联删除 |
| `name` | text | 用户可识别名称，同一用户不可重名 |
| `description` | text | 分析目标和使用说明，可空 |
| `scope_type` | text | `task_set` 或 `task_filter`；项目 Workspace 不必落一条记录 |
| `scope_spec` | jsonb | 任务范围定义，结构见 7.2 |
| `filter_spec` | jsonb | 查询过滤与展示定义，结构见 7.3 |
| `version` | integer | 乐观锁，默认 1 |
| `archived_at` | timestamptz | 软归档 |
| `created_at` / `updated_at` | timestamptz | 审计时间 |

项目 Workspace 通过 `project_id` 即时解析，不需要创建一条 Workspace 记录；如果用户需要给它命名、保存额外过滤器，再创建一个 `scope_type=task_filter` 的保存 Workspace，里面引用该项目范围。

### 7.2 任务范围：不使用多态 `workspace_members`

首期不建立“项目/事项/更新混合成员表”。这会把 Workspace 重新变成任意事件图，难以保证任务聚合和权限边界。任务范围采用三种形式：

| 范围 | 载荷 | 用途 |
|---|---|---|
| `project` | `{ "project_id": "..." }` | 内置 Project Workspace；动态选择该项目下 `scope=work` 且未删除的任务 |
| `task_set` | `{ "task_ids": ["...", "..."] }` | 显式选择同项目或跨项目任务 |
| `task_filter` | `{ "project_ids": [], "task_query": "...", ... }` | 按项目、状态、标签、人员和文本动态筛任务；如果带 `task_ids`，它作为额外 allowlist 与过滤条件取交集 |

保存的 Workspace 只允许 `task_set`/`task_filter`；临时查询和项目详情入口可以直接使用 `project`。所有任务 ID 在服务层验证 `items.user_id`、删除/归档状态；默认只接受 `scope=work`，只有 `include_personal=true` 且用户显式提供个人任务时才允许 `scope=personal`。数据库不复制任务正文。

### 7.3 `scope_spec` / `filter_spec` 推荐结构

```json
{
  "scope_type": "task_filter",
  "scope_spec": {
    "project_ids": ["project-uuid-1", "project-uuid-2"],
    "task_ids": [],
    "task_query": "MCP workspace",
    "statuses": ["planned", "in_progress", "waiting", "done"],
    "tag_ids": [],
    "people_ids": [],
    "include_personal": false
  },
  "filter_spec": {
    "event_types": ["task", "activity", "focus_session", "agent_proposal"],
    "include_project_context": true,
    "date_from": "2026-07-01T00:00:00+08:00",
    "date_to": "2026-09-21T23:59:59+08:00",
    "query": "完成 MCP workspace",
    "match_mode": "any",
    "group_order": "first_event_at",
    "event_order": "asc",
    "safe_mode": true
  }
}
```

`scope_spec` 决定有哪些任务，`filter_spec` 决定任务组内取哪些证据。未知字段在 API 层拒绝；`project` 范围不需要持久化到表中，直接使用相同的内部 `WorkspaceQuery` 结构。

### 7.4 任务组与项目上下文

查询结果的主结构不是扁平事件列表，而是：

```text
EvidencePack
├── task_groups[]
│   ├── task                 # 当前 item 快照
│   ├── project              # 所属项目摘要
│   ├── first_event_at
│   ├── last_event_at
│   ├── event_count
│   └── events[]             # 只包含与该 task 直接关联的证据
└── project_context[]        # project / milestone / project_update，一份一条
```

任务组内的直接证据来源：

| 来源 | 关联方式 | 默认 | 说明 |
|---|---|---:|---|
| `task` | `items.id` | 是 | 当前任务快照；不是完整历史事件溯源 |
| `activity` | `activity_events.entity_type=item` + `entity_id` | 否 | 任务状态/字段变化动作 |
| `focus_session` | `focus_sessions.item_id` | 否 | 任务实际专注时间 |
| `agent_proposal` | `target_item_id`/`applied_item_id` | 否 | Agent 提案和人工决策证据 |

项目上下文来源：

| 来源 | 关联方式 | 默认 | 说明 |
|---|---|---:|---|
| `project` | `projects.id` | 是 | 项目目标、状态、健康度、风险和下一步 |
| `milestone` | `milestones.project_id` | 是 | 项目级里程碑，不强行归属某个任务 |
| `project_update` | `project_updates.project_id` | 是 | 项目级判断、进度、风险和下一步 |

项目上下文不复制到每个 task group；跨项目 Task Workspace 会按项目去重后返回一份。这样既保留项目背景，又不会因任务数增长而重复放大上下文。

### 7.5 为什么选择任务聚合而不是通用事件成员

| 方案 | 做法 | 主要问题 | 结论 |
|---|---|---|---|
| 通用事件成员 | Workspace 任意挂项目、任务、更新、里程碑、活动 | 很快变成多态事件图；重复关系、权限校验和排序语义复杂 | 不采用 |
| 复制任务/事件快照 | 创建 Workspace 时复制一份内容 | 数据过期、重复存储、删除和隐私边界难处理 | 不采用 |
| 复用现有 `saved_views` | 把 Workspace 定义塞进当前事项筛选视图 | `saved_views` 没有项目上下文、任务组、归档/版本和分析证据语义；会把简单列表筛选与分析上下文绑死 | 不采用，保留两者边界 |
| **任务聚合虚拟视图** | 任务是根；任务事件组内排序；项目记录为去重上下文 | 需要明确任务与项目级记录的边界，但可解释且能复用现有表 | **首期采用** |

任务是用户真正要“完成”的单位，也是当前 `items`、活动、专注、提案最容易形成稳定关联的实体；项目则天然适合成为任务集合的快捷范围。这个模型同时覆盖：

- 单项目分析：`project_id → tasks[] → task events[]`；
- 跨项目分析：`task_ids/project_ids/filter → tasks[] → task events[]`；
- 项目背景分析：`tasks[].project_id → unique project_context[]`；
- 未来扩展：只需新增任务级来源适配器，不改变 Workspace 主模型。

## 8. 查询与时间线语义

### 8.1 任务集合规则

先计算任务集合，再计算每个任务的证据：

1. `project` 范围：选择 `items.project_id = project_id` 的工作任务；
2. `task_set` 范围：选择显式 `task_ids`，并验证每个任务属于当前用户且为工作事项；
3. `task_filter` 范围：按项目、任务文本、状态、标签、人员和任务日期筛选；
4. 对任务集合应用归档、软删除和 `include_personal` 边界；
5. 再按 `event_types` 和时间范围读取任务事件；如果 `include_project_context=true`，按这些任务所属项目去重读取项目上下文。

任务去重键为 `task_id`；组内事件去重键为 `(source_type, source_id)`；项目上下文去重键同样为 `(source_type, source_id)`。项目 Workspace 不允许通过任务筛选混入其他项目，跨项目必须使用 `task_set` 或 `task_filter`。

推荐的服务执行顺序固定为：

```text
resolve scope
  → load task candidates
  → apply task-level search/status/tag/date filters
  → load task events by item_id
  → group and order tasks/events
  → load unique project context by project_id
  → redact + budget + cursor
  → return EvidencePack
```

这样项目 Workspace 和保存的跨项目 Workspace 只是 `resolve scope` 不同，后续查询、排序、裁剪和 MCP 输出完全复用；不会出现“项目页面一套逻辑、MCP 另一套逻辑”。

### 8.2 搜索规则

- `query` 为空时只应用结构化过滤。
- 默认 `query_scope=task`：搜索命中任务标题/备注或任务直接事件后，才产生 task group；项目上下文命中不会凭空生成任务组。
- 如果用户只想搜索项目更新/里程碑，显式使用 `query_scope=project_context`；结果放在 `project_context`，不伪造任务关联。
- 首期使用转义后的 `ILIKE` 子串匹配，兼容中文，不直接使用不稳定的数据库全文分词。
- 任务搜索字段包括事项标题/备注/地点/URL、标签和安全裁剪后的任务 activity/focus/proposal 文本；项目过滤字段包括项目名称/目标/风险/下一步。
- `include_project_context=true` 时，返回命中任务所属项目的上下文；上下文本身不改变 task group 的匹配结果。
- 默认 `match_mode=any`；可选 `match_mode=all` 时，按空白和中英文标点切分词，所有非空词都必须命中同一条规范化记录。
- 过滤与搜索在数据库层执行，返回内容在应用层做安全裁剪和格式统一。

### 8.3 时间排序

每个任务组和每条事件都包含：

```json
{
  "occurred_at": "2026-09-20T10:30:00+08:00",
  "recorded_at": "2026-09-20T11:02:00+08:00",
  "time_basis": "project_update.created_at"
}
```

默认先按 task group 的 `first_event_at ASC` 排序，再在组内按 `occurred_at ASC` 排序，适合重建每个任务的工作过程；支持 `group_order=last_event_at|updated_at` 和 `event_order=desc` 查看最近活动。相同时间使用 `recorded_at`、`source_type`、`source_id` 作为稳定的二级/三级排序键。查询不会假装把没有发生时间的项目元数据当成精确事件，会在 `time_basis` 中明确标注。

### 8.4 分页、长度和截断

- 单次默认返回最多 100 个 task group，硬上限 200 个；每组默认最多 100 条事件。
- 单条内容默认最多 4,000 字符，证据包总字符数默认最多 80,000；超出时返回 `truncated=true` 和 `next_cursor`。
- 游标包含最后一个 task group 的排序键，不使用不稳定的 offset 分页；组内事件随组一次返回，避免分页把任务上下文拆散。
- MCP 返回 `matched_task_count`、`returned_task_count`、`source_counts`、`context_project_count`、`time_range`、`truncated` 和 `applied_filters`，让 Agent 知道材料是否完整。

### 8.5 任务组与事件结构

```json
{
  "task_groups": [{
    "task": {
      "id": "task-uuid",
      "title": "完成 MCP 读取接口设计",
      "status": "in_progress",
      "project_id": "project-uuid"
    },
    "project": {"id": "project-uuid", "name": "EventFlowOS"},
    "first_event_at": "2026-09-10T09:00:00+08:00",
    "last_event_at": "2026-09-18T11:02:00+08:00",
    "event_count": 2,
    "events": [{
      "event_key": "activity:uuid",
      "source_type": "activity",
      "source_id": "uuid",
      "occurred_at": "2026-09-18T09:12:00+08:00",
      "recorded_at": "2026-09-18T09:12:00+08:00",
      "time_basis": "activity_events.created_at",
      "title": "任务状态更新",
      "content": "……",
      "metadata": {},
      "source_url": "/api/v1/items/task-uuid"
    }]
  }],
  "project_context": [{
    "event_key": "project_update:uuid",
    "source_type": "project_update",
    "source_id": "uuid",
    "project_id": "project-uuid",
    "occurred_at": "2026-09-18T09:00:00+08:00",
    "time_basis": "project_update.created_at",
    "title": "项目进度更新",
    "content": "……"
  }]
}
```

`source_url` 是应用内引用，不代表 MCP 客户端可以绕过认证直接访问。项目上下文不在每个 task group 中重复展开。

## 9. REST/API 方案

### 9.1 Workspace 管理

```text
GET    /api/v1/workspaces
POST   /api/v1/workspaces
GET    /api/v1/workspaces/{workspace_id}
PATCH  /api/v1/workspaces/{workspace_id}
DELETE /api/v1/workspaces/{workspace_id}       # 软归档
```

写入接口沿用现有 session + CSRF / PAT write scope；更新使用 `If-Match` 或显式 `version`，避免多个页面覆盖范围定义。任务 ID 和过滤器作为 Workspace 定义的一部分保存，不另建多态成员 API。

项目本身的虚拟 Workspace 不需要创建记录，直接复用项目路由：

```text
GET /api/v1/projects/{project_id}/workspace/timeline
```

### 9.2 查询接口

```text
GET /api/v1/workspaces/{workspace_id}/timeline
GET /api/v1/projects/{project_id}/workspace/timeline
```

查询参数建议：`query`、`query_scope`、`event_types`、`date_from`、`date_to`、`group_order`、`event_order`、`limit`、`cursor`、`include_project_context`、`safe_mode`。

API 返回 `task_groups + project_context`，与 MCP 证据包保持一致，避免 UI 和 Agent 获得两套不同语义。

### 9.3 读模型与服务边界

建议新增：

- `storage/repositories/workspaces.py`：Workspace 定义 CRUD；
- `application/workspace_query_service.py`：项目/任务范围解析、过滤规范化、实体所有权检查、任务组适配器、项目上下文适配器、去重、排序、分页、裁剪；
- `api/routes/workspaces.py`：REST 路由；
- `api/schemas.py`：Workspace、ScopeSpec、TaskGroup、ProjectContext、EvidencePack schema。

查询服务不能复用前端过滤逻辑，也不能让 MCP 直接拼接 SQL。

## 10. MCP 方案

### 10.1 首期工具

```text
pa_list_workspaces(include_archived=false)
pa_get_workspace(workspace_id)
pa_query_workspace(
  workspace_id=null,
  project_id=null,
  task_ids=null,
  query=null,
  query_scope="task",
  event_types=null,
  date_from=null,
  date_to=null,
  group_order="first_event_at",
  event_order="asc",
  limit=100,
  cursor=null,
  include_project_context=true,
  safe_mode=true
)
```

`pa_query_workspace` 是核心工具。`workspace_id`、`project_id`、`task_ids` 三者必须恰好提供一个：

- `workspace_id`：查询保存的 Task Workspace；
- `project_id`：直接查询该项目的内置 Project Workspace；
- `task_ids`：执行一次不保存的跨项目临时 Task Workspace。

它返回按任务聚合的证据包，不返回模型生成的“最终分析结论”。Agent 可以根据用户问题自行决定先查询、再分析、再引用 `event_key`。

首期不提供 `pa_create_workspace`、`pa_update_workspace` 和 `pa_delete_workspace`，Workspace 由 Web/API 创建和维护；这样只读 PAT 可以安全地提供给分析 Agent。后续若需要 Agent 保存查询，再单独增加 write scope 和审批策略。

### 10.2 MCP 调用示例

```json
{
  "name": "pa_query_workspace",
  "arguments": {
    "project_id": "project-uuid",
    "query": "完成 MCP workspace 分析能力",
    "event_types": ["task", "activity", "focus_session"],
    "date_from": "2026-07-01T00:00:00+08:00",
    "date_to": "2026-09-21T23:59:59+08:00",
    "group_order": "first_event_at",
    "event_order": "asc",
    "limit": 100,
    "safe_mode": true
  }
}
```

返回至少包含：`scope`、`task_groups`、`project_context`、`matched_task_count`、`returned_task_count`、`source_counts`、`context_project_count`、`time_range`、`truncated`、`next_cursor`、`applied_filters`。

### 10.3 MCP 安全约束

- PAT 仍通过现有 `TokensRepository` 验证；没有有效 PAT 不执行查询。
- read-only PAT 只能调用读取工具；Workspace 查询不修改任何表。
- 所有 SQL 条件必须包含 `user_id`，保存的 Workspace、任务范围和源实体都要验证所有权。
- `safe_mode=true` 默认递归裁剪 `token`、`secret`、`password`、`cookie`、`private_key`、`authorization` 等键，并限制 `source_context`/`execution_output` 的深度和长度。
- MCP 工具的 limit、字符预算和查询超时必须硬限制，防止一次调用拖垮数据库或把全部私人数据塞进上下文。

## 11. Web 页面设计

### 11.1 P0：Workspace 列表页

- 侧栏新增“工作区”，与“项目跟进”同属事务区。
- 显示名称、说明、任务数、覆盖项目数、最近任务活动、归档状态。
- 支持新建 Task Workspace、复制过滤器、归档；不显示其他用户数据。
- 项目不要求出现在保存列表中；项目详情直接进入对应的 Project Workspace。

### 11.2 P0：Workspace 详情页

顶部：名称/项目名称、目标说明、任务范围、覆盖项目、时间范围、搜索框、事件类型开关、刷新按钮。

主体：

1. 主区域按任务分组：显示任务状态、所属项目、首/末事件时间、事件数；
2. 展开任务组后显示组内时间线：任务快照、活动、专注、Agent 证据；
3. 独立的项目上下文折叠区：项目更新和里程碑按项目去重展示；
4. 右侧证据详情：正文、元数据、原始实体链接、复制 event key；
5. 顶部摘要：任务数、项目数、来源分布、最早/最新记录、截断提示；
6. “复制 MCP 查询”按钮：复制当前过滤器对应的工具参数，不复制敏感内容。

### 11.3 项目详情快捷入口

项目详情页增加“在工作区中分析”动作：

- 直接打开当前项目的 Project Workspace，不创建额外 Workspace 记录；
- 默认以该项目下工作任务为任务集合，项目更新/里程碑进入 project context；
- 用户可在当前过滤条件下将查询另存为 Task Workspace；
- 不默认加入个人事项、活动 payload、Agent proposal 原始 JSON。

### 11.4 UI 不承担的职责

前端不展示自动生成的分析结论，不在浏览器内调用模型；它负责管理范围和核对原始证据。综合分析通过 MCP 客户端完成。

### 11.5 前后端同步交付方案

前端和后端必须围绕同一份“Workspace 查询契约”交付，不能由前端再次拼接项目、事项和更新数据。推荐的依赖关系如下：

```text
PostgreSQL migrations
        ↓
WorkspaceRepository + WorkspaceQueryService
        ↓
REST /api/v1/workspaces/{id}/timeline ─────────┐
REST /api/v1/projects/{id}/workspace/timeline ──┤
                                               ├─ 同一份 EvidencePack schema
MCP pa_query_workspace(scope) ─────────────────┘
        ↓
frontend api client → React Query → WorkspacePage / Timeline / Detail
```

#### 后端交付清单

1. **迁移**：新增 `workspaces`、必要索引和约束；不改写现有业务表，也不建立多态 `workspace_members`。
2. **Schema**：在 `backend/src/personal_affairs/api/schemas.py` 定义 `WorkspaceCreate`、`WorkspacePatch`、`WorkspaceOut`、`WorkspaceScope`、`TaskGroupOut`、`ProjectContextOut`、`EvidencePackOut`。同一套输出模型用于 OpenAPI 和 MCP 的返回注解。
3. **Repository**：`storage/repositories/workspaces.py` 只负责 Workspace 定义 CRUD 和用户隔离，不承载搜索拼接。
4. **Query service**：`application/workspace_query_service.py` 负责：
   - 校验 `scope_spec`/`filter_spec` 白名单和 UUID；
   - 校验 Workspace、任务、项目和源实体属于当前用户；
   - 先解析 task set，再调用任务事件和项目上下文适配器；
   - 参数化 SQL、任务去重、稳定组排序、cursor、字符预算和安全裁剪；
   - 生成 `source_counts`、`context_project_count`、`time_range`、`truncated` 等确定性统计。
5. **REST route**：新增 `api/routes/workspaces.py`，提供保存 Workspace CRUD 和 timeline；在 `projects.py` 增加 Project Workspace 只读入口；写接口沿用现有 CSRF/PAT write scope 与乐观锁。
6. **MCP**：`mcp/server.py` 只调用 `WorkspaceQueryService`，不复制 SQL 和过滤逻辑；`pa_list_workspaces`/`pa_get_workspace`/`pa_query_workspace` 首期保持只读，查询 scope 支持保存 Workspace、项目或临时 task IDs。
7. **导出与 OpenAPI**：如果当前导出接口采用固定白名单，默认只导出保存的 Workspace 定义，不导出重复的 task group/timeline 快照。
8. **测试**：先完成 repository/service/API contract，再让前端接入；任何返回字段变化先改 schema 和测试，不直接改前端类型绕过契约。

#### 前端交付清单

1. **类型镜像**：在 `frontend/src/api/client.ts` 增加 `Workspace`、`WorkspaceScope`、`TaskGroup`、`TimelineEvent`、`ProjectContext`、`EvidencePack`、`WorkspaceFilterSpec`，字段名与后端 JSON 保持一致；时间字段统一解析为 ISO 字符串，不在类型层转换时区。
2. **API 封装**：增加 `api.workspaces()`、`api.createWorkspace()`、`api.updateWorkspace()`、`api.archiveWorkspace()`、`api.workspaceTimeline()`、`api.projectWorkspaceTimeline()`；所有写请求携带现有 CSRF token，查询请求支持 cursor。
3. **页面路由**：在 `App.tsx` 增加 `workspaces` 页面和“工作区”导航项；页面级数据使用 TanStack Query，详情过滤器变化只刷新 timeline query，不重载项目列表。
4. **组件拆分**：
   - `WorkspacesPage`：列表、新建、归档、选择 Workspace；
   - `WorkspaceFilterBar`：搜索、来源、状态、日期、升/降序、安全模式；
   - `WorkspaceTaskGroups`：任务分组、项目色、状态、首末时间、分页加载；
   - `WorkspaceTaskTimeline`：单任务内的事件时间线和来源图标；
   - `WorkspaceContextPanel`：项目更新、里程碑和项目快照的去重展示；
   - `WorkspaceScopeEditor`：项目范围、任务 ID 集合和任务过滤器编辑；
   - `WorkspaceMcpCopyButton`：复制当前过滤器对应的 MCP 参数。
5. **状态交互**：创建/编辑/归档成功后失效对应 Workspace query；timeline 只读，不做乐观写入；筛选条件保存在 URL hash 或页面状态，但不自动写回 Workspace，除非用户点击“保存过滤器”。
6. **边界呈现**：清楚区分“没有匹配记录”“查询被截断”“源记录已归档/删除”“时间依据不是实际发生时间”，不能用空白列表掩盖语义差异。
7. **性能**：首期最多渲染后端返回的 200 个任务组，不引入复杂虚拟列表；确认数据量和使用频率后再优化。

#### 共享响应契约

```json
{
  "scope": {"type": "project", "project_id": "project-uuid"},
  "workspace": null,
  "task_groups": [],
  "project_context": [],
  "matched_task_count": 18,
  "returned_task_count": 18,
  "source_counts": {"task": 10, "activity": 5, "project_update": 5, "milestone": 2},
  "context_project_count": 1,
  "time_range": {"from": "2026-07-01T00:00:00+08:00", "to": "2026-09-20T10:30:00+08:00"},
  "truncated": false,
  "next_cursor": null,
  "applied_filters": {"query": "MCP", "group_order": "first_event_at", "event_order": "asc", "safe_mode": true}
}
```

REST 和 MCP 只允许在传输层包装该结构，不改变 `task_groups`、`project_context` 和事件字段语义。前端任务时间线、MCP Agent 和测试都以 `task.id` / `event_key` 作为引用单位。

#### 错误与空状态契约

| 场景 | HTTP/API | MCP | 前端行为 |
|---|---|---|---|
| Workspace 不存在或不属于用户 | 404 | 工具错误，不泄露存在性 | 显示“工作区不存在或已归档” |
| 查询参数非法 | 422 | 工具错误并返回字段名 | 保留当前输入，标记具体字段 |
| 版本冲突 | 409 | 不适用于首期只读工具 | 重新拉取详情并提示刷新 |
| 没有匹配记录 | 200 + 空 `task_groups`/`project_context` | 正常返回空证据包 | 显示“范围内没有匹配记录” |
| 结果超预算 | 200 + `truncated=true` | 正常返回并提示继续使用 cursor | 显示继续加载入口 |

#### 同步开发顺序

1. 后端先提交迁移、schema、repository、query service 和服务级测试；
2. 锁定 OpenAPI response shape，并补 API smoke；
3. 接入 MCP，增加工具名、参数和只读行为 contract；
4. 前端同步镜像类型和 API wrapper，先用固定响应开发时间线组件；
5. 接通真实 API，补错误/空/截断/分页状态；
6. 最后补项目详情快捷入口和复制 MCP 参数；
7. 运行后端全量测试、前端 `tsc -b`/build，确认现有事项和项目页面无回归。

这样即使前端页面延后，REST/MCP 查询能力仍可独立交付；如果后端契约变化，必须先更新本文、Pydantic schema、OpenAPI smoke 和前端类型。

## 12. 安全、隐私与数据治理

1. **用户隔离**：所有保存 Workspace、任务范围、项目范围、源实体和查询结果按 `user_id` 限定。
2. **默认最小暴露**：默认排除归档、软删除和个人事项；敏感扩展字段只在 `safe_mode=false` 且调用方明确承担风险时考虑开放，首期可暂不支持关闭安全模式。
3. **内容裁剪**：不把完整 `execution_output`、proposal evidence 或活动 payload 原样灌入上下文；返回摘要和受限 metadata。
4. **外部链接**：只返回已存的 URL 字符串，不在查询过程中抓取网页，也不触发 webhook、会议或第三方 API。
5. **审计**：首期不记录查询正文和返回内容；如未来需要审计，保存哈希、Workspace ID、调用者和耗时，不保存完整私人上下文。
6. **归档语义**：归档 Workspace 不删除源数据；删除 Workspace 不影响项目、任务、更新或活动记录；Project Workspace 随项目权限和项目归档状态实时变化。

## 13. 性能与一致性目标

- 首期目标：单用户常规数据量（约 10 万条以内）下，常用 Workspace 查询 p95 小于 1 秒；超过预算明确返回截断，不无限扩大 SQL。
- 为 Workspace owner、范围类型、`items(user_id, project_id, status, archived_at, deleted_at)` 和各时间列增加索引；不要一开始为 JSON payload 建宽泛 GIN 索引。
- 查询使用事务内一致快照；不承诺跨多个独立 MCP 调用的快照一致性。
- 记录 `query_duration_ms` 仅用于服务端日志/指标，不默认暴露给 Agent。

## 14. 测试与验收标准

### 14.1 数据与权限

- 同项目的项目、事项、里程碑、项目更新可以被同一 Workspace 合并。
- Project Workspace 能自动选择该项目下的工作任务，项目更新/里程碑进入 `project_context`，不会重复到每个任务组。
- 两个项目的任务可以组合，且每个 task group 的 `project_id/project_name` 正确。
- 不属于当前用户的 Workspace、任务、项目或源实体返回 404/权限错误，不泄露存在性。
- 重复任务 ID 会去重；查询不会重复任务组、任务事件或项目上下文。
- 归档/删除默认排除，显式参数行为有测试覆盖。

### 14.2 搜索与排序

- 中文/英文子串搜索覆盖标题、备注、项目更新正文和风险字段。
- 状态、标签、人员、时间范围和来源类型可组合过滤。
- 任务组升序/降序、组内相同时间的稳定排序、cursor 分页和字符截断可复现。
- 每个任务组都有首末事件时间；每条事件都有 source ID、project ID、occurred_at、recorded_at 和 time_basis。

### 14.3 MCP 契约

- MCP 工具列表出现 `pa_list_workspaces`、`pa_get_workspace`、`pa_query_workspace`，并覆盖 `workspace_id`、`project_id`、`task_ids` 三种 scope。
- 无 PAT、过期 PAT、read-only PAT 行为符合现有认证规则。
- 查询工具为只读，测试确认不会写入 Workspace、事项或活动表。
- `safe_mode` 会裁剪敏感键并保留 `truncated`/预算信息。

### 14.4 Web/API

- OpenAPI 包含 Workspace CRUD、任务范围管理和 Project/Task Workspace timeline 查询路径。
- 前端可以打开项目 Workspace，创建跨项目 Task Workspace，执行搜索，按任务分组浏览并复制 MCP 参数。
- 不影响现有事项、项目、日历、提醒、复盘和 Agent proposal 测试。

## 15. 分阶段实现建议

### Phase 1：只读查询核心

1. 增加 Workspace 定义迁移和 repository，不建立多态成员表；
2. 实现 Project/Task-set/Task-filter 三种 scope 解析；
3. 实现 `workspace_query_service`、任务事件适配器和项目上下文适配器；
4. 增加 REST timeline 查询和项目 Workspace 入口；
5. 增加任务分组、排序、过滤、分页、裁剪、权限测试。

### Phase 2：MCP 证据包

1. 注册三个只读 MCP 工具；
2. 复用同一个 query service，避免 REST/MCP 语义分叉；
3. 增加 MCP contract 和安全模式测试；
4. 在文档中给出 Agent 分析提示模板，但不在后端调用模型。

### Phase 3：Web 管理

1. Task Workspace 列表、创建/编辑、任务范围管理；
2. 任务分组详情、项目上下文和原始实体链接；
3. 项目详情直接打开 Project Workspace；
4. 保存项目查询为 Task Workspace、复制 MCP 查询参数。

### Phase 4：可选增强

- 语义搜索或全文索引；
- 查询快照/分析运行历史；
- Agent 受控保存 Workspace（write scope + 审批）；
- 外部 Git/文档/聊天连接器；
- 可解释的自动关联建议，但必须允许用户确认后入 Workspace。

## 16. Grill-with-doc 压测结论

| 被拷问的问题 | 结论 |
|---|---|
| 目标到底是哪一个 EventFlow？ | 只改 `/home/jkiter/eventflowos` 的个人事务管理版；`Horizon` 和旧事件链实现均不在范围内。 |
| Workspace 是不是新项目？ | 不是。它是动态查询视图，不复制数据、不拥有项目生命周期。项目本身直接作为内置 Project Workspace。 |
| 能否跨项目？ | 能。按显式任务 ID 或任务过滤器组合，结果按任务分组并保留项目来源。 |
| “串联事件”是否要做通用图数据库？ | 首期不做。任务是唯一主聚合单位，活动/专注/提案按任务关联，项目更新/里程碑作为去重后的项目上下文；真正的语义边/图关系后续单独设计。 |
| 综合分析由谁完成？ | EventFlowOS 提供确定性证据包；外部 MCP Agent 负责综合分析并引用 event key。 |
| 为什么不直接让 MCP 创建 Workspace？ | 首期把 MCP 设为只读，避免给分析 Agent 写权限；Web/API 管理足够完成保存和维护。 |
| 搜索是否上向量数据库？ | 首期不做。中文子串 + 结构化过滤可先满足可验证需求，后续以实际命中率决定。 |
| 时间顺序是否可信？ | 返回 `occurred_at + time_basis`，按来源语义选择时间，并用稳定键处理同一时间；不伪装成完整事件溯源。 |
| 默认包含哪些数据？ | 任务快照和项目上下文（项目、里程碑、项目更新）；活动、专注、Agent proposal 需要显式开启；个人事项默认排除。 |
| 如何避免泄露 token/secret？ | 全部查询按用户隔离，`safe_mode` 默认开启，敏感键裁剪，限制单条/总字符和返回上限。 |
| 是否替代复盘功能？ | 不替代。Workspace 是按问题临时或长期组合证据的工具，复盘仍是周期性产品能力。 |
| 删除 Workspace 会不会删除业务数据？ | 不会，只删除引用和过滤器。 |
| 是否需要先补历史数据？ | 不需要。现有项目/事项/更新等记录即时可查询；没有历史记录的时间段应明确显示为空。 |

### 16.1 已收敛的推荐默认值

- 首期同时提供 Web/API 管理和 MCP 只读查询。
- 默认任务组和组内事件均按升序；分析“最近动态”时显式传 `group_order=last_event_at` 与 `event_order=desc`。
- 默认 `limit=100`、硬上限 200、单条 4,000 字符、总量 80,000 字符。
- 默认聚合单位为任务；默认返回任务快照和 `project/milestone/project_update` 上下文，`activity/focus_session/agent_proposal` 显式开启。
- 默认排除 `personal`、归档、软删除和敏感扩展 payload。
- 不做模型调用、向量检索、自动关系推断和 MCP 写入。

### 16.2 仍需在实现前确认的两个产品选择

这两项不影响后端核心模型，但会影响首期页面范围；若没有额外指定，按推荐值实现：

1. **是否首期就做 Workspace Web 页面**：推荐“做”，项目详情先提供 Project Workspace，独立页面管理跨项目 Task Workspace。
2. **是否允许保存临时查询**：推荐“允许”，但只保存任务范围和过滤器，不保存查询结果快照；这样结果始终反映最新数据。

## 17. 实现前的变更隔离要求

- 保留当前工作区已有的地点/会议字段未提交改动，不回滚、不重排。
- 新功能只新增迁移、repository、service、route、MCP contract、前端页面和文档；不重写现有事项/项目查询。
- 实现完成前不执行生产迁移、不重启服务、不改变现有 PAT scope。
- 任何需要扩大到外部数据源、模型服务或旧事件链代码的需求，必须另开设计决策。

## 18. 文档维护规则

后续每次修改以下内容都要同步本文件：

- Workspace scope 字段、任务聚合结构或 `scope_spec`/`filter_spec` 白名单；
- 任务/项目上下文适配器、时间依据、搜索字段和敏感裁剪规则；
- MCP 工具签名、权限或返回结构；
- UI 页面范围、验收标准和非目标；
- 任何从“推荐默认”变成“已确认”的产品决策。

实现完成后，在本文顶部补充实现版本、迁移号、测试命令和上线验证结果；未实现能力不得写成“已支持”。
