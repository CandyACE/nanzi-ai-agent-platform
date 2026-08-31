# 🎉 NanZi AI Agent Platform v1.0.13.0 Release Notes

**GitHub Repository**: [RandyChen1985/nanzi-ai-agent-platform](https://github.com/RandyChen1985/nanzi-ai-agent-platform)

v1.0.13.0 版本是一次以 **统一可复用结果链路与聊天会话一致性、Docker 沙箱交互式终端与公共文档隔离、8 大浏览器工具与验证码人工兜底、会话身份隔离、上下文手动压缩与工具调用超时治理** 为核心，并全面推进 **聊天防重复发送、六大业务中心流程引导、数据门户固化报表工作台、智能指标与实体关系双视图、开发环境生命周期管理、Kubernetes 部署资源、PostgreSQL 兼容性，以及流式防刷屏与模型重复输出保护** 的版本。

在本次更新中，平台打通「AI 分析产出 → 可复用结果统一协议 → 跨轮分析引用」的完整闭环，并重构了聊天消息与记忆的后台持久化、取消恢复与幂等防重复上送；上线 Docker 沙箱交互式终端、公共 `docs` 只读挂载与个人技能隔离、预构建流式日志；落地 8 大企业级浏览器工具与拟人化交互引擎、多模态验证码自解算、单击选定 + 双击执行的人机协同机制及云端缓存占用可视化；严格废除 Anonymous 降级，会话存储 / Redis / 工作区 / 审计全链路绑定真实用户并加固目录树与文件路径租户隔离；新增手动上下文压缩与比例控制、工具调用单次超时与总次数上限治理、工具权限卡片与执行时间线优化；同时大规模重构数据门户与固化报表、智能指标与实体关系双视图，补齐六大业务中心流程指引与规范弹窗、MCP 管理 CodeMirror 编辑器，并显著增强 PostgreSQL 的日期函数、业务指标 SQL、预览 SQL 反引号等方言兼容性。

本次变更范围自 `b8c207a776fc8d57538d35384e9d453188ae30d3`（不含，为 v1.0.12 末相关提交）至 `a1eb537f4aecfc20b1ac7588e24d9b0c64e978fc`（含），共 **147 个提交**（其中非 Merge 提交 124 个），涉及 507 个文件、约 65,019 行新增代码与 4,415 行删除。

---

## 🚀 Key Features

### 1. 🔁 统一可复用结果链路与跨轮分析引用 (Unified Reusable Result & Cross-Turn Reference)
*   **可复用结果统一协议**：构建 `build_reusable_result` / `is_reusable_result_candidate` / `resolve_reusable_result` 核心协议逻辑，统一 AI 分析产出的可复用结果判定、保存与消费路径，替代原先零散的结果处理。
*   **跨轮分析引用与决策路由**：`resolve_reusable_result` 在 reuse / fallback / none 之间形成清晰决策路径；`followup_data` 中统一写入经过协议封装的结果，本次实际复用结果会被显式标记，支持跨对话轮次的稳定引用。
*   **内存服务栈式存储**：`MemoryService` 新增 `get / set / push_reusable_result` 及 stack 操作，为可复用结果提供独立的缓存栈管理。
*   **配套测试与契约**：新增 `test_reusable_result.py`、`test_reusable_result_routing.py`、`test_assistant_agent_reusable_result.py`、`test_reusable_result_api.py`、`test_reusable_result_contract.py` 等全量测试。

### 2. 💬 聊天消息与记忆持久化重建、幂等门控与取消恢复 (Chat Persistence, Idempotency & Consistency)
*   **后端持久化与一致性修复**：优化聊天消息与记忆后台持久化，修复聊天取消与历史恢复不一致、浏览器会话状态同步错位；新增 `filter_tools_for_reusable_result` 与 `load_session_tool_artifact` 新路径；完善思考卡片历史持久化与终止轮对话上下文过滤。
*   **幂等防重复上送**：新增 `chat_request_idempotency.py`，基于 `client_request_id` 做幂等校验与去重；前端新增 `useChatSendGate` 发送门控 composable 与 `clientRequestId` 工具，杜绝重复发送。
*   **运行状态心跳与轮询**：`session_run_lane` 补充 run 状态管理与心跳机制，新增 `run-status` 端点支持前端轮询；前端 `useConversationRunStatus` 对话运行状态轮询 composable。
*   **统一错误响应与流式错误卡片**：新增 `error_response_service.py` 统一错误响应构建与分类，`streamErrorPresentation` 流式错误呈现工具，前端新增 `ErrorDetailCard.vue` 流式错误详情展示。
*   **正文完整性守护**：修复任务清单更新吞掉最终正文、处理 `todo_write` 后最终正文丢失，以及任务清单更新后正文还原等边界问题；修复历史消息数据产出计数恢复问题。
*   **移动端适配**：移动端收纳数据文件入口，优化消息底部操作入口。

### 3. 🧹 上下文手动压缩与体验优化 (Manual Context Compaction & UX)
*   **手动压缩与比例控制**：支持手动触发上下文压缩并控制压缩比例，配合既有自动溢出压缩，形成「自动 + 手动」双引擎。
*   **压缩记录卡片布局优化**：优化压缩记录卡片布局，精简智能压缩提示文案；全链路更新上下文压缩验收清单与测试。
*   **运行时能力发现与会话聚焦**：完善运行时能力发现（Runtime Capability Discovery）与会话聚焦，让模型与面板更清晰地聚焦当前会话所需能力。

### 4. 🛡️ 会话身份「Fail-Closed」隔离、全量工具透传与思考协议自适配 (Identity Isolation, Full Tool Passthrough & Thinking Protocol Adapter)
*   **严格会话身份隔离（Fail-Closed）**：彻底废除 `anonymous` 降级，会话存储、Redis 键、工作区与审计回退严格绑定真实有效的 `user_id`；`chat.py` 历史查询、截断与导出接口强校验用户身份，杜绝多租户数据越权与串线。
*   **全量工具透传与自主调度**：废弃死板的当前轮关键词动态裁剪门禁，将系统隐式工具 + 配置工具 + MCP 工具全量透传；保持原生多轮 User-Assistant 消息流，保障多轮追问、代词消歧与视觉多模态连续性。
*   **推理思考协议自适配**：原生支持 DeepSeek V4、Kimi、智谱、火山引擎、DashScope、SiliconFlow 等思考协议；兼容 DeepSeek V4 思考模式下强制 `tool_choice` 参数冲突，支持 400 重试与优雅降级。
*   **主备降级可见通知**：主模型调用失败触发 Fallback 时推送 `model_fallback` 结构化事件，优化换行防止引用块吞正文。

### 5. 🐳 Docker 沙箱交互式终端、公共文档隔离与预构建流式日志 (Docker Terminal, Public Docs Isolation & Prebuild Stream)
*   **Docker 交互式终端**：后端新增 `/api/v1/sandbox/docker/workspace` 下 `stop` / `restart` / `exec` 端点，支持停止容器、强制删除重建与容器内交互执行命令，并修复 aiodocker Stream 异步协议读取；前端新增 `DockerTerminalModal` 交互终端，支持实时输入执行、历史命令翻阅、快捷命令工具栏、一键清屏与复制，以及连续 `cd` 路径导航动画、默认最大化打开与关机过渡动效。
*   **结构化中文欢迎卡**：终端每次打开渲染含容器 ID、工作目录、文件与同步路径、资源限制与生命周期边界的彩色欢迎卡。
*   **公共 docs 只读挂载与技能隔离**：实现 Docker 沙箱公共 `docs` 只读挂载至 `/workspace/public/docs`，支持 DooD 路径转换；解耦个人技能源码目录与沙箱技能目录，仅挂载 `sandbox/skills`。
*   **预构建流式日志**：`docker_prebuild.py` 支持 aiodocker build stream 逐行事件推送，新增 `/prebuild-stream` SSE 端点；前端 SystemConfig 面板实时展示构建日志与进度条，镜像选择优先阿里云加速源。
*   **文件路径与命名空间收敛**：收敛沙箱文件路径命名空间、统一公共文档逻辑路径，修复 Docker 沙箱与文件工具路径映射，完善文件工具缺参可重试错误与路径预检防线，并设计容器路径读取的 Bash 降级方案。

### 6. 🌐 8 大企业级浏览器工具、验证码自解算与人机协同面板 (Enterprise Browser Tools, CAPTCHA Auto-Solve & Human-in-the-Loop)
*   **8 大企业级高级浏览器工具**：落地 8 大企业级浏览器工具与全局拟人化交互引擎，支持智能元素高亮检视、自适应低带宽压缩、页面滚动快照同步（顶部/底部直达 + 视口中心滚轮双保险）。
*   **多模态验证码自解算与人工兜底**：基于多模态大模型的验证码自解算，失败时无缝切换至人工协同兜底。
*   **单人选定 + 双击执行人机协同**：单击高亮元素轮廓并在状态栏展示 `[#ref]` 语义标签，双击确认执行，移除画面内黑底文字浮标，防止远程串流误触。
*   **缓存占用可视化**：浏览器面板与个人中心展示云端缓存磁盘占用大小（B/KB/MB/GB）与一键清除入口，两次点击确认清理 + 二次确认弹窗。
*   **浏览器环境诊断**：服务端浏览器环境缺失精准诊断、右下角版本检测与向导卡片；参数脱敏审计与会话运行时控制。
*   **人工输入悬浮岛**：悬浮岛居中展示，自动聚焦、Enter 发送 / Esc 关闭，标题动态展示聚焦输入框语义信息。

### 7. 🧭 六大业务中心全生命周期引导与规范大弹窗 (Guided Workflows & Standards Modal)
*   **智能体中心**：梳理定义 / 装配 / 版本发布 / 角色授权 / 调试消费 5 步流程；帮助说明明确系统自动路由、多智能体协同与发布前检查标准。
*   **知识库 / MCP / 任务调度 / 案例集**：KnowledgeFlowGuideBanner / McpFlowGuideBanner / TaskFlowGuideBanner / ExampleFlowGuideBanner 分别落地环境连通、连接协议与 Scope 权限、Cron 编排与审批模式、会话点赞沉淀闭环等指引。
*   **技能 / 提示词 / 数据源 / 记忆工作台**：补充各页面的帮助说明与规范弹窗，覆盖研发 5 步流、双轨归集、多源连接与向量索引等规范。
*   **统一折叠交互**：六大中心指引横幅统一「默认折叠」模式，页面顶部提供帮助入口与「显示流程指引」恢复入口；全局指引卡片防折行精修。

### 8. 📊 数据门户固化报表工作台重构与智能指标/关系双视图 (Data Portal Report Workbench & Dual-View Discovery)
*   **固化报表工作台重构**：数据门户抽屉顶部双 Tab（数据集与场景 / 固化报表）；主页恢复左侧 Aside 垂直导航（数据首页 / 固化报表 / 推荐场景 / 数据目录）；手工开发新建报表工作台支持选数据源 / 数据集、手写 / 粘贴 SQL、试跑测试 SQL、前 50 条预览与一键固化入库。
*   **CodeMirror 6 专业 SQL 编辑器**：升级固化报表编辑器为 CodeMirror 6，支持参数试跑独立选择器；全平台「黄金报表」更名「固化报表」。
*   **AI 保存报表上下文继承**：AI 保存报表时自动继承本轮查询关联的 data_source 与 dataset_id，避免回退默认源。
*   **智能指标 / 实体关系双视图升级**：支持按需选表、折叠、秒表计时与双视图 ER 图，补充智能发现更新指南与 FAQ。
*   **报表列表视图 / 推荐指标详情**：新增固化报表列表视图（卡片 / 列表切换）与推荐指标详情弹窗。
*   **云端缓存清理**：个人中心展示浏览器云端缓存占用并支持清理。

### 9. 🧰 工具调用超时治理、权限卡片与执行时间线优化 (Tool Timeout Governance, Permission Card & Timeline)
*   **单次工具调用超时配置**：新增全局 `agent_max_toolcall_timeout` 系统配置（默认 120s）与版本级 `toolcall_timeout_seconds` 字段，版本级配置优先于全局。
*   **工具调用总次数上限**：新增 `agent_tool_loop_global_limit` 系统配置（默认 50 次），防止工具循环空转。
*   **工具权限卡片与执行时间线**：新增 `ToolPermissionCard` 组件与 `toolPermissionDisplay` 工具模块；`ChatExecutionTimeline` 工具步骤显示 WrenchScrewdriverIcon 图标；优化执行阶段卡片渲染、Thinking 头部样式与动画。
*   **工具错误可观测性**：完善工具错误状态与原因展示，补齐工具错误观测测试清单。
*   **Shell 删除策略增强**：`shell_deletion_policy` 增加 Python / Node 脚本内删除调用识别；资源目录统计 `fetch_accessible_resource_counts` 与 `authorized_resource_scope` / `turn_resource_scope` 上报。

### 10. ⏳ 会话排队透明化与路由大模型超时保护 (Queue State Transparency & Router Timeout)
*   **并发排队状态透传**：`ConversationRunLane` 新增 `is_locked` 状态探测，上一轮任务未完成时通过 SSE 实时下发「等待上一次会话任务完成」进度日志，锁释放后自动完成并附带等待耗时，避免静默假死。
*   **路由大模型超时保护**：为未指定智能体时的路由大模型调用添加 15s 有界超时保护，超时重试后平滑回退兜底助手。
*   **思考定时器优化**：优先保持后端推送的活跃 pending 步骤文案，不被静态轮播粗暴冲刷；为排队状态添加专属沙漏图标。

### 11. 🔁 流式防刷屏与模型重复死循环熔断 (Stream Anti-Spam & Loop Circuit-Breaker)
*   **服务端流式防刷屏拦截**：新增服务端流式防刷屏拦截机制，优化流式重复检测算法，熔断阈值提升至 50 次并消除无标点误判。
*   **模型重复死循环熔断**：增加模型重复输出死循环熔断机制。
*   **软错误降级容错**：智能体工具执行软错误降级，捕获非致命异常并以 ToolChunk(ERROR) 返回大模型，杜绝 ExceptionGroup 中断会话；全局异常递归解包 `unwrap_exception_message`。

### 12. 🛠️ dev.sh 后台生命周期管理与 K8S 部署资源 (Dev.sh Lifecycle & K8S Deployment)
*   **dev.sh 生命周期管理**：新增 `./dev.sh status`（PID / Uvicorn 归属 / 端口监听 / health 检查）与 `./dev.sh stop`（优雅 TERM，超时 KILL，复核端口释放）；加固停止 / 状态判定的端口归属识别，兼容相对路径与 `python3 -m uvicorn` 包装形态，服务器缺 lsof 时依次回退 `ss → fuser`。
*   **一键开发环境**：统一开发环境搭建为一键 `dev.sh` 流程，自动安装前端依赖，补充本地联调前 `.env` 编辑说明。
*   **启动环境校验**：启动前校验 Node.js 与 npm 版本，自动准备开发运行环境，加强敏感信息脱敏。
*   **K8S 部署资源**：新增 Kubernetes 部署资源与文档，补齐归档版本克隆与版本对比、Docker 打包启动日志。

### 13. 🗄️ PostgreSQL 综合兼容性与前端契约 (PostgreSQL Compatibility & Contracts)
*   **日期函数兼容**：修复 PostgreSQL 日期函数兼容性。
*   **业务指标 SQL 方言**：修复 PostgreSQL 业务指标 SQL 方言兼容；预览 SQL 反引号标识符兼容（覆盖限定 / 分段标识符、字符串、注释与预览总数查询场景）。
*   **前端路由中文标题**：统一前端路由 `meta.title` 为中文，修复面包屑与标签页标题英文显示问题。
*   **前端契约测试**：`pytest --confcutdir=tests/frontend` 契约与 `vue-tsc --noEmit` 类型检查持续加固。

### 14. 🗂️ 平台自助意图识别、公共目录只读与应用工作区（Platform Self-Service & Public Docs）
*   **公共 docs 固化**：将根目录 FAQ.md 与 README.md 固化复制到 `data/docs/`，替代相对软链接，确保 Docker 构建及目录挂载完整可用。
*   **目录清单自愈**：支持 `list_accessible_directories` 目录清单工具，强化文件读写与路径防盲猜规范；FileNotFoundError / PermissionError / 越界错误自动注入目录清单自愈提示。
*   **租户目录隔离加固**：加固 `directory_tree_navigator` 目录树导航工具，普通用户直接导航他人私有工作区返回 403，递归遍历时自动剪枝其他用户私有工作区。
*   **平台自助意图识别**：扩展平台自助词表，精准识别多智能体并行、协同等特性解析意图；新增平台公共文档引导与全局提示词强化，明确禁止沙箱 Bash 访问公共文档。

### 15. 🧩 能力发现、MCP 与模型兼容容错（Capability Discovery, MCP & Model Compatibility）
*   **能力发现领域**：统一规范化 legacy `reasoning_effort` 字段映射；增加 Agent 执行观测与模型兼容容错。
*   **MCP 管理优化**：MCP 管理页面 UI 优化并引入 CodeMirror 编辑器，完善前端契约测试。
*   **入口配置一致性**：对齐确认卡片宽度，恢复技能安装帮助说明。

---

## 🐛 Bug Fixes

### 聊天会话 / 持久化 / 幂等
*   **后台永久化与恢复一致**：修复聊天消息与记忆后台持久化、聊天取消与历史恢复一致性问题，浏览器会话状态同步错位。
*   **正文丢失**：修复任务清单更新吞掉最终正文、处理 `todo_write` 后最终正文丢失，以及历史消息数据产出计数恢复。
*   **幂等防重复**：新增发送门控与 `client_request_id` 幂等去重，杜绝重复上送。

### 沙箱 / Docker / 文件路径
*   **路径映射**：修复 Docker 沙箱与文件工具路径映射，收敛沙箱文件路径命名空间、统一公共文档逻辑路径，设计容器路径读取 Bash 降级。
*   **文件工具容错**：文件工具缺参时返回可重试错误并补齐绕过路径预检的网络守护（缺参即拦截，不得绕过预检）。

### 浏览器自动化 / 人机协同
*   **交互与算法优化**：优化流式重复检测算法（熔断阈值 50 次、消除无标点误判）；切后台会话队列挂起自愈、退避轮询平滑自愈。
*   **远程滚动与快照同步**：增强远程页面滚动快照同步机制，翻页采用视口中心滚轮 + scrollBy 双保险。

### 数据库 / PostgreSQL
*   **日期函数 / SQL 方言 / 反引号**：修复 PostgreSQL 日期函数兼容性、业务指标 SQL 方言兼容，以及预览 SQL 反引号标识符兼容。
*   **查询闭环**：修复 ChatBI 查询总数统计错误、数据集歧义后无法继续查询、消息编辑重发会话记忆截断对齐、执行报表后结果未持久化（补充提交）。

### 工具 / 权限 / 分类
*   **工具分类修复**：修复 AgentManagement 工具自动分组匹配顺序，将 browser_ 提升至顶层并收窄 RAG 匹配，修正 browser_drag / browser_slider_drag 归类。
*   **废弃工具清理**：新增迁移彻底删除废弃的 search_github_repos 工具并清理任务中心示例。

### 部署 / 开发环境
*   **dev.sh 端口识别**：修复服务器缺少 lsof 时无法停止服务问题，加固端口归属识别，避免误判无关进程。
*   **启动校验**：启动前校验 Node.js / npm 版本，加强敏感信息脱敏。

---

## ⚠️ Breaking Changes & Migration Notes

> 从 v1.0.12 升级至 v1.0.13.0 时，请特别注意以下变更：

| 项目 | 说明 |
| :--- | :--- |
| **废弃工具清理 & 历史智能体主能力补齐** | 彻底删除 `search_github_repos` 工具；为历史智能体补齐类型对应的锁定主能力（复用运行时兼容旧行）；需执行 `db-prod/V130`、`V131` 或 `db-prod-pg/V30`、`V31` 增量迁移。 |
| **工具调用超时配置** | 新增全局 `agent_max_toolcall_timeout` 与版本级 `toolcall_timeout_seconds`；需执行 `db-prod/V132`、`V133` 或 `db-prod-pg/V32`、`V33` 增量迁移。 |
| **工具调用总次数上限** | 新增全局 `agent_tool_loop_global_limit`（默认 50）；需执行 `db-prod/V134` 或 `db-prod-pg/V34` 增量迁移。 |
| **会话身份 Fail-Closed** | 彻底废除 anonymous 降级；升级后的历史会话需由真实 `user_id` 接管，接口历史查询 / 截断 / 导出均已强校验身份。 |

---

## 🗄️ Database Incremental Upgrades (数据库增量升级说明)

### MySQL（`db-prod/`）

从 v1.0.12 升级至 v1.0.13.0，MySQL 主库引入 **5 个**增量脚本：

| 脚本文件 | 核心变更内容 |
| :--- | :--- |
| **[V130-delete_search_github_repos_tool.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V130-delete_search_github_repos_tool.sql)** | 删除废弃的 `search_github_repos` 通用 API 工具并清理引用。 |
| **[V131-add_agent_legacy_primary_capabilities.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V131-add_agent_legacy_primary_capabilities.sql)** | 为历史智能体按类型补齐锁定主能力（general_chat / data_query / knowledge_base），幂等执行。 |
| **[V132-add-agent-max-toolcall-timeout.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V132-add-agent-max-toolcall-timeout.sql)** | 新增全局单次工具调用超时配置 `agent_max_toolcall_timeout`（默认 120s）。 |
| **[V133-add-agent-version-toolcall-timeout.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V133-add-agent-version-toolcall-timeout.sql)** | `ai_agent_versions` 表新增版本级工具调用超时字段 `toolcall_timeout_seconds`。 |
| **[V134-add-agent-tool-loop-global-limit.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V134-add-agent-tool-loop-global-limit.sql)** | 新增单次对话工具调用总次数上限配置 `agent_tool_loop_global_limit`（默认 50）。 |

### PostgreSQL（`db-prod-pg/`）

PostgreSQL 对应的 5 个增量升级脚本如下：

| 脚本文件 | 核心变更内容 |
| :--- | :--- |
| **[V30-delete_search_github_repos_tool.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V30-delete_search_github_repos_tool.sql)** | 删除废弃的 `search_github_repos` 工具。 |
| **[V31-add_agent_legacy_primary_capabilities.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V31-add_agent_legacy_primary_capabilities.sql)** | 为历史智能体按类型补齐锁定主能力。 |
| **[V32-add-agent-max-toolcall-timeout.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V32-add-agent-max-toolcall-timeout.sql)** | 新增全局单次工具调用超时配置。 |
| **[V33-add-agent-version-toolcall-timeout.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V33-add-agent-version-toolcall-timeout.sql)** | `ai_agent_versions` 表新增版本级工具调用超时字段。 |
| **[V34-add-agent-tool-loop-global-limit.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V34-add-agent-tool-loop-global-limit.sql)** | 新增单次对话工具调用总次数上限配置。 |

---

## 🛠️ Upgrade Guide (升级指南)

### 方式一：源码直接升级（本地 / 虚机部署）

#### 1. MySQL 主库

```bash
# 1. 拉取最新代码
git fetch origin && git checkout main && git pull origin main

# 2. 执行数据库增量升级 (V130~V134)
./db-prod/apply-sql-native.sh

# 3. 启动/重启服务（dev.sh 会自动准备 uv/Python 3.11 环境、按需安装后端依赖，
#    自动感知前端依赖并执行 npm install；支持后台生命周期管理）
./dev.sh
```

#### 2. PostgreSQL 主库

```bash
# 配置 DATABASE_TYPE=postgresql 并执行迁移
./db-prod-pg/apply-sql.sh
```

---

### 方式二：Docker 容器化升级（生产环境 / 容器集群）

#### 1. 场景 A：下载官方 Release 镜像归档（推荐生产/离线环境）

从 [GitHub Releases v1.0.13.0](https://github.com/RandyChen1985/nanzi-ai-agent-platform/releases/tag/1.0.13.0) 下载对应架构的 Docker 镜像归档包：

```bash
# 1. 执行数据库迁移（使用宿主机或临时容器）
./db-prod/apply-sql-native.sh  # PG: ./db-prod-pg/apply-sql.sh

# 2. 导入 Docker 镜像归档（按服务器架构选择对应文件）
# x86_64 服务器
docker load -i nanzi-ai-agent_1.0.13.0_linux-amd64_*.tar

# ARM64 服务器（鲲鹏 / Ampere 等）
docker load -i nanzi-ai-agent_1.0.13.0_linux-arm64_*.tar

# 3. 检查镜像加载状态
docker images | grep nanzi-ai-agent

# 4. 启动 / 重启容器服务（默认挂载宿主机 docker.sock 支持 DooD 沙箱）
cd docker && ./start-nanzi-ai-agent.sh
# 或使用 compose 重启：docker-compose -f docker-compose.ai-agent.yml up -d --force-recreate
```

#### 2. 场景 B：本地 / 服务器自主构建镜像

```bash
# 1. 拉取最新代码并执行数据库迁移
git fetch origin && git checkout main && git pull origin main
./db-prod/apply-sql-native.sh  # PG: ./db-prod-pg/apply-sql.sh

# 2. 进入 docker 目录构建 v1.0.13.0 镜像
cd docker

# x86_64 Linux 服务器
./build_linux_x86.sh 1.0.13.0

# ARM64 Linux 服务器（鲲鹏 / Ampere / M 芯片）
./build_linux_arm.sh 1.0.13.0

# 3. 启动 / 重启容器服务
./start-nanzi-ai-agent.sh
```

---

## 💾 Downloads / Assets

本项目 v1.0.13.0 发布版本关联的源码、Docker 镜像资产归档包及配置文件如下：

* 📦 **Source Code (zip)**: `nanzi-ai-agent-platform-1.0.13.0.zip`
* 📦 **Source Code (tar.gz)**: `nanzi-ai-agent-platform-1.0.13.0.tar.gz`
* 🐳 **Docker Image for Linux amd64 (x86_64)**: `nanzi-ai-agent_1.0.13.0_linux-amd64_*.tar`
* 🐳 **Docker Image for Linux arm64 (aarch64)**: `nanzi-ai-agent_1.0.13.0_linux-arm64_*.tar`
* ⚙️ **Docker Compose YAML file**: `docker-compose.ai-agent.yml` / `docker-compose.yml`

🔗 **下载地址**: [GitHub Releases v1.0.13.0](https://github.com/RandyChen1985/nanzi-ai-agent-platform/releases/tag/1.0.13.0)

---

## ✅ Test Checklist

升级后建议验证以下核心场景：

- [ ] **统一可复用结果链路**：AI 分析产出通过 `build_reusable_result` / `resolve_reusable_result` 统一协议；跨轮分析可稳定引用上一次可复用结果，且本次实际复用结果被显式标记。
- [ ] **聊天持久化 / 幂等 / 取消恢复**：聊天消息与记忆后台持久化正常；取消后历史恢复一致；发送门控与 `client_request_id` 幂等去重生效，无重复上送；`todo_write` 后最终正文不丢失。
- [ ] **上下文手动压缩与比例控制**：手动触发压缩并控制比例；压缩记录卡片布局正常、提示精简；自动 + 手动压缩协同生效。
- [ ] **会话身份 Fail-Closed**：以真实用户身份访问历史、截断与导出接口均通过校验；Anonymous 不产生降级后可访问的数据。
- [ ] **Docker 沙箱交互式终端与公共文档隔离**：`stop / restart / exec` 端点正常；打开终端渲染中文欢迎卡，支持 cd 导航与快捷命令；公共 docs 只读挂载可见、个人技能目录隔离。
- [ ] **8 大浏览器工具与验证码自解算**：拟人化交互引擎、智能元素高亮、双击执行正常；多模态验证码可自解并支持人工兜底；面板与个人中心展示云端缓存占用并可清理。
- [ ] **工具调用超时与总次数上限**：全局 `agent_max_toolcall_timeout` 与版本级 `toolcall_timeout_seconds` 生效；`agent_tool_loop_global_limit`（默认 50）可拦截工具循环空转。
- [ ] **六大业务中心引导与规范弹窗**：全局可折叠指引横幅与帮助说明正常展示，版本 / 知识库 / MCP / 任务 / 案例集 / 技能 / 提示词 / 数据源 / 记忆中心均有对应引导。
- [ ] **数据门户固化报表与智能发现**：固化报表工作台试跑 SQL、CodeMirror 6 编辑器与参数试跑、AI 保存报表数据源继承；智能指标 / 实体关系双视图按需选表与折叠正常。
- [ ] **PostgreSQL 兼容**：日期函数、业务指标 SQL、预览 SQL 反引号标识符在 PostgreSQL 与 MySQL 下均无差异报错。
- [ ] **dev.sh 生命周期**：`./dev.sh status` / `./dev.sh stop` 在服务器缺 lsof 时正常（依次回退 ss → fuser）；K8S 部署资源文档可参考使用。
- [ ] **自动化测试回归**：运行 `PYTHONPATH=. pytest tests/`，前端契约测试 `pytest --confcutdir=tests/frontend`，前端类型检查 `vue-tsc --noEmit`，确保全量通过。

完整测试清单见 [tests/CHECKLIST.md](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/tests/CHECKLIST.md)。

---

## 📋 Commit Log

| Hash | 描述 |
| :--- | :--- |
| `a1eb537f` | fix: 限制审计链路大消息体积 |
| `5838fccc` | fix: 修复历史消息数据产出计数恢复 |
| `5e774708` | 修复: 移动端收纳数据文件入口 |
| `c1d5f563` | feat: 优化消息底部操作入口 |
| `496a7f14` | Merge pull request #143 · fix: 优化聊天持久化与可复用结果体验 |
| `e4cac1b3` | fix: 标记本次实际复用结果 |
| `daff740e` | fix: 优化聊天消息与记忆后台持久化 |
| `69121cb4` | fix: 修复聊天取消与历史恢复一致性 |
| `5558c5f8` | fix: 完善思考卡片历史持久化 |
| `05d4ca87` | fix: 过滤终止轮对话上下文 |
| `6b969ae9` | fix: 修复浏览器会话状态同步 |
| `2c05b22c` | fix: 修复处理 todo_write 后最终正文丢失 |
| `aa5cf0b2` | fix: 修复任务清单更新吞掉最终正文 |
| `410eb3c5` | Merge pull request #142 · feat: 统一可复用结果链路与跨轮分析引用 |
| `4661541e` | feat: 完成统一可复用结果链路 |
| `3735d6b9` | Merge pull request #141 · 修复 PostgreSQL 日期函数兼容性 |
| `487930ae` | 修复 PostgreSQL 日期函数兼容性 |
| `bd7e3f74` | Merge pull request #139 · 修复 PostgreSQL 业务指标 SQL 方言兼容 |
| `f325ba6d` | Merge pull request #140 · feat: 完善会话运行时能力与上下文压缩体验 |
| `598da4ee` | fix: 优化压缩记录卡片布局 |
| `cddb6c96` | fix: 精简智能压缩提示文案 |
| `8b976b3d` | feat: 优化上下文压缩体验 |
| `64a4f275` | feat: 支持手动上下文压缩与比例控制 |
| `7b753052` | feat: 完善运行时能力发现与会话聚焦 |
| `73871512` | fix: 统一公共文档逻辑路径 |
| `3e688a75` | fix: 收敛沙箱文件路径命名空间 |
| `bce19d13` | fix: 文件工具缺参绕过路径预检 |
| `452a7880` | fix: 文件工具缺参时返回可重试错误 |
| `c38577c0` | Merge pull request #138 · feat: 完善 Docker/DooD 沙箱文档、工具执行观测与 Office 工具触发 |
| `e2005902` | feat: 完善工具执行观测与 Office 工具触发 |
| `11dba2fc` | 前端: 默认折叠鉴权上下文准备步骤 |
| `1225966c` | 文档与前端: 完善 DooD 映射说明并折叠准备步骤 |
| `e19f15a7` | fix: 修复 Docker 沙箱与文件工具路径映射 |
| `5f19d117` | Merge pull request #137 · feat: 完善 AgentScope 工具超时、调度治理与浏览器能力 |
| `f006e436` | feat: 增加工具调用总次数上限配置 |
| `88e593a5` | feat: 完成智能体与平台功能更新 |
| `c04785bb` | 修复 PostgreSQL 业务指标 SQL 方言兼容 |
| `f6cb5b39` | Merge pull request #136 · 修复工具错误状态误判并完善错误原因展示 |
| `4e5b330a` | 修复: 完善工具错误状态与原因展示 |
| `0f781f21` | Merge pull request #135 · feat: 工具权限卡片、执行时间线优化、Shell 删除策略增强及资源目录统计 |
| `b65b6ab6` | feat: 工具权限卡片、执行时间线优化、Shell 删除策略增强及资源目录统计 |
| `746830e9` | fix: 对齐确认卡片宽度 |
| `9c83fa21` | feat: 恢复技能安装帮助说明 |
| `a98e50aa` | Merge pull request #132 · 修复 PostgreSQL 预览 SQL 的反引号标识符兼容 |
| `f92821af` | 修复 PostgreSQL 预览 SQL 的反引号标识符兼容 |
| `d870f06e` | feat(chat): 完善执行时间线阶段卡片展示逻辑 |
| `46ac0e54` | feat(chat): 修正执行时间线阶段卡片渲染细节 |
| `af749b38` | feat(chat): 优化执行时间线与 Thinking 头部展示 |
| `79a55a9f` | feat(chat): 聊天幂等性、错误响应服务、运行状态与执行时间线优化 |
| `96b0c39f` | test(ai): 补充并更新全量自动化测试用例 |
| `8f41ed34` | Merge pull request #131 · feat: 会话并发排队状态流式透传与路由大模型超时保护 |
| `d6671610` | feat(sandbox): Docker 预构建流式日志推送与 SystemConfig 前端状态增强 |
| `10809235` | feat(ai): 支持会话并发排队状态流式透传与路由大模型超时保护 |
| `0db3eee9` | Merge pull request #130 · feat: 加固会话身份隔离、全量工具透传、思考协议适配与模型降级通知 |
| `a9270460` | feat(ai): 加固会话身份隔离、全量工具透传、思考协议适配与模型降级通知 |
| `9a57e5a9` | fix: 加固 dev.sh 停止/状态判定的端口归属识别 |
| `d0bd727c` | Merge pull request #128 · feat: 归档版本克隆与对比、dev.sh 后台生命周期管理及部署文档完善 |
| `f7ec21a5` | feat: dev.sh 支持后台服务状态检查与生命周期管理 |
| `663c8253` | feat: 完善版本对比与部署配置 |
| `6954710d` | feat: 支持归档版本克隆并统一开发启动入口 |
| `1e7950c0` | Merge pull request #127 · fix: 加强开发环境启动校验与敏感信息脱敏 |
| `fcb0803b` | fix: 加强开发环境启动校验与敏感信息脱敏 |
| `472b23da` | feat: 自动准备开发运行环境并同步文档 |
| `e65ccd8b` | feat: 增加 K8S 部署资源和文档 |
| `68981fb6` | Merge pull request #126 · feat(ai): 统一规范化 legacy reasoning_effort 字段映射 |
| `3c1203d8` | feat(ai): 统一规范化 legacy reasoning_effort 字段映射 |
| `280489cb` | feat: MCP 管理页面 UI 优化、引入 CodeMirror 编辑器并完善相关前端契约测试 |
| `346aba69` | Merge pull request #125 · feat: 增加 Agent 执行观测与模型兼容容错 |
| `9ecf0b28` | feat: 增加 Agent 执行观测与模型兼容容错 |
| `b15b792e` | feat: 增加固化报表列表视图 |
| `75c0276d` | feat: 增加推荐指标详情弹窗 |
| `1e08197e` | Merge pull request #124 · feat: 完善报表运行说明与模型工具兼容 |
| `a9166edb` | feat: 完善报表运行说明与模型工具兼容 |
| `a16550d6` | feat(browser): 优化云端缓存清除弹窗交互与文案 |
| `31e5a6aa` | feat(browser): 浏览器面板与个人中心展示云端缓存占用大小及清理入口 |
| `b41bf769` | feat: 完善固化报表功能与界面 |
| `29dbfe29` | feat(sandbox): Docker 终端每次打开时渲染结构化中文欢迎卡片 |
| `bdebfdaa` | feat(portal): AI 保存报表时自动继承查询数据源上下文 |
| `600b471b` | Merge pull request #123 · feat(portal & metadata): 智能指标/关系发现全面升级双视图与选表、固化报表编辑器升级 CodeMirror 6 |
| `19c1ded1` | feat(portal): 升级固化报表编辑器为 CodeMirror 6 专业 SQL 编辑器与参数试跑独立选择器 |
| `10dd12c7` | feat(metadata): 智能指标发现与实体关系发现全面升级，支持按需选表、折叠、秒表计时与双视图 ER 图 |
| `a45e8e3f` | Merge pull request #122 · feat(portal): 数据门户抽屉/主页固化报表Tab重构、手工开发新建工作台与全平台更名 |
| `9e2be82c` | feat(portal): 数据门户抽屉/主页固化报表Tab重构、手工开发新建工作台与全平台更名 |
| `c46189eb` | feat(frontend): 落地技能工作台/提示词工坊/数据源管理/记忆工作台规范弹窗与卡片防折行排版优化 |
| `e79cac33` | feat(frontend): 全面落地六大业务中心全生命周期指引横幅与设计规范大弹窗 |
| `a242ae70` | feat(system-config): 系统配置增加未保存修改检测、顶部常驻保存操作与底部吸底浮动保存栏 |
| `bf719670` | Merge pull request #121 · docs(faq): 补充MySQL字符集、向量与知识库选型等指南 |
| `af6ae800` | docs(faq): 补充MySQL字符集、向量与知识库选型、首次安装检查清单、智能体路由权限及数据集新建指南 |
| `e7dd83dd` | feat(browser): 增加服务端浏览器环境缺失精准诊断、右下角版本检测与向导卡片 |
| `90d6e96b` | feat(browser): 优化人工输入悬浮岛居中展示并增强远程页面滚动快照同步机制 |
| `91640e2a` | feat(browser&routing): 优化浏览器面板人机选定与双击交互机制并支持意图路由阶段流式透传 |
| `469be23e` | fix(ai): 优化流式重复检测算法提升熔断阈值至50次并消除无标点误判 |
| `08a00879` | feat(browser): 完善浏览器自动化工具参数脱敏审计、会话运行时控制与面板优化 |
| `7dead780` | feat(runtime): 增加服务端流式防刷屏拦截与模型重复死循环熔断机制 |
| `1f36163d` | fix(agent): 智能体工具执行软错误降级与ExceptionGroup解包、浏览器输入识别及切后台自愈优化 |
| `2ceeb920` | Merge pull request #120 · feat(browser): 支持基于多模态大模型的验证码自解算与人工协同兜底 |
| `df7b587c` | feat(browser): 支持基于多模态大模型的验证码自解算与人工协同兜底 |
| `ca086ee1` | feat(sandbox): 完善 Docker 终端连续 cd 路径导航与关机过渡动效 |
| `da56b9e0` | feat(sandbox): 新增 Docker 沙箱操作列与交互式终端、思考卡片一键复制、工具分类修复与废弃工具清理 |
| `87e866a2` | feat(sandbox): 支持 Docker 沙箱公共 docs 只读挂载映射与个人技能隔离 |
| `7a6f23b0` | feat(browser): 落地8大企业级高级浏览器工具、全局拟人化交互引擎、智能元素高亮检视与自适应低带宽压缩 |
| `70a9142b` | feat(docs): 固化公共文档至 data/docs 并完善文件操作防盲猜与目录自愈引导 |
| `c717a331` | Merge pull request #119 · fix(frontend/security): 统一前端路由中文标题、平台特性自助导流与目录树租户隔离 |
| `57b7a69b` | fix(security): 加固 directory_tree_navigator 目录树导航工具的租户工作区隔离与跨租户防泄露 |
| `646f1a6d` | feat(ai): 增强平台自助与特性解释意图识别并优先引导宿主侧公共 docs 检索 |
| `996e30a3` | fix(frontend): 统一前端路由 meta 标题为中文并完善沙箱文件访问边界规范 |
| `dafbc18b` | feat(ai): 优化文件与目录工具引导机制与 list_accessible_directories 自愈闭环 |
| `5d473f00` | feat(workspace): 工作空间支持公共目录只读徽章标记与会话挂载交互规范 |
| `121c551f` | Merge pull request #118 · feat(ai): 新增 list_accessible_directories 目录清单工具、公共 docs 目录支持与 FAQ 扩充 |
