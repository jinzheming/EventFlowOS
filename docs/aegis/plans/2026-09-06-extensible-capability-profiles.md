# 2026-09-06 可拓展能力配置设计：External / LLM Profiles

## 状态

- 状态：开发中；第一版 `write_targets` 已作为兼容入口保留，第一版 `llm_profiles` / `llm_bindings` 已接入 `intake_normalization`，第一版 `external_profiles` / `external_bindings` 已作为通用外部集成层落地。
- 背景：飞书多维表格写入只是一个例子，真正需要沉淀的是“外部系统能力”和“LLM 能力”的统一配置方式。
- 目标：让用户可以在预置方案基础上覆盖目标、格式、映射和 Agent 行为说明，避免在代码、Prompt 或 Agent 中硬编码飞书链接、字段名、模型名或 provider 细节。

## 设计原则

1. **Preset 是默认，不是边界**：飞书多维表格、DeepSeek Flash、LiteLLM gateway 都只是内置 preset，用户必须可以新增或覆盖。
2. **能力优先于供应商**：先表达 `write` / `read` / `sync` / `notify` / `llm` / `lookup` 等能力，再绑定具体 provider。
3. **Profile 管连接，Binding 管用途**：连接层保存 provider、目标、凭据引用；绑定层保存用途、范围、映射、说明和优先级。
4. **Agent 可读且必须遵守**：Agent 在外部读写或调用 LLM 前，必须先读取 active profile/binding，并遵守其 instructions、mapping、format 和 scope。
5. **凭据不进业务配置**：数据库只保存 `auth_ref` 或虚拟 key 引用，不保存飞书 app secret、tenant token、LLM API key。
6. **可测试、可回退、可审计**：每个 profile/binding 都应支持 dry-run/test、fallback、last_used/last_error 和操作日志。

## 统一概念

| 概念 | 外部系统场景 | LLM 场景 |
| --- | --- | --- |
| `provider_key` | `feishu` / `notion` / `webhook` / `custom_http` | `litellm` / `openai_compatible` / `ollama` / `anthropic` |
| `capability` | `write` / `read` / `sync` / `notify` / `lookup` | `llm_chat` / `llm_json` / `llm_tool_use` / `llm_vision` |
| `preset_key` | `feishu_bitable` / `google_calendar` | `fast_structured` / `long_context` / `private_local` |
| `target_ref` | 表链接、日历 ID、Webhook URL、文档库路径 | base URL、gateway route、workspace model id |
| `format_key` | `personal_item_v1` / `calendar_event_v1` | `json_object_v1` / `tool_call_v1` / `summary_v1` |
| `mapping` | 内部字段到外部字段、枚举值映射 | 输入/输出 schema、response format、tool contract |
| `instructions` | 写入规则、冲突处理、目标表说明 | 模型用途、风格、审批边界、失败处理 |
| `scope` | 全局、项目、事项类型、来源、人员 | 全局、用途、来源、项目、风险等级 |

## 建议数据模型

### external_profiles

```sql
CREATE TABLE personal_affairs.external_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
  name text NOT NULL,
  provider_key text NOT NULL,
  preset_key text,
  capability text NOT NULL,
  auth_ref text,
  active boolean NOT NULL DEFAULT true,
  priority integer NOT NULL DEFAULT 100,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

### external_bindings

```sql
CREATE TABLE personal_affairs.external_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES personal_affairs.external_profiles(id) ON DELETE CASCADE,
  scope_type text NOT NULL DEFAULT 'global',
  scope_value text,
  target_ref text NOT NULL,
  format_key text NOT NULL,
  field_mapping jsonb NOT NULL DEFAULT '{}'::jsonb,
  value_mapping jsonb NOT NULL DEFAULT '{}'::jsonb,
  instructions text NOT NULL DEFAULT '',
  conflict_policy text NOT NULL DEFAULT 'ask',
  dry_run boolean NOT NULL DEFAULT false,
  last_used_at timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

### llm_profiles

```sql
CREATE TABLE personal_affairs.llm_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
  name text NOT NULL,
  provider_key text NOT NULL,
  preset_key text,
  base_url text,
  model_name text NOT NULL,
  auth_ref text,
  capabilities jsonb NOT NULL DEFAULT '{}'::jsonb,
  default_params jsonb NOT NULL DEFAULT '{}'::jsonb,
  fallback_profile_id uuid REFERENCES personal_affairs.llm_profiles(id) ON DELETE SET NULL,
  privacy_tier text NOT NULL DEFAULT 'standard',
  active boolean NOT NULL DEFAULT true,
  priority integer NOT NULL DEFAULT 100,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

### llm_bindings

```sql
CREATE TABLE personal_affairs.llm_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES personal_affairs.users(id) ON DELETE CASCADE,
  purpose_key text NOT NULL,
  scope_type text NOT NULL DEFAULT 'global',
  scope_value text,
  profile_id uuid NOT NULL REFERENCES personal_affairs.llm_profiles(id) ON DELETE CASCADE,
  override_params jsonb NOT NULL DEFAULT '{}'::jsonb,
  instructions text NOT NULL DEFAULT '',
  active boolean NOT NULL DEFAULT true,
  priority integer NOT NULL DEFAULT 100,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

## 当前代码迁移点

- `write_targets`：保留为 v0 API；运行源中 `024_write_targets.sql` / `025_llm_profiles.sql` / `026_external_profiles.sql` 顺序落库，其中 `026_external_profiles.sql` 会把现有写入目标迁移为 `external_profiles + external_bindings`，`target_type=feishu_bitable/custom` 映射到 `provider_key/preset_key/capability`。
- `llm_profiles + llm_bindings`：已新增 v1 API、设置页入口和 MCP 工具；`ItemIntakeNormalizer` 优先按 `purpose_key=intake_normalization` 读取用户绑定，找不到时回退 `intake_normalization_*` 环境变量。
- `external_profiles + external_bindings`：已新增 v1 API、设置页入口和 MCP 工具；新 Agent 应优先调用 `pa_resolve_external_bindings` / `pa_list_external_bindings`，旧 `pa_list_write_targets` 保留为 legacy-compatible 面。
- `pa_list_write_targets`：保留兼容；后续 adapter 完整切换后再考虑标记为 legacy alias。

## 适用场景

### 外部系统配置

- 飞书多维表格、Notion database、Google Sheet、Airtable、自定义 HTTP endpoint 写入。
- 日历同步，包括工作/个人事项、地点、参与人和提醒时间映射。
- 通知渠道，包括飞书机器人、Webhook、邮件、Push、ntfy。
- 外部来源读取，包括飞书 IM、邮件、会议纪要、Cubox、网页剪贴。
- 联系人、地点、标签、状态、优先级等外部字典映射。

### LLM 配置

- `intake_normalization`：快速录入归一化，优先使用低延迟、结构化能力稳定的模型。
- `proposal_extract`：从飞书 IM、会议文本、邮件等生成待审批提议。
- `daily_brief`：今日简报/日报，优先使用总结能力强且成本可控的模型。
- `meeting_parse`：会议邀约、会议纪要、action items 抽取，要求 JSON 输出稳定。
- `external_formatting`：写入外部系统前做格式化，但必须受 external binding 的 mapping 约束。
- `risk_review`：批量变更、冲突日程、高风险操作前的审查，可绑定更强模型或强制人工审批。

## 手动接口建议

### 外部集成页

- 一级列表：展示 profile，包括名称、provider、能力、active、priority、最近使用、最近错误。
- 二级绑定：展示 target、scope、format、mapping、conflict policy、instructions。
- 普通模式：用户从 preset 选择飞书多维表格/日历/Webhook 等，并填写链接或 ID。
- 高级模式：允许编辑 JSON mapping、value mapping、format key、instructions 和 dry-run。
- 测试按钮：执行 schema 校验和 dry-run，不直接写真实外部系统。

### AI 模型页

- 一级列表：展示模型 profile，包括 provider、model、capabilities、active、fallback、privacy tier。
- 用途绑定：按 `intake_normalization`、`proposal_extract`、`daily_brief`、`meeting_parse` 等用途选择模型。
- 普通模式：提供“快速便宜 / 结构化可靠 / 长上下文 / 本地隐私”等 preset。
- 高级模式：允许编辑 base URL、model name、temperature、max tokens、timeout、JSON/tool calling 能力、fallback。
- 测试按钮：验证连通性、JSON 输出、工具调用能力和超时配置。

## Agent 合约

### 外部系统

新增 MCP 工具建议：

```text
pa_list_external_profiles(capability?, provider?, scope?)
pa_get_external_profile(profile_id)
pa_get_external_profile_presets()
pa_validate_external_payload(profile_id, payload)
```

Agent 规则：

1. 任何外部写入、同步、通知、读取前，必须先读取 active external profile/binding。
2. 按 `capability + scope + priority` 选择目标；多个同优先级目标且说明不明确时，进入 dry-run 或询问用户。
3. 必须遵守 `target_ref`、`format_key`、`field_mapping`、`value_mapping`、`instructions` 和 `conflict_policy`。
4. 禁止硬编码飞书链接、表 ID、字段名、Webhook URL、日历 ID。
5. 凭据只通过 `auth_ref`、运行环境或外部 gateway 获取，不向事项正文、备注或外部 payload 泄露。

### LLM

新增 MCP/API 工具建议：

```text
pa_list_llm_profiles(active_only=true)
pa_get_llm_binding(purpose_key, scope?)
pa_get_llm_profile_presets()
pa_validate_llm_profile(profile_id)
```

Agent 规则：

1. 任何事项解析、摘要、提议、外部格式转换前，必须按 `purpose_key` 读取 active LLM binding。
2. 必须使用 binding 指定的 profile、params、capabilities、instructions 和 fallback。
3. 禁止硬编码模型名、provider、base URL 或 API key。
4. 如果 profile 不支持必要能力（如 JSON 输出、tool calling、vision），必须换 fallback、降级为人工确认，或只生成 proposal。
5. 对高风险事项修改，LLM 只能生成建议，不能绕过 `agent_proposals` / 人工审批边界。

## 开源方案参考

- **LiteLLM**：适合作为模型网关层，提供 OpenAI-compatible proxy、model list、router/fallback、virtual keys、logging、cost/rate-limit 等生产化能力。适合作为 `provider_key=litellm` 的默认后端。
- **Dify**：模型 provider 插件区分预置模型和可自定义模型，并把 provider credential、model schema、表单校验拆开。适合参考 preset + customizable 的配置体验。
- **Open WebUI**：Workspace Model 把 base model、system prompt、parameters、knowledge、tools 包成可复用模型。适合参考“面向用户的模型 preset”而不是暴露裸模型列表。
- **LangChain**：`init_chat_model` / runtime config / structured output / tool binding 展示了按运行时用途切换模型和能力的抽象。
- **AutoGen**：用 model client 抽象不同模型提供商，Agent 使用统一 client。适合参考 Agent 层不要直接绑定 provider SDK。

## 实施顺序

1. **命名收敛**：把 UI 文案从“写入目标”逐步上提为“外部集成 / 外部绑定”，保留 `write_targets` API 兼容。
2. **LLM v1**：新增 `llm_profiles + llm_bindings`，先接入 `intake_normalization`，env 保持 fallback。（已完成）
3. **External v1**：新增 `external_profiles + external_bindings`，把 `write_targets` 后台迁移进去。（已完成）
4. **MCP 合约**：新增通用 profile/binding 查询工具，旧工具作为 alias 保留一段时间。（已完成）
5. **测试与审计**：为 dry-run、fallback、scope 选择、Agent 工具合约和 OpenAPI schema 增加测试。
6. **UI 完整化**：外部集成页和 AI 模型页都支持普通模式、高级模式、测试按钮和最近错误展示。

## 部署验证

- 2026-09-07 已部署到 Tailnet 生产环境，最终镜像为 `personal-affairs-api:20260907125500-extensible-config-migrationfix` 和 `personal-affairs-web:20260907125500-extensible-config-migrationfix`。
- 生产迁移已执行到 `026_external_profiles.sql`；迁移 runner 现在会在每个 SQL 文件成功执行后写入 `schema_migrations`，`/api/v1/ready` 可稳定报告 `026_external_profiles`。
- 线上 smoke 覆盖 health/ready、Web 首页、预设读取、write target / external profile / external binding / LLM profile / LLM binding 创建解析删除，以及 MCP 工具列表。
- 本地验证覆盖后端 focused/full tests、后端 Ruff、前端 TypeScript、前端 node tests、Vite build 和 `git diff --check`；`backend/.venv` 已重建，常规 `uv --project backend ...` 命令恢复可用。

## Definition of Done

- 用户可以不用改代码就新增或覆盖外部目标和 LLM 选择。
- Agent 所需的外部目标、模型用途、字段映射、格式和说明都能通过 MCP/API 读取。
- 系统没有硬编码飞书表格链接、列名、模型名或 provider 凭据。
- 默认 preset 可开箱即用，自定义配置可通过 dry-run 验证。
- 高风险写操作仍进入 proposal/审批流，不因 LLM 或外部 profile 配置绕过人工控制。
