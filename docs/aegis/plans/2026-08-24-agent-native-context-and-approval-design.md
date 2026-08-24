# Agent 原生事件管理：上下文接入、腾讯会议/IM 解析与人机审批放行机制设计

- **Date**: 2026-08-24
- **Status**: Design Approved / Draft Specification
- **Scope**: standalone `personal-affairs` repository
- **Target**: 从“人类手动录入管理”演进为“多源上下文无感流入 + Agent 结构化解析 + 人机交接审批放行 + 自动化协同推进”的 Agent 原生事件中枢。

## 0. 已确认设计决策

- **2026-08-24：L2/L3 使用独立 `agent_proposals` 提议队列，不向 `items.status` 增加 `needs_review`。**
  - 原因：当前 `items.status` 是正式事项生命周期，已被后端枚举、前端类型、今日/日历/收集箱筛选和状态机共同使用；`needs_review` 更准确地表示“候选变更等待审批”，不是一个正式事项状态。
  - 结果：L1 高置信、低风险事项可以直接写入 `items` 并带来源溯源；L2/L3 先写入 `agent_proposals`，用户批准后再事务性创建或修改正式 `items`。
- **2026-08-24：第一版 L1 自动放行范围收窄为初始白名单。**
  - L1 仅允许“确定性会议邀约”和“受信 Agent 明确请求创建的低风险独立事项”自动写入正式 `items`。
  - 飞书 IM 文本、后续更多 IM、邮件、网页剪贴、截图/OCR、会议纪要 action items、任何修改既有事项或批量变更的动作，第一版默认进入 `agent_proposals`。
  - 原因：会议邀约字段稳定且可验证；其他上下文语义误判和隐私扩散风险更高，先用 proposal 批准率观察后再逐步升级自动化范围。
- **2026-08-24：腾讯会议第一版实现事前会议邀约解析，并接入官方 `tmeet` CLI 作为受控只读补全路径；纪要/录音/截图 action items 延后。**
  - 第一版输入支持完整邀约文本、会议号、会议 ID，以及能提取会议号/会议 ID 的加入链接。
  - 默认先做本地文本解析；若缺少主题/时间等关键字段，则调用已安装且已授权的官方 `tmeet` CLI 查询会议详情。
  - 第一版 `tmeet` 能力限定为只读查询：允许 `meeting get` / 后续必要的只读 search；不开放 `meeting create`、`meeting update`、`meeting cancel`、录制、纪要或参会报告读取。
  - 若链接无法稳定解析会议号/会议 ID，或 CLI 未安装/未授权/查询失败/超时，则进入 L2 proposal，由用户补全确认。
- **2026-08-24：`tmeet` CLI 只在服务端后台按需启用，不做前端/浏览器直连。**
  - 前端只提交会议文本、会议号、会议 ID 或链接；所有 CLI 调用由 Personal Affairs 后端执行。
  - `tmeet` 默认关闭，必须通过运行时配置显式启用，并设置命令路径、执行超时和查询失败降级。
  - OAuth/凭据只允许存在服务端 runtime secret 或 `tmeet` 自身授权目录中，禁止写入仓库、设计文档、OpenAPI 示例、前端 localStorage 或 webhook payload。
  - 后端只记录非敏感审计摘要，例如 `tmeet_enabled`、`lookup_method`、`lookup_status`、耗时和错误类别；不记录 token、完整凭据或不必要的会议隐私内容。
- **2026-08-24：腾讯会议自动同步列为后续 P2 候选能力，不进入第一版。**
  - 第一版只处理用户主动提交的会议文本、会议号、会议 ID 或链接。
  - 后续 P2 可新增服务端后台同步开关：默认关闭，按固定窗口只读拉取未来会议列表并同步到 `items`。
  - 同步必须按 `meeting_id` / `meeting_code` 等稳定键去重；冲突、取消、查询失败、用户已手动编辑过的事项，不自动覆盖，统一进入 `agent_proposals`。
  - 同步能力仍限制为只读会议列表/详情；录制、纪要、参会报告、创建/更新/取消会议不属于该候选能力。
- **2026-08-24：第一版上下文输入限定为文本-only，接入来源暂定只走飞书 IM。**
  - 第一版不接收图片、截图、文件、语音、录音、会议纪要附件、网页抓取或浏览器插件内容。
  - 第一版不做微信、钉钉、邮箱、网页剪贴、OCR/Vision LLM 直接接入。
  - 外部上下文入口暂定为飞书 IM：用户把会议邀约、会议号、待办文本或上下文摘要发送给飞书机器人/指定会话，服务端接收文本后生成 `agent_proposals` 或触发腾讯会议解析。
  - Feishu IM 接入仍必须遵守 proposal-first 原则；除已确认的 L1 白名单外，不直接写正式事项。
- **2026-08-24：飞书 IM 第一版只做机器人被动接收文本消息，不主动读取或轮询聊天记录。**
  - Personal Affairs 只处理用户主动发送给机器人/指定会话的文本消息。
  - 不扫描历史聊天、不调用聊天记录搜索、不轮询会话、不读取未转发给机器人的上下文。
  - 飞书事件消息必须按消息 ID / event ID 做幂等去重；重复投递不得重复创建 proposal 或事项。
  - 该边界用于最小化权限、隐私扩散和重复处理风险。
- **2026-08-24：`pa_find_free_slots` 保留在第一版，但只做只读空闲时间查询。**
  - 第一版仅基于 Personal Affairs 内已有 `items` 与 milestones 计算空闲段，不接外部日历。
  - 默认工作时间为 `09:00-18:00`，工具参数可覆盖；不自动创建、移动或取消事项。
  - 返回候选空闲段、冲突摘要和排除原因，供 Agent 生成 proposal 或回复用户。
- **2026-08-24：`pa_get_executive_briefing` 保留在第一版，但只做只读结构化上下文快照。**
  - 返回今日事项、逾期事项、待审批 proposal、未处理提醒、日历冲突摘要和可选专注状态等 JSON 块。
  - 不创建、不修改、不自动重排事项，也不在后端生成 LLM 日报文案；Agent 可基于快照自行组织回复。
  - 原因：Agent 接手前需要一个稳定、低成本的全盘上下文入口，避免连续调用多个工具时漏掉待审批项或提醒。
- **2026-08-24：Web 端 Agent 交接卡片第一版只做最小审批队列。**
  - 第一版在「今日」和「收集箱」展示 pending proposals，支持确认、修改后确认、忽略/拒绝三类闭环动作。
  - 修改后确认仅覆盖正式事项已有核心字段，例如标题、范围、状态、优先级、日期/时间、备注与提醒；不做复杂差异编辑器、拖拽排期、批量审批或多步骤自动化编排。
  - 原因：第一版关键风险是 proposal 幂等落库与审批事务闭环，复杂 UI 会扩大交付面，并推迟飞书 IM 文本入口和腾讯会议解析的验证。
- **2026-08-24：源码对齐实现原则：入站飞书、出站 webhook、正式事项服务层三者分离。**
  - 现有 `/api/v1/webhooks` 是 Personal Affairs 对外发送事件的订阅管理与 outbox 事件查看，不作为飞书 IM 入站回调入口。
  - 飞书 IM 入站新增独立 integration route，并以独立幂等表记录飞书 `event_id` / `message_id`；重复投递不得重复创建 proposal 或事项。
  - proposal 批准后创建/修改正式事项必须复用现有 `ItemService.create/patch`，以保留日程校验、项目约束、people/tags、activity、提醒和出站事件语义。
- **2026-08-24：Focus Shield 不进入第一版实现批次，仅作为后续独立小改候选。**
  - 第一版不要求外部 Agent 自动静默，也不生成专注结束摘要。
  - 原因：当前 focus start/stop 只写 `focus_sessions`，若新增 `focus.started` / `focus.ended` outbox 事件，需要同步扩展后端事件类型、webhook 设置选项与订阅语义；该改动不在“飞书 IM 文本入口 → proposal → 审批 → item”的主路径上。
  - 后续如需要 Focus Shield，可单独增加 `focus.started` / `focus.ended` 出站事件，但仍不承诺 Personal Affairs 验证外部 Agent 是否静默。
- **2026-08-24：Subtasks / Checklists 不进入第一版，仅作为后续 P2/P3 候选。**
  - 第一版不新增 `checklist_items` 表、子任务状态机、排序/完成度 API 或 MCP 更新接口。
  - Agent 拆解出的步骤可暂存在 proposal 的 `proposed_payload` / `evidence` 或正式事项 `notes` 中，必须由用户确认后再成为正式事项内容。
  - 原因：该能力需要新增子结构、详情 UI 与进度同步语义，和本版核心“飞书 IM 文本接入 + proposal 审批 + 腾讯会议解析”不同轴，提前做会扩大交付面。

---

## 1. 核心设计理念 (Core Paradigm)

传统的个人事务管理系统（如 Todoist、Things 3）以“人类手动创建、手动排期、手动勾选”为中心。
而在 **Agent 原生 (Agent-Native)** 架构下，核心逻辑发生根本演进：

```
[日常上下文 (第一版：飞书 IM 文本/腾讯会议；后续：邮件/网页等)]
               ↓
     [Agent 结构化解析与意图提取]
               ↓
    [人机交接流与分级放行机制 (HITL Gate)]
         ↙                  ↘
[L1: 低风险直接归位]    [L2/L3: 待确认审批卡片]
         ↓                  ↓ (人类确认/修正)
[进入工作台/日程排期/多端提醒/跨 Agent 联合调度]
```

1. **输入端（第一版文本-only）**：人类无需打开事务软件手动打字，先通过飞书 IM 将腾讯会议邀约、会议号、待办文本或上下文摘要转发给 Agent；系统只处理文本，不处理图片、文件、录音或网页抓取。
2. **决策端（分级自主与人机交接）**：Agent 不是简单地往数据库塞一条文本，而是附带**原文证据、置信度、推断理由与结构化产物**；高风险或模糊事项通过轻量级审批卡片由人类一键放行或修正。
3. **执行端（状态透视与协同推进）**：清晰标识人类创建与各 Agent 创建的任务来源，第一版支持只读空闲插槽检索、专注事件铺垫与跨 Agent 联合调度基础；子步骤推进列为后续候选。

---

## 2. 日常上下文接入与智能解析引擎

### 2.1 腾讯会议 (Tencent Meeting) 专项解析机制

腾讯会议在日常办公与个人协同中存在两类典型上下文：**事前会议邀约** 与 **事后会议纪要/录制**。

#### A. 事前会议邀约解析（会议日程化）
- **输入样本**：
  > “某同事 邀请您参加腾讯会议
  > 会议主题：EventFlow Q3 架构评审与交付计划
  > 会议时间：2026-08-26 14:30-16:00 (GMT+08:00)
  > 点击链接入会：https://meeting.tencent.com/dm/AbCdEf1234
  > 会议号：987-654-321 密码：260824 ”
- **提取与归一化要素**：
  - `title`：“EventFlow Q3 架构评审与交付计划”（自动去除邀请人前缀）
  - `schedule`：`start_at: 2026-08-26T14:30:00+08:00`, `due_at: 2026-08-26T16:00:00+08:00`, `all_day: false`
  - `estimated_minutes`：90
  - `meeting_meta`：
    - `meeting_id`: `"987654321"`
    - `meeting_code`: `"260824"`
    - `join_url`: `"https://meeting.tencent.com/dm/AbCdEf1234"`
  - `reminder`：默认关联开会前 10 分钟提醒（外部飞书/ntfy + 应用内桌面通知）
  - `notes`：自动格式化入会信息（含一键直达短链与会议号密码）

#### A1. 第一版实现口径（链接、文本、会议号与 CLI）

第一版腾讯会议解析采用“两段式”策略：

1. **本地确定性文本解析（默认路径）**：从用户粘贴的会议邀约文本中提取 `会议主题`、`会议时间`、`会议号`、`密码`、`join_url`，不依赖外部网络或腾讯会议授权。
2. **CLI/API 只读补全（第一版纳入范围）**：当系统能够从文本、会议号输入或加入链接中拿到会议 ID 或会议号，且运行环境已安装并授权腾讯会议官方 `tmeet` CLI 时，调用 `tmeet meeting get --meeting-id ...` 或 `tmeet meeting get --meeting-code ...` 获取会议详情，并用返回的 `subject`、`start_time`、`end_time`、`join_url` 补齐结构化结果。

实现边界：

- 第一版必须支持“只有会议号”或“只有会议 ID”的输入；如果 CLI 可用且查询成功，应能补全会议主题与时间。
- 只给一个 `meeting.tencent.com/dm/...` 加入链接时，系统先尝试从链接或相邻文本提取会议号/会议 ID；若无法稳定提取，第一版不承诺自动反查主题和时间。
- 若解析结果缺少 `title`、`start_at`、`due_at` 中任一关键字段，不进入 L1 自动写入，改为 L2 proposal。
- `tmeet` 集成必须显式配置启用，并设置命令路径、执行超时和失败降级；OAuth token、refresh token、应用密钥等只允许存放在运行时 secret 环境或 `tmeet` 自身授权存储中，禁止写入项目文档或仓库。
- 第一版不调用 `tmeet` 的创建、更新、取消、录制、纪要、参会报告能力；这些能力如需接入，必须另行做权限与审批设计。
- 腾讯会议纪要、云录制、转写、智能纪要、截图/OCR action items 暂不进入第一版；后续如接入，也默认先产出 proposal。

服务端配置建议：

- `PERSONAL_AFFAIRS_TMEET_ENABLED=false`：默认关闭，只有明确启用后才调用 CLI。
- `PERSONAL_AFFAIRS_TMEET_BIN=tmeet`：CLI 可执行文件路径。
- `PERSONAL_AFFAIRS_TMEET_TIMEOUT_SECONDS=8`：单次查询超时；超时后降级为 L2 proposal。
- `PERSONAL_AFFAIRS_TMEET_HOME`：如需隔离授权缓存，指向服务端 secret/runtime 目录；不得放在项目仓库。
- `PERSONAL_AFFAIRS_TMEET_ALLOWED_COMMANDS=meeting:get`：第一版命令白名单，防止误调用写操作或录制/纪要读取。

后端查询流程：

1. 前端/API 接收文本、会议号、会议 ID 或链接。
2. 本地 parser 先尝试提取结构化字段。
3. 若缺少关键字段且 `PERSONAL_AFFAIRS_TMEET_ENABLED=true`，后端按白名单调用 `tmeet meeting get`。
4. 查询成功且字段完整时，按 L1/L2 规则创建正式日程或 proposal；查询失败、超时、未授权或字段仍不完整时，降级为 L2 proposal。

#### A2. 后续候选：腾讯会议自动同步（P2，不进第一版）

未来可在服务端增加“腾讯会议自动同步”后台任务，但该能力不进入第一版交付范围。

建议边界：

- 默认关闭，必须由用户在服务端配置和前端设置中双重启用。
- 只读拉取未来窗口内会议，例如未来 7 或 14 天；不做长期历史全量同步。
- 同步频率保持低频，例如 30 到 60 分钟；支持手动触发一次同步。
- 以 `meeting_id` 为主键，必要时辅以 `meeting_code` / `join_url` 做幂等去重，避免重复事项。
- 只自动创建确定性未来会议；若与已有日程冲突、缺少关键字段、会议取消、会议消失、查询失败，或对应事项已被用户手动编辑，则生成 L2/L3 proposal。
- 已同步事项应保存 `source_context.sync_meta`，包括 `meeting_id`、`meeting_code`、`last_synced_at`、`sync_status`、`last_lookup_status`，但不保存 OAuth token 或完整敏感凭据。

非目标：

- 不读取腾讯会议录制、转写、智能纪要、参会报告。
- 不通过 Personal Affairs 创建、更新或取消腾讯会议本身。
- 不自动删除或取消 Personal Affairs 事项；会议取消/消失只生成 proposal。

#### B. 事后会议纪要 / AI 录音解析（后续候选，不进第一版）
- **输入样本**：腾讯会议 AI 妙记链接、导出纪要文本或截图。
- **提取逻辑**：
  - 自动识别纪要中的「待办事项 (Action Items)」与「决议项」。
  - 识别任务分配给谁（若为当前用户，标记为高优先级 `planned`；若分配给他人，自动创建 `@人名` 的 `waiting` 等待跟进项）。
- **第一版处理**：不做自动解析；如由 Agent 或人工粘贴纪要内容，只能创建 L2 proposal，等待用户确认。

---

### 2.2 IM 聊天会话解析引擎（第一版仅飞书 IM 文本）

第一版 IM 接入仅处理飞书 IM 文本消息。微信、钉钉、图片、文件、语音和截图/OCR 不进入第一版。

飞书 IM 第一版接入方式：

- **被动事件接收**：机器人只接收用户主动发送给它或指定会话的文本消息。
- **独立入站路由**：新增 `POST /api/v1/integrations/feishu/im/events`，不复用 `/api/v1/webhooks` 出站订阅路由。
- **服务端签名校验**：校验飞书 challenge、签名、时间戳/nonce；失败直接拒绝，不进入 proposal 解析。
- **第一版用户映射**：通过服务端运行时配置绑定到一个 Personal Affairs 用户（例如默认 username / user_id）；暂不做多用户 Feishu identity 映射表。
- **不主动读取历史**：不调用聊天记录搜索，不扫描群历史，不轮询会话列表，不读取用户未转发的消息。
- **文本-only**：只处理纯文本与文本中的 URL；文件、图片、语音、卡片富文本、附件统一忽略或回复不支持。
- **幂等去重**：以飞书 `message_id` / `event_id` 加 `tenant/open_chat_id` 作为幂等键，避免事件重放导致重复 proposal。
- **权限边界**：飞书机器人只负责把文本转为 Personal Affairs proposal；除 L1 白名单会议邀约外，不直接写正式 `items`。

- **单条/多条合并聊天记录**：
  - 识别模式：
    1. **直接指令/约定**：“周四下午3点我们过一下方案” → 自动提取时间并关联对方为协作者。
    2. **等待他人交付**：“我明天上午把报表发你” → 自动识别为 `waiting` 状态，`waiting_on = 对方姓名`，`waiting_follow_up_date = 明天`。
    3. **模糊待办**：“有空看下这个链接” → 归入收集箱，并标记为低优先级待读。
- **聊天截图 / 图片转办**：
  - 后续候选能力；第一版不处理截图、图片或 OCR。

---

### 2.3 其他典型日常上下文（后续候选，不进第一版）

1. **邮件通知 (Email Ingestion)**：
   - 机票、火车票、酒店预订邮件 → 自动生成行程日程、地点与提前提醒。
   - 账单与信用卡还款邮件 → 生成到期还款事项。
2. **网页与知识剪贴 (Browser Extension / Share Sheet)**：
   - 浏览器插件一键抓取当前网页标题、URL 与选中文本，生成待阅读/待调研事项。

第一版处理：邮件、网页剪贴、浏览器插件、截图/OCR 均不接入；如未来接入，也默认先进入 `agent_proposals`，不得直接写正式事项。

---

## 3. 人机交接流与分级审批放行机制 (Human-in-the-Loop)

为了平衡“自动化效率”与“人类对日程/事务的掌控感”，建立 **三级自主放行策略 (Tiered Autonomy)**：

```
                    ┌─────────────────────────┐
                    │ Agent 提取生成候选事项  │
                    └────────────┬────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼
     【L1: 高置信度】       【L2: 中置信/模糊】     【L3: 高影响/破坏性】
  (会议邀约/确定性时间)   (口头约定/推断截止日)   (日程冲突/大范围改期)
           │                     │                     │
      自动写入生效          进入待确认状态          生成阻断式审批卡片
           │                     │                     │
      带 🤖 来源标识       展示在「今日/收集箱」   人类明确决策放行
```

### 3.1 分级放行规则 (Autonomy Tiers)

| 分级 | 判定场景 | Agent 动作 | 人类感知与交互 |
|---|---|---|---|
| **L1（自动放行）** | 确定性会议邀约，或受信 Agent 明确请求创建的低风险独立事项；必须无日程冲突、无既有实体改动、无敏感原文扩散 | 直接写入正式 `items`，设定默认提醒，并记录 `source_context` | 事项展示 Agent 来源标；进入今日/日历列表 |
| **L2（待复核）** | 飞书 IM 文本提取（意图置信度 0.7~0.9）、推断出的时间、未指定工作/个人范围 | 写入 `agent_proposals`，状态为 `pending`，不污染正式事项列表 | 收集箱顶部展示交接卡片，人类可点击 `[确认] / [修改后确认] / [忽略]` |
| **L3（强阻断审批）** | 变更既有重要日程、批量顺延任务、与现有日程严重冲突（重叠超30分钟） | 写入 `agent_proposals`，记录目标实体、拟变更 payload 与风险标记，暂不修改底层实体 | 今日页醒目弹出审批卡片，需人类点击 `[批准变更] / [拒绝]` |

### 3.1.1 Proposal 与正式事项边界

- `items.status` 继续只表达正式事项生命周期：`inbox` / `planned` / `in_progress` / `waiting` / `done` / `cancelled`。
- `agent_proposals.state` 表达候选提议审批生命周期：`pending` / `approved` / `edited_approved` / `rejected` / `ignored` / `expired`。
- L2/L3 proposal 在批准前不进入日历、今日必须处理、等待跟进、习惯统计、项目进度或提醒 worker 的正式计算。
- 批准 proposal 时，后端在同一事务内创建/修改 `items`、写入 activity、必要时挂提醒，并通过既有 event outbox 发出事件。

### 3.1.2 L1 初始白名单与升级规则

第一版 L1 自动写入仅覆盖两类场景：

1. **确定性会议邀约**：能够稳定解析 `title`、`start_at`、`due_at`、会议链接/会议号等关键字段，且与既有日程无明显冲突。
2. **受信 Agent 低风险创建**：Agent 明确调用创建独立事项，payload 含标题、范围、日期/时间等必要字段，不修改既有事项、不批量变更、不携带需要外发的敏感原文。

第一版默认不进入 L1 的场景：

- 飞书 IM 文本、后续更多 IM 聊天记录、邮件、网页剪贴、截图/OCR、会议纪要 action items。
- 任何 `update_item`、`reschedule_item`、`bulk_reschedule` 或影响已有事项/提醒/日程的动作。
- 时间、负责人、范围、任务归属或冲突判断不确定的解析结果。

后续只有当某一来源在真实使用中表现出高批准率、低编辑率、低拒绝率，并且隐私边界稳定时，才可从 proposal 升级为 L1 自动写入。

### 3.2 Web 端最小审批队列 (Handoff Queue)

第一版在「今日工作台」和「收集箱」顶部引入最小 **Agent 交接队列**，目标是把 `agent_proposals` 的审批闭环打通，而不是一次性实现复杂卡片编辑器。

展示内容：

- 来源与类型：`source_type`、L2/L3 分级、置信度、风险标记。
- 结构化结果：标题、范围、状态、优先级、日期/时间、备注摘要、会议号/链接等核心字段。
- 证据与理由：`evidence.raw_snippet` 折叠展示，`reasoning`、解析来源、冲突/缺失字段提示。
- 排序规则：L3 在前，其次按创建时间；同级可按风险标记和即将发生时间排序。

第一版动作：

- `[确认]`：按 proposal payload 创建或修改正式 `items`，并关闭 proposal。
- `[修改后确认]`：用户先编辑正式事项已有核心字段，再按编辑后的 payload 批准。
- `[忽略] / [拒绝]`：关闭 proposal，不修改正式事项；可选记录简短原因。

第一版不做：

- 不做批量审批、拖拽排期、复杂字段 diff、跨 proposal 合并、富文本编辑器或多步骤自动化编排。
- 不暴露任意 JSON 编辑给普通用户；调试信息可折叠只读展示。
- 不让 pending proposal 进入今日/日历/提醒统计，只有批准后才成为正式事项。

示意：

```
┌───────────────────────────────────────────────────────────┐
│ Agent 提议接入事项 · 飞书 IM · L2 · 置信度 0.86          [忽略] │
│ ───────────────────────────────────────────────────────── │
│ 📌 【会议】EventFlow Q3 架构评审与交付计划                  │
│ ⏰ 2026-08-26 14:30–16:00 (90分钟) · 腾讯会议 (987-654-321) │
│ 推断依据：从飞书 IM 文本中提取，无日程冲突；原文可展开       │
│ ───────────────────────────────────────────────────────── │
│ [修改后确认]                  [拒绝]        [确认并排期] │
└───────────────────────────────────────────────────────────┘
```

---

## 4. 更多 Agent 原生进阶能力设计

### 4.1 智能空闲插槽检索 (`pa_find_free_slots`)
- **功能**：调度 Agent（如协助约会议的助手）调用 MCP 工具 `pa_find_free_slots(duration=60, date_range=["2026-08-25", "2026-08-27"])`。
- **服务端计算**：自动剔除全天不可用时段、已有工作事项、腾讯会议、个人硬性日程，返回推荐的空闲时间段列表（如 `["2026-08-25 15:00-16:00", "2026-08-26 10:00-11:00"]`）。

第一版边界：

- 只读 MCP 工具，不写入 `items`、`agent_proposals` 或提醒。
- 仅基于 Personal Affairs 当前日历数据计算：定时 work/personal items、milestones、未来 L1 腾讯会议事项。
- 不接 Google Calendar、飞书日历、系统日历或腾讯会议自动同步结果之外的外部日历。
- 默认可用时间为工作日 `09:00-18:00`；参数可覆盖 `preferred_hours`、日期范围、最小时长和缓冲时间。
- 返回结构包含 `slots`、`conflicts`、`excluded_reasons`；Agent 如需排期，必须另行创建 proposal 或调用已有创建事项工具。

### 4.2 执行态上下文快照 (`pa_get_executive_briefing`)

第一版保留 `pa_get_executive_briefing`，但严格限定为只读聚合工具，用于让 Agent 在接手前拿到当前 Personal Affairs 的关键执行态。

返回建议：

- `generated_at` / `timezone` / `window`：快照生成时间、时区与查询窗口。
- `today_items`：今日 work/personal 事项，含标题、状态、优先级、时间、项目和 Agent 来源摘要。
- `overdue_items`：逾期未完成事项。
- `pending_proposals`：`agent_proposals.state = pending` 的待审批卡片摘要，按 L3/L2、创建时间和风险标记排序。
- `unseen_reminders`：已投递但未 ack 的提醒。
- `calendar_conflicts`：当前窗口内的硬冲突摘要，例如时间重叠、L1 会议与已有日程冲突。
- `focus_status`：如已有专注会话，可返回当前专注状态；没有则为 `null`。

第一版边界：

- 只读，不写入 `items`、`agent_proposals`、reminders 或 outbox。
- 不调用 LLM，不生成自然语言日报，不替代现有 `pa_daily_brief` prompt。
- 不接外部日历或外部会议自动同步；只基于 Personal Affairs 数据库当前事实。
- 返回结构化 JSON，排序规则固定且可测试，便于 Agent、CLI 或前端复用。

### 4.3 专注时段静默守门人 (Focus Shield Protocol)

第一版不做完整 Focus Shield 闭环，也不把 `focus.started` / `focus.ended` outbox 事件放入第一实现批次。

源码对齐判断：当前 focus start/stop 路径只负责写 `focus_sessions`；若增加出站事件，需要同时扩展后端事件类型、webhook 订阅选项和设置页事件列表。该能力与本版主线“飞书 IM 文本接入、proposal 审批、腾讯会议解析”不是同一交付链路，因此不作为第一版验收项。

后续候选能力：

- 飞书机器人收到 `focus.started` 后暂停普通提醒，只保留紧急/审批类消息。
- `focus.ended` 后汇总专注期间 proposal、提醒和外部消息。
- 多 Agent 统一遵守 Focus Shield 协议。

### 4.4 任务结构化拆解与进度流 (Subtasks / Checklists)

该能力不进入第一版。第一版不新增 `checklist_items` 表、不提供子任务排序/完成状态 API，也不扩展 MCP 工具让 Agent 直接更新子步骤进度。

后续候选能力：Agent 接收到宏观任务（如“完成服务器迁移评估”）时，可通过 MCP 挂载 3~5 个子检查项，并随着后台执行逐步打勾；人类在 Web 端详情中查看步骤进度。

第一版替代方案：Agent 可以把拆解建议写入 `agent_proposals.proposed_payload` / `evidence`，或在用户批准后写入正式事项 `notes`，但这些内容只是文本说明，不参与独立完成度、提醒、排序或统计。

---

## 5. 数据模型与接口扩展规范 (Technical Specification)

### 5.1 数据库模式扩展 (PostgreSQL Migrations)

#### 1. 事项增加 Actor 溯源字段（仅正式事项）
```sql
-- migration: 022_agent_native_handoff.sql
ALTER TABLE personal_affairs.items
  ADD COLUMN IF NOT EXISTS created_by_actor VARCHAR(80) DEFAULT 'human',
  ADD COLUMN IF NOT EXISTS updated_by_actor VARCHAR(80) DEFAULT 'human',
  ADD COLUMN IF NOT EXISTS source_context JSONB DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS execution_output JSONB DEFAULT NULL;
```

#### 2. Agent 提议队列（L2/L3 审批缓冲层）
```sql
-- migration: 022_agent_native_handoff.sql
CREATE TABLE IF NOT EXISTS personal_affairs.agent_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
  tier text NOT NULL CHECK (tier IN ('L1','L2','L3')),
  source_type text NOT NULL CHECK (source_type IN ('tencent_meeting','feishu_im','wechat_chat','email','web_clip','manual_agent','other')),
  proposed_action text NOT NULL CHECK (proposed_action IN ('create_item','update_item','reschedule_item','bulk_reschedule','create_waiting_item')),
  target_entity_type text,
  target_entity_id uuid,
  proposed_payload jsonb NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric(4,3) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  risk_flags text[] NOT NULL DEFAULT ARRAY[]::text[],
  state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','approved','edited_approved','rejected','ignored','expired')),
  decided_at timestamptz,
  decided_by_actor varchar(80),
  applied_item_id uuid REFERENCES personal_affairs.items(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_agent_proposal_target_for_update CHECK (
    proposed_action IN ('create_item','create_waiting_item')
    OR (target_entity_type IS NOT NULL AND target_entity_id IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS ix_agent_proposals_user_state
  ON personal_affairs.agent_proposals(user_id, state, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_agent_proposals_target
  ON personal_affairs.agent_proposals(user_id, target_entity_type, target_entity_id)
  WHERE target_entity_id IS NOT NULL;
```

#### 3. 入站事件幂等表（飞书 IM 文本入口）
```sql
-- migration: 022_agent_native_handoff.sql
CREATE TABLE IF NOT EXISTS personal_affairs.agent_ingest_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
  source_type text NOT NULL CHECK (source_type IN ('feishu_im')),
  tenant_key text NOT NULL,
  conversation_key text NOT NULL,
  event_id text,
  message_id text,
  sender_key text,
  payload_digest text NOT NULL,
  text_preview text,
  status text NOT NULL DEFAULT 'received' CHECK (status IN ('received','ignored','proposal_created','l1_applied','failed')),
  proposal_id uuid REFERENCES personal_affairs.agent_proposals(id) ON DELETE SET NULL,
  applied_item_id uuid REFERENCES personal_affairs.items(id) ON DELETE SET NULL,
  error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_agent_ingest_event_identity CHECK (event_id IS NOT NULL OR message_id IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_ingest_event
  ON personal_affairs.agent_ingest_events(
    source_type,
    tenant_key,
    conversation_key,
    COALESCE(event_id, ''),
    COALESCE(message_id, '')
  );

CREATE INDEX IF NOT EXISTS ix_agent_ingest_events_user_created
  ON personal_affairs.agent_ingest_events(user_id, created_at DESC);
```

说明：该表只记录幂等、审计和最小文本预览，不保存飞书 token、应用密钥、完整原始事件或不必要的聊天隐私内容。

#### 4. `source_context` / `evidence` JSONB 结构规范
```json
{
  "source_type": "tencent_meeting | feishu_im | wechat_chat | email | web_clip",
  "raw_snippet": "原始文本片段或转发消息...",
  "confidence": 0.95,
  "reasoning": "从会议链接中解析出会议号与起止时间",
  "external_url": "https://meeting.tencent.com/dm/AbCdEf1234",
  "meeting_meta": {
    "meeting_id": "987654321",
    "meeting_code": "260824",
    "join_url": "https://meeting.tencent.com/dm/AbCdEf1234"
  }
}
```

### 5.2 MCP 工具面扩展 (FastMCP Tools)

| 工具名 | 入参 | 功能说明 |
|---|---|---|
| `pa_propose_item` | `tier, source_type, proposed_action, proposed_payload, evidence, confidence, risk_flags` | 创建待复核 `agent_proposals`；默认不写正式 `items` |
| `pa_approve_proposal` | `proposal_id, edited_payload?` | 批准或修改后批准 proposal，并事务性创建/修改正式 `items` |
| `pa_reject_proposal` | `proposal_id, reason?` | 拒绝、忽略或关闭 proposal，不修改正式事项 |
| `pa_parse_meeting_invite` | `raw_text: str` | 第一版专用于解析腾讯会议文本、会议号、会议 ID 或链接并提取结构化字段 |
| `pa_get_executive_briefing` | `date?, window_days?, include_done?` | 只读返回今日事项、逾期、待审批 proposal、未处理提醒、冲突摘要和可选专注状态的结构化 JSON 快照；不生成 LLM 文案、不写数据 |
| `pa_find_free_slots` | `duration_minutes, date_range, preferred_hours, buffer_minutes?` | 只读检索 Personal Affairs 日历中的空闲可用时间段；不自动排期 |

---

## 6. 实施演进路线 (Roadmap)

1. **第一阶段：数据模式与提议队列**
   - 数据库应用 `022_agent_native_handoff.sql`（增加 `items` 溯源字段、`agent_proposals` 表与飞书 IM 入站幂等表 `agent_ingest_events`）；
   - REST API 支持 proposal 创建、列表、批准、修改后批准、拒绝/忽略。
2. **第二阶段：MCP 工具与确定性解析**
   - 增加 `pa_propose_item`、`pa_approve_proposal`、`pa_reject_proposal`、`pa_find_free_slots`、`pa_get_executive_briefing`；
   - 实现腾讯会议事前邀约解析器；默认走本地文本解析，纳入已授权 `tmeet` CLI 的只读会议详情补全。
   - IM 文本提取规则仅接收飞书 IM 文本，只产出 proposal payload，不进入第一版 L1 自动写入。
3. **第三阶段：飞书 IM 文本入口与 Web 端交接卡片**
   - 接入飞书 IM 文本消息入口，将会议邀约、会议号、待办文本或上下文摘要转为 proposal。
   - 在「今日」和「收集箱」顶部上线最小 Agent 审批队列，支持确认、修改后确认、忽略/拒绝；不做批量审批、复杂 diff 或拖拽排期。
   - 事项详情抽屉展示会议信息专用面板（一键唤起腾讯会议客户端/跳转入会）。
4. **后续候选：更多 IM / 邮件 / 网页 / OCR 来源**
   - 微信、钉钉、邮箱、网页剪贴、浏览器插件、截图/OCR 均延后，且默认 proposal-first。
5. **后续 P2：腾讯会议自动同步候选**
   - 服务端后台只读同步未来腾讯会议，默认关闭；按稳定会议键去重。
   - 自动创建仅限确定性未来会议；冲突、取消、失败、用户已编辑事项全部进入 proposal。
6. **后续 P2/P3：Subtasks / Checklists 候选**
   - 另行评估 `checklist_items` 数据模型、详情 UI、MCP 更新接口、排序/完成度语义和与正式事项统计的关系。

---

## 7. 源码对齐实施方案 (Source-Aligned Implementation Plan)

本设计与当前 `personal-affairs` 源码之间的差异主要是“计划能力尚未实现”，不是结构冲突。第一版实现应贴合现有分层，而不是绕开已有服务与仓储。

### 7.1 现有能力与设计差异判断

| 设计点 | 当前源码事实 | 判断 | 实施要求 |
|---|---|---|---|
| `agent_proposals` | 当前无 proposal 表、仓储、API 或前端类型 | 合理新增 | 用 `022_agent_native_handoff.sql` 添加独立队列，不改 `items.status` |
| 飞书 IM 入站 | 当前只有提醒投递的 `feishu_webhook_url` 配置和出站 `/webhooks` 订阅管理 | 需要分层 | 新增独立 integration route，不复用出站 webhook 路由 |
| 正式事项创建/修改 | `ItemService.create/patch` 已集中校验、activity、outbox、recurrence、people/tags | 必须复用 | proposal 批准路径调用 `ItemService`，不得直接写 `items` 绕过业务规则 |
| 幂等能力 | 现有 `create_requests` 支持 item 创建幂等，但不覆盖外部事件接收 | 部分可复用 | 创建事项可使用 `client_request_id = proposal:{id}`；飞书事件另建 `agent_ingest_events` 去重 |
| outbox / webhook | `event_outbox` 与 `/webhooks` 是对外投递事件，不是入站消息队列 | 不复用入站 | proposal 状态变化第一版不强制发出站事件；批准创建 item 会自然产生现有 `item.created` 事件 |
| Web 审批入口 | 前端已有 `TodayPage`、`InboxPage`、`api/client.ts` 和 React Query 模式 | 可复用 | 新增 `AgentProposalDeck` 组件，挂到 Today/Inbox 顶部；动作后 invalidate proposals/items/calendar/reminders |
| 执行态快照/空闲段 | 已有 `CalendarQueryService`、`RemindersRepository`、`FocusRepository` | 可复用 | 新增聚合 service/MCP tool，不复制日历查询逻辑 |
| Focus Shield | `focus.start/stop` 目前只写 `focus_sessions`，未写 outbox；前端 `WebhookEventType` 也没有 focus 事件 | 移出第一批 | 作为后续独立小改；若实现 `focus.started/ended`，需同步扩展后端 schema、`WebhookEventType` 与设置页事件选项 |

### 7.2 后端落点

- 新增 `storage/repositories/agent_proposals.py`：负责 proposal CRUD、pending 列表、状态流转和审批幂等。
- 新增 `storage/repositories/agent_ingest_events.py`：负责飞书事件去重、状态记录和 proposal/item 关联。
- 新增 `application/agent_proposal_service.py`：负责 `propose`、`approve`、`reject`；批准时在同一事务中调用 `ItemService.create/patch`，必要时调用 `ReminderService.upsert`。
- 新增 `application/meeting_invite_parser.py`：先做本地文本解析；字段不足且 `tmeet` 已启用时，调用受控 CLI 补全。
- 新增 `api/routes/agent_proposals.py`：提供 pending 列表、批准、修改后批准、拒绝/忽略；写接口复用 `require_csrf`。
- 新增 `api/routes/integrations_feishu.py`：提供飞书 challenge 与事件接收；使用独立签名校验，不依赖 cookie session / CSRF。
- 扩展 `config.py`：增加 `feishu_im_enabled`、`feishu_im_verification_token` / `encrypt_key`、`feishu_im_default_user_id` 或 `feishu_im_default_username`、`tmeet_*` 配置；所有 secret 仅来自 runtime env。
- 扩展 `ItemService` / `ItemsRepository`：支持服务层内部传入 `created_by_actor`、`updated_by_actor`、`source_context`、`execution_output`，但普通 REST item create/patch 不向前端暴露任意 source 写入能力。

### 7.3 前端落点

- 在 `frontend/src/api/client.ts` 增加 `AgentProposal` 类型，以及 `agentProposals()`、`approveProposal()`、`rejectProposal()` API 方法。
- 新增 `frontend/src/components/AgentProposalDeck.tsx`，复用现有轻量列表/按钮风格，展示来源、L2/L3、置信度、核心字段、折叠证据和冲突/缺失提示。
- `TodayPage` 顶部展示 L3 和即将发生的 pending proposals；`InboxPage` 顶部展示所有 L2/L3 pending proposals。
- 修改后确认第一版只用受控字段表单，不开放任意 JSON 编辑给普通用户。
- 审批动作成功后 invalidate `agent-proposals`、`items`、`calendar`、`reminder-health`、`reminder-deliveries`；如果生成 item，可打开对应事项抽屉。

### 7.4 测试与验收

- OpenAPI smoke：新增 `/api/v1/agent-proposals` 与 `/api/v1/integrations/feishu/im/events` 路径断言。
- MCP contract：新增 proposal、meeting parse、briefing、free slots 工具名断言。
- Repository/service tests：覆盖 proposal approve 只执行一次、重复飞书 event 不重复创建、修改后批准保留 `ItemService` 校验、拒绝不写正式事项。
- Frontend smoke：Today/Inbox 能展示 pending proposals，确认/拒绝后列表刷新，正式事项列表同步更新。
- 安全验收：仓库、OpenAPI 示例、前端 localStorage、webhook payload 中不得出现飞书 token、`tmeet` token、OAuth secret 或完整密钥。
