# EventFlowOS 开发现状

详细开发需求、接口契约和验收标准见 [development-requirements.md](development-requirements.md)。

更新日期：2026-09-07

## 范围声明

EventFlowOS 在当前仓库中指「个人事务管理系统」：围绕个人工作事项、个人事项、项目、日程提醒、协作等待、复盘、Agent 辅助录入与自托管部署形成的应用。本文不包含、也不沿用旧的「事件链拆分」实验方案。

## 当前定位

- **产品形态**：自托管、单操作者优先的个人事务管理 OS。
- **技术形态**：FastAPI + PostgreSQL 后端，React/Vite 前端，Docker/Nginx 部署，MCP 暴露 Agent 原生访问接口。
- **发布状态**：早期 `0.1.0-beta` 预览候选；适合个人可控环境部署，不按多租户 SaaS 宣传。
- **兼容边界**：公开品牌使用 EventFlowOS；内部包名、CLI、镜像名、OpenAPI 文件名和 `PERSONAL_AFFAIRS_*` 环境变量暂保持稳定。

## 分类进展

### 1. 事项核心

已实现：

- 工作事项与个人事项统一建模，支持 `inbox / planned / waiting / done / cancelled` 等生命周期状态。
- 事项支持标题、备注、优先级、起止时间、全天/非全天、预估耗时、归档、软删除、恢复和彻底删除。
- 事项变更支持乐观锁与幂等创建，避免重复写入和覆盖并发更新。
- 等待对象与协作人已从自由文本升级为 people 目录及 item-person 关系。
- 标签支持两级层级、置顶、按标签查看关联事项。

后续建议：

- 增加线上/线下地点字段，与腾讯会议、本地地址和地图解析打通。
- 增加更明确的事项来源字段展示，例如人工创建、飞书导入、会议解析、Agent 建议。

### 2. 时间与提醒

已实现：

- 今日视图汇总当前/接下来、今天必须处理、等待跟进、阻塞项目、未排期事项。
- 日历页支持周/月视图、拖拽排期、调整时长、ICS 订阅 token。
- 提醒规则、提醒投递、ack、snooze、retry/dead 状态和健康诊断已具备基础闭环。
- 支持浏览器桌面通知、Web Push subscription、飞书 webhook、ntfy 等可选投递路径。
- 支持早晚摘要偏好与摘要发送日志。

后续建议：

- 增加提醒渠道的端到端可观测面板，统一显示最近投递、失败原因、下一次重试。
- 将地点解析后的线上会议/线下地址纳入日历与提醒文本。

### 3. 项目与复盘

已实现：

- 项目支持目标、状态、健康度、进度模式、风险摘要、下一步、复盘时间、截止日期和颜色。
- 项目里程碑、项目更新、项目分组和项目关联事项已经落库并暴露 API。
- 周复盘是可开关功能，聚合逾期、等待、项目风险、已完成与专注/习惯洞察。
- 今日页能够把阻塞项目和项目下一步纳入主工作台。

后续建议：

- 增加项目健康度自动建议：基于逾期事项、等待时间、里程碑完成度生成候选状态。
- 增加复盘结论沉淀入口，把复盘动作转化为下周事项或项目更新。

### 4. 前端体验

已实现：

- 前端采用 React/Vite + TanStack Query，页面包括今日、收集箱、工作事项、个人事项、项目、日历、标签、设置、复盘。
- 抽屉式编辑、快速添加、搜索、批量操作、撤销、快捷键帮助、保存视图等日常高频操作已覆盖。
- PWA manifest、Service Worker、图标资源和响应式布局基础已具备。
- UI 文案已切到 EventFlowOS 品牌，登录页强调「个人事务管理」。

后续建议：

- 把快速添加能力扩展为自然语言解析入口，输出待确认的结构化事项草稿。
- 在个人事项创建/编辑页增加线上/线下地点能力，地址解析只由用户显式触发。

### 5. 后端与数据层

已实现：

- 后端采用 FastAPI，集中注册 system、auth、items、projects、calendar、reminders、preferences、tags、people、export、push、webhooks、agent proposals 等路由。
- PostgreSQL migration 已推进到 `022_agent_native_handoff.sql`，覆盖初始模型、等待字段、重复规则、复盘、桌面通知、标签层级、预估耗时、people、软删除、push、项目分组、习惯、摘要、保存视图、PAT、事件 outbox、webhook、Agent handoff。
- Repository + Unit of Work 结构已经覆盖 items、projects、people、tags、reminders、preferences、focus、habits、tokens、webhooks、event outbox、agent proposals。
- 生产边界包含 Host allowlist、CSRF、PAT scope、问题详情响应、请求 ID 和基础 rate limit。

后续建议：

- 为新地点能力新增幂等 migration，避免直接塞入 notes/source_context 导致后续查询困难。
- 对 webhook DNS rebinding 和分布式 rate limit 做生产级增强。

### 6. Agent 与集成

已实现：

- Agent proposal 队列支持 create、approve、edit approve、reject、ignore，并能落正式事项。
- Feishu IM 集成为被动文本 callback 入口，默认关闭，支持 URL verification、签名/加密校验、去重和 proposal 创建。
- 腾讯会议邀请解析已能提取主题、时间、会议号、密码、入会链接；`tmeet` 只作为后端只读增强，默认关闭。
- MCP server 已暴露事项、people、提醒、日历、会议解析、提案审批、executive briefing、free slot 等工具。
- Outbound webhook 通过 event outbox + worker 形成至少一次投递链路，并默认拒绝不安全目标地址。
- **设计中**：以工作任务为聚合单位的虚拟 Workspace 与时间线证据查询；项目本身作为内置 Project Workspace，跨项目按任务集合组合，并通过只读 MCP 提供给 Agent。当前仅完成需求与前后端契约设计，尚未迁移或实现。

后续建议：

- 将线上会议解析结果从 notes 迁移为正式 location/meeting 字段。
- 增加 Agent 建议的风险分层策略：L1 可自动落库，L2/L3 必须人工确认。

### 7. 部署、开源与 GitHub

已实现：

- `infra/` 包含 API/Web Dockerfile、开发与服务端 compose、Nginx 配置和带确认门槛的部署脚本。
- `docs/deployment.md` 覆盖生产配置、Host/headers/body limits、rate limiting、webhook 边界、备份与发布检查。
- `.github/` 包含 CI、CodeQL、Dependabot、issue templates、PR template。
- `docs/open-source-readiness.md` 已整理开源候选边界、已完成加固、验证证据和剩余风险。

后续建议：

- GitHub 仓库描述建议使用：`Self-hosted personal affairs management OS for tasks, reminders, projects, reviews, and agent-assisted capture.`
- Topics 建议：`personal-productivity`, `task-management`, `self-hosted`, `fastapi`, `react`, `postgresql`, `mcp`, `agent-workflow`。

## 当前验证覆盖

- 后端测试覆盖 domain policy、API smoke、recurrence schema、people policy、tags policy、rate limit、Feishu ingestion、Tencent Meeting parser、tmeet adapter、MCP contract、Agent proposal、Agent context、webhook contract。
- 前端验证以 TypeScript build/lint 为主，当前 package 脚本中 `test` 和 `lint` 都执行 `tsc -b`。
- CI 覆盖 backend tests/Ruff/Pyright、frontend audit/lint/build、compose validation、Docker build、CodeQL 和 secret scanning。

## 下一阶段建议

优先级从高到低：

1. **地点与会议正式字段**：为个人事项增加 `location_type / online_url / meeting_provider / meeting_id / address / address_granularity / geo`，腾讯会议先本地解析，地图只点击解析。
2. **Agent 写入安全策略**：落地 L1/L2/L3 风险分层，减少低风险人工确认成本，同时保留高风险审批。
3. **提醒可靠性面板**：把 delivery、worker、channel、retry、dead letter 的状态集中到设置或诊断页。
4. **端到端验证**：补充 Playwright/浏览器级用例，覆盖登录、创建事项、提醒、日历拖拽、proposal 审批。
5. **生产发布门槛**：从新 clone 重新跑完整验证，确认 GitHub branch protection、secret scanning、Dependabot alerts 已开启后再打 tag。
6. **虚拟 Workspace**：按 [设计文档](aegis/plans/2026-09-21-virtual-workspace-analysis-design.md) 实现跨项目时间线查询、证据包和只读 MCP 工具；前后端共用同一查询契约。
