# 🎉 NanZi AI Agent Platform v1.0.12 Release Notes

**GitHub Repository**: [RandyChen1985/nanzi-ai-agent-platform](https://github.com/RandyChen1985/nanzi-ai-agent-platform)

v1.0.12 版本是一次以 **多策略安全沙箱与 Docker 预构建加速、服务端持久化浏览器会话与实时人机协同面板** 为核心领衔，并全面推进 **智能体上下文预算管控与溢出压缩、推理思考模型强制工具调用兼容层、AI 交付物工件与长效下载管理、AI 主动提问与全卡片折叠交互重构、子代理（Subagent）独立会话委派与层级时间线，以及元数据批量治理与聊天日志双 Tab 链路追踪** 的重磅里程碑版本。

在本次更新中，平台正式支持 `local`/`docker`/`e2b`/`ssh` 四大安全沙箱策略，实现 Docker 沙箱工作区宿主机同绝对路径挂载与分钟级镜像预构建加速；推出基于 Playwright 的服务端持久化浏览器会话与 WebSocket 实时画面流人机协同面板，支持拟人轨迹拖拽与 Stale 自动恢复；上线 `agent_context` 上下文预算管理、溢出压缩与输入框环形水位线浮标；构建 `tool_choice_for_model` 适配层，深度解决 DeepSeek-R1 / QwQ 等推理思考模型在强制工具调用时的死循环问题；上线 `publish_generated_file` 工件发布工具并将下载链接延长至 7 天；推出 `ask_user_question` AI 主动提问工具，并对工具权限卡、提问卡、业务确认卡与 TODO 任务清单进行全量折叠与状态自适应重构；完善子代理专属会话隔离与嵌套时间线回放；全面优化元数据批量删除与聊天日志「对话/轨迹」双 Tab 交互。

本次变更范围自 `43c634f4a72f26de7761e8e002b06c5c2c4caad1`（不含，为 v1.0.11 末相关提交）至 `091236a11707921a6bc66601b0b5220c43144fc3`（含），共 **59 个提交**（其中非 Merge 提交 52 个），涉及 352 个文件、约 46,162 行新增代码与 4,678 行删除。

---

## 🚀 Key Features

### 1. 🛡️ 安全沙箱多策略扩展与 Docker 预构建加速 (Sandbox Policies: Local/Docker/E2B/SSH & Image Prebuild)
*   **四大沙箱策略全面支持**：在系统配置【安全沙箱】分组中新增 `sandbox_policy` 策略体系，支持 `local`（默认，本机工作区）、`docker`（Docker 容器工作区）、`e2b`（E2B 远程安全沙箱）、`ssh`（SSH 远程主机工作区）四类策略，并针对不同策略动态展示专属配置项。
*   **Docker 沙箱工作区同绝对路径挂载**：解决容器内 `/workspace` 逻辑路径与宿主机用户工作区物理路径不一致导致的工具生成文件下载/预览错位问题；支持将用户宿主机工作区直接挂载至容器内相同绝对路径，同时软链 `/workspace` 保持向后兼容；容器内 MCP 工作目录与系统提示词动态适配真实路径。
*   **Docker 镜像预构建加速与自定义镜像**：针对 Docker 冷启动慢的问题，提供后台镜像预构建端点（`POST /api/v1/admin/sandbox/docker/prebuild`），将首次慢转变为分钟级预构建 + 秒级会话启动；新增 `sandbox_docker_manual_image_url` 支持配置自定义远程镜像；内置 Docker Hub、阿里云、华为云、腾讯云等同一 Python 镜像的多地域加速源预设。
*   **Bash 执行环境探测与安全警示**：后端 `get_env()` 自动探测服务运行环境（容器/宿主机），前端在输入框上方渲染自适应 Bash 执行环境横幅（`BashEnvBanner.vue`），非隔离宿主机执行时给出明确安全风险警示，支持一键折叠与本地持久化记忆。

### 2. 🌐 服务端持久化浏览器会话与右侧人机协同面板 (Persistent Browser Sessions & Interactive Panel)
*   **服务端持久化浏览器会话**：基于 Playwright 实现用户级持久化浏览器会话（`browser_open`/`browser_snapshot`/`browser_click`/`browser_fill`/`browser_slider_drag` 等套件与 `BrowserProfile`/`BrowserSession` 存储模型）。
*   **实时人机协同接管面板**：前端支持通过 WebSocket + Viewer Token 实时串流浏览器画面，支持用户直接点击、滚轮滚动、按键输入及输入框填充等实时协同接管操作。
*   **拟人滑块拖拽与执行期自愈恢复**：支持拟人滑块拖拽能力（`browser_slider_drag`），自动生成贝塞尔曲线缓入缓出拟人轨迹并模拟垂直抖动；增加元素交互就绪等待（`_ensure_actionable`）、动作后稳定等待（`_post_action_settle`）以及执行期 Transient Stale 异常自动刷新快照重试（`_run_with_stale_recovery`）。
*   **严格安全拦截与缓存抹除**：具备严格的 SSRF 防护（拦截私有网段/元数据 IP/内网主机名）、敏感输入参数脱敏与高风险提交确认拦截；个人中心与面板二次确认弹窗支持一键清除浏览器历史与缓存并物理抹除底层数据目录。

### 3. 🧠 上下文预算管控、历史溢出压缩与水位线浮标 (Context Compaction & Floating Telemetry)
*   **上下文预算管控与溢出压缩**：引入 `agent_context` 专属配置分组（包含预算上限 `agent_context_max_tokens` 默认 64k、历史溢出压缩 `agent_context_compaction_enabled`、压缩最大字符数限制与语义摘要开关）；当多轮历史逼近预算时，自动触发确定性摘录压缩与 LLM 语义摘要降级保障。
*   **摘要结构化解析与多模态识别增强**：新增 `_structured_tool_block` 结构化解析，优先保留工具名与输出核心结论（`->` 后的结果），剔除冗长入参和无用计数；单工具块独立截断配额，避免单条超长工具结果挤占整段摘要；多模态图片/附件载体包含名称时保留 `[图片: 文件名]`。
*   **输入框上下文水位线浮标**：在聊天输入框右上角增加渐变环形/徽标上下文水位线浮标，直观展示 Token 使用量、预算占比、使用状态徽标（「使用正常/接近上限/已达输入上限」）以及当前生效的沙箱策略；自适应显示「平台 Docker 容器内」或「宿主机」。
*   **模型调用上下文动态夹紧保护**：在 `ModelCallStatsMiddleware` 中增加 `_clamp_completion_to_context` 保护拦截，当请求输入 Token 逼近物理窗口时动态将 `max_tokens` 夹紧至可用空间，防止超出模型物理极限引发 API 报错。

### 4. 🧩 推理思考模型强制工具调用兼容层 (Thinking Model Tool Choice Compatibility)
*   **深度解决推理模型强制工具调用冲突**：解决推理模型（如 DeepSeek-R1 / QwQ 等）在强制工具调用场景下（如 ChatBI 意图生成或特定结构化阶段），如果模型先输出 `<think>` 思考块而未直出 tool_calls 导致的解析异常或死循环问题。
*   **tool_choice_for_model 适配层**：构建 `tool_choice_for_model` 适配层与 `ThinkingToolChoiceCompatAgent`，智能解析思考块并在流式分发与事件总线中规范化 tool_call 触发，兼顾深度思考与工具调用的强稳定性。

### 5. 📦 AI 交付物工件与长效下载管理 (AI Artifacts & Publish Generated File)
*   **生成文件发布工具（`publish_generated_file`）**：新增系统工具与 `ai_artifacts` 工件存储管理，支持智能体将本地/沙箱工作区生成的文件发布为平台下载工件。
*   **下载有效期延长与前缀配置**：生成文件下载链接默认有效期延长至 7 天；新增 `file_download_url_prefix` 系统配置项，支持自动合成工件的绝对/相对下载链接；系统提示词引导智能体生成交付物后主动调用。

### 6. 💬 AI 主动提问与全卡片折叠交互重构 (AI-Initiated Questioning & Collapsible Cards)
*   **AI 主动提问交互（`ask_user_question`）**：实现系统内置隐式工具 `ask_user_question`，支持单选/多选/补充输入；问题写入带 TTL 的 pending 状态并通过 SSE 独立出卡中断当前 ReAct，支持用户交互提交与取消硬拦截。
*   **确认框与提问卡展开/折叠与状态自适应**：工具权限确认卡（`pendingPermission`）、外部工具执行卡（`pendingExternalExecution`）、AI 提问卡（`UserQuestionCard`）与业务数据确认卡（`BusinessConfirmationCard`）统一增加展开/折叠交互；待处理默认展开，处理完成（approved/rejected/submitted/cancelled/stale）后自动折叠为紧凑单行，彻底解决长脚本霸屏。
*   **TODO 任务清单底部常驻与记忆关闭**：TODO 任务清单改为在输入框正上方常驻展示，任务项采用状态语义色；全部完成时自动折叠；引入基于 `localStorage` 的持久化记录，手动关闭后绝不重复弹出。

### 7. 🤝 子代理独立会话委派与层级时间线 (Subagent Delegation & Hierarchical Timeline)
*   **子代理专属会话隔离**：实现子智能体结构化元数据流式透传（run_id/depth/agent_name/display_name）；每次成功委派生成独立 `child_session_id`，子执行器使用子会话命名空间而不复用父 `conversation_id`，父子通过 `parent_conversation_id` 关联。
*   **多层嵌套时间线展示**：主会话过程时间线实现子代理步骤嵌套收拢至「调用子代理」父级容器下，支持子代理内部分析、SQL 与工具调用多层展开折叠；防止子代理过程旁白与主对话正文重复。
*   **可用智能体目录与委派前置发现**：新增系统隐式工具 `list_available_agents`，基于用户权限与就绪状态动态返回可用智能体轻量目录，便于智能体自主决策子任务委派。

### 8. 🗃️ 元数据批量治理与聊天日志双 Tab 链路追踪 (Metadata Batch Ops & Chat Logs Dual-Tab Trace)
*   **元数据批量删除与 N+1 消除**：元数据管理支持数据表/指标/关系批量删除，跨库关系短路优化与行级权限 N+1 查询消除。
*   **元数据详情页紧凑布局**：容器间距与边距紧凑化，实体关系列表改源表/目标表分两行展示（物理表名加粗 + 业务中文名）。
*   **聊天日志双 Tab 与链路时间标注**：聊天日志右侧详情区新增「对话」与「轨迹」双 Tab 切换，所有 Step 节点补充 `HH:mm:ss` 触发时间展示。
*   **Toast 柔和淡彩与微磨砂重构**：采用微光淡彩渐变 + 状态色环境弥散阴影 + 实心小徽标（`rounded-2xl`），视觉层次大幅提升。

---

## 🐛 Bug Fixes

### 沙箱 / Docker / 执行环境
*   **沙箱路径错位修复**：修复 Docker 容器内 `/workspace` 路径与宿主机用户工作区物理路径不一致导致的文件找不到或工件无法下载问题。
*   **Docker 预构建状态标记**：修复 Docker 预构建状态标记在不同加速源切换时未即时刷新的问题。
*   **Bash 环境横幅提示**：修复在本地宿主机运行时缺乏明确安全隔离风险提示的问题。
*   **系统配置卡片下拉遮挡**：修复系统配置页卡片项较少时，自定义多行下拉框展开被外层卡片 `overflow-hidden` 截断遮挡的问题。

### 浏览器会话 / 人机协同
*   **长事务锁超时修复**：修复浏览器 Profile 初始化时 `get_or_create_default` 在高并发下的数据库锁争用与超时问题。
*   **页面 Stale 元素自愈**：修复自动化执行中页面刷新或 DOM 变更引起的 Transient Stale 异常，实现自动刷新快照与动作重试。
*   **地址栏协议补全**：修复浏览器面板地址栏输入未加协议的网址时偶发跳转失败的问题，自动补全 `https://` 前缀。
*   **面板轮询频率优化**：将浏览器面板自动轮询间隔降至 5 秒，并在 AI 触发动作时即时触发快照刷新。

### 上下文管理 / 思考模型
*   **思考模型强制工具调用死循环**：修复 DeepSeek-R1 / QwQ 等思考模型在强约束 JSON 场景下先输出 `<think>` 导致的无法解析与死循环问题。
*   **单次输出预留溢出**：修复长上下文下 `max_tokens` 超出模型物理上下文上限引发的 API 调用失败问题，增加动态夹紧。
*   **模型管理上下文清空保存**：修复在模型管理弹窗中清空输入上下文或输出上限时，因空字符串未转换为 `null` 导致的 Pydantic 校验失败问题。
*   **消息编辑重发记忆截断**：修复前端编辑历史消息重发后服务端 Redis 记忆未同步截断导致的历史污染问题。

### 前端交互 / 提问卡 / 任务清单
*   **提问与确认卡霸屏**：修复复杂流程中多张长脚本或参数卡片展开导致的界面过度拉长问题，统一支持折叠与状态自适应收起。
*   **TODO 清单关闭重复弹出**：修复 TODO 任务清单手动关闭后在后续轮次中重复弹出的问题，引入 `localStorage` 持久化记忆。
*   **AI 补全描述弹窗关闭**：修复元数据管理在「确认 AI 补全描述？」二次确认框中点击「开始生成」时确认框未及时关闭的问题。
*   **生成文件私有链接 Host 补全**：修复相对路径下载链接在部分场景下缺少 Host 前缀导致无法直接点击的问题。

---

## ⚠️ Breaking Changes & Migration Notes

> 从 v1.0.11 升级至 v1.0.12 时，请特别注意以下变更：

| 项目 | 说明 |
| :--- | :--- |
| **安全沙箱多策略配置** | 系统配置新增 `sandbox_policy` 分组与相关配置项；需执行 `db-prod/V127`~`V128` 或 `db-prod-pg/V27`~`V28` 增量迁移脚本。 |
| **服务端浏览器会话持久化** | 新增浏览器会话与 Profile 存储表；需执行 `db-prod/V122` 或 `db-prod-pg/V22` 增量迁移脚本。 |
| **AI 交付物工件与文件下载前缀** | 新增 `ai_artifacts` 工件表与 `file_download_url_prefix` 系统配置；需执行 `db-prod/V124`、`V129` 或 `db-prod-pg/V24`、`V29` 增量迁移脚本。 |
| **上下文预算管控系统配置** | 系统配置新增 `agent_context_*` 预算与压缩配置项；需执行 `db-prod/V126` 或 `db-prod-pg/V26` 增量迁移脚本。 |
| **指标标签与执行历史输出标记** | 历史表与指标表扩展字段；需执行 `db-prod/V123`、`V125` 或 `db-prod-pg/V23`、`V25` 增量迁移脚本。 |

---

## 🗄️ Database Incremental Upgrades (数据库增量升级说明)

### MySQL（`db-prod/`）

从 v1.0.11 升级至 v1.0.12，MySQL 主库引入 **8 个**增量脚本：

| 脚本文件 | 核心变更内容 |
| :--- | :--- |
| **[V122-browser-session.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V122-browser-session.sql)** | 新增服务端持久化浏览器会话表 `ai_browser_sessions` 与配置表 `ai_browser_profiles`。 |
| **[V123-add-has-data-output-to-history.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V123-add-has-data-output-to-history.sql)** | 执行历史表 `ai_agent_execution_history` 增加 `has_data_output` 数据产出标记字段。 |
| **[V124-create-ai-artifacts.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V124-create-ai-artifacts.sql)** | 新增 AI 生成文件与交付物工件表 `ai_artifacts`。 |
| **[V125-add-metric-tags.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V125-add-metric-tags.sql)** | 指标表 `metadata_metrics` 增加 `tags` 标签字段。 |
| **[V126-add_context_management_configs.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V126-add_context_management_configs.sql)** | 系统配置新增上下文预算上限与历史溢出压缩配置项。 |
| **[V127-add-sandbox_policy_configs.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V127-add-sandbox_policy_configs.sql)** | 系统配置新增安全沙箱多策略（`local`/`docker`/`e2b`/`ssh`）配置项。 |
| **[V128-add-sandbox_manual_image_url.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V128-add-sandbox_manual_image_url.sql)** | 系统配置新增 Docker 沙箱自定义远程镜像地址配置 `sandbox_docker_manual_image_url`。 |
| **[V129-add_download_url_prefix_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V129-add_download_url_prefix_config.sql)** | 系统配置新增生成文件下载链接前缀配置 `file_download_url_prefix`。 |

### PostgreSQL（`db-prod-pg/`）

PostgreSQL 对应的 8 个增量升级脚本如下：

| 脚本文件 | 核心变更内容 |
| :--- | :--- |
| **[V22-browser-session.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V22-browser-session.sql)** | 新增服务端持久化浏览器会话表与配置表。 |
| **[V23-add-has-data-output-to-history.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V23-add-has-data-output-to-history.sql)** | 执行历史表增加 `has_data_output` 数据产出标记字段。 |
| **[V24-create-ai-artifacts.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V24-create-ai-artifacts.sql)** | 新增 AI 生成文件与交付物工件表 `ai_artifacts`。 |
| **[V25-add-metric-tags.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V25-add-metric-tags.sql)** | 指标表增加 `tags` 标签字段。 |
| **[V26-add_context_management_configs.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V26-add_context_management_configs.sql)** | 系统配置新增上下文预算上限与历史溢出压缩配置项。 |
| **[V27-add-sandbox_policy_configs.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V27-add-sandbox_policy_configs.sql)** | 系统配置新增安全沙箱多策略配置项。 |
| **[V28-add-sandbox_manual_image_url.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V28-add-sandbox_manual_image_url.sql)** | 系统配置新增 Docker 沙箱自定义远程镜像地址配置。 |
| **[V29-add_download_url_prefix_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V29-add_download_url_prefix_config.sql)** | 系统配置新增生成文件下载链接前缀配置。 |

---

## 🛠️ Upgrade Guide (升级指南)

### 方式一：源码直接升级（本地 / 虚机部署）

#### 1. MySQL 主库

```bash
# 1. 拉取最新代码
git fetch origin && git checkout main && git pull origin main

# 2. 更新 Python 依赖
source .venv/bin/activate
pip install -r requirements.txt

# 3. 执行数据库增量升级 (V122~V129)
./db-prod/apply-sql-native.sh

# 4. 重新编译前端并启动服务
cd frontend && npm install && npm run build && cd ..
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

从 [GitHub Releases v1.0.12](https://github.com/RandyChen1985/nanzi-ai-agent-platform/releases/tag/1.0.12) 下载对应架构的 Docker 镜像归档包：

```bash
# 1. 执行数据库迁移（使用宿主机或临时容器）
./db-prod/apply-sql-native.sh  # PG: ./db-prod-pg/apply-sql.sh

# 2. 导入 Docker 镜像归档（按服务器架构选择对应文件）
# x86_64 服务器
docker load -i nanzi-ai-agent_1.0.12_linux-amd64_*.tar

# ARM64 服务器（鲲鹏 / Ampere 等）
docker load -i nanzi-ai-agent_1.0.12_linux-arm64_*.tar

# 3. 检查镜像加载状态
docker images | grep nanzi-ai-agent

# 4. 启动 / 重启容器服务
cd docker && ./start-nanzi-ai-agent.sh
# 或使用 compose 重启：docker-compose -f docker-compose.ai-agent.yml up -d --force-recreate
```

#### 2. 场景 B：本地 / 服务器自主构建镜像

```bash
# 1. 拉取最新代码并执行数据库迁移
git fetch origin && git checkout main && git pull origin main
./db-prod/apply-sql-native.sh  # PG: ./db-prod-pg/apply-sql.sh

# 2. 进入 docker 目录构建 v1.0.12 镜像
cd docker

# x86_64 Linux 服务器
./build_linux_x86.sh 1.0.12

# ARM64 Linux 服务器（鲲鹏 / Ampere / M 芯片）
./build_linux_arm.sh 1.0.12

# 3. 启动 / 重启容器服务
./start-nanzi-ai-agent.sh
```

---

## 💾 Downloads / Assets

本项目 v1.0.12 发布版本关联的源码、Docker 镜像资产归档包及配置文件如下：

* 📦 **Source Code (zip)**: `nanzi-ai-agent-platform-1.0.12.zip`
* 📦 **Source Code (tar.gz)**: `nanzi-ai-agent-platform-1.0.12.tar.gz`
* 🐳 **Docker Image for Linux amd64 (x86_64)**: `nanzi-ai-agent_1.0.12_linux-amd64_*.tar`
* 🐳 **Docker Image for Linux arm64 (aarch64)**: `nanzi-ai-agent_1.0.12_linux-arm64_*.tar`
* ⚙️ **Docker Compose YAML file**: `docker-compose.ai-agent.yml` / `docker-compose.yml`

🔗 **下载地址**: [GitHub Releases v1.0.12](https://github.com/RandyChen1985/nanzi-ai-agent-platform/releases/tag/1.0.12)

---

## ✅ Test Checklist

升级后建议验证以下核心场景：

- [ ] **安全沙箱多策略与挂载**：系统配置中切换 `local` / `docker` / `e2b` / `ssh` 策略；Docker 模式下验证工作区宿主机同绝对路径挂载及文件生成；预构建状态正常展示；本地运行时正常展示宿主机风险提示横幅。
- [ ] **服务端浏览器会话与人机接管**：AI 执行浏览器工具时右侧面板画面实时推流；可手动点击/拖拽/打字接管；拟人滑块拖拽轨迹自然；个人中心可一键清除浏览器缓存并物理抹除。
- [ ] **上下文预算管控与水位线**：聊天输入框右上角环形水位线浮标正常显示当前 Token 用量与沙箱环境；长多轮对话触发溢出压缩时，摘要保留工具核心结论与图片文件名；单次输出预留不溢出物理窗口。
- [ ] **思考模型工具兼容**：使用 DeepSeek-R1 / QwQ 等思考模型在强约束工具调用场景下生成正常，无 `<think>` 块解析死循环。
- [ ] **工件发布与长效下载**：智能体生成交付物文件后调用 `publish_generated_file` 发布为下载工件；工件列表与详情链接有效（默认 7 天）。
- [ ] **AI 提问卡与全卡片折叠**：触发 `ask_user_question` 正常出卡并能交互提交/取消；权限确认卡、执行卡、业务确认卡在处理完成后自动折叠为单行；TODO 任务清单在全部完成后自动折叠且手动关闭后不重复弹出。
- [ ] **子代理委派与层级时间线**：调用子代理时生成专属 `child_session_id`，过程时间线内部分析与工具调用支持多层展开折叠；`list_available_agents` 正常返回可用列表。
- [ ] **元数据批量治理与日志双 Tab**：数据表/指标/关系支持批量勾选删除；聊天日志右侧详情区支持「对话」与「轨迹」双 Tab 平滑切换，步骤带有触发时间戳。
- [ ] **自动化测试回归**：运行 `PYTHONPATH=. pytest tests/`，确保测试全量通过。

完整测试清单见 [tests/CHECKLIST.md](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/tests/CHECKLIST.md)。

---

## 📋 Commit Log

| Hash | 描述 |
| :--- | :--- |
| `091236a1` | feat(ai): 优化上下文溢出压缩摘要结构化解析与多模态附件识别 |
| `18fb5c65` | feat: 增加上下文压缩观测界面 |
| `e9d2aa9e` | Merge pull request #113 from RandyChen1985/dev-agentscope |
| `41e5cc7e` | feat(frontend): 优化输入框上下文浮标详情展示并对齐Docker预构建状态归一化 |
| `899dcb30` | feat(chat): 输入框上下文浮标支持沙箱执行环境自适应展示并补齐单测与契约 |
| `f3a904ab` | feat(ai/tools): 将生成文件下载链接默认有效期延长至7天并补充单测 |
| `be993126` | feat(sandbox): 实现 Docker 沙箱工作区同绝对路径挂载与路径一致性 |
| `7dd5acdb` | feat(sandbox): 新增生成文件发布工件工具与沙箱预构建增强及手动镜像配置 |
| `3882001e` | Merge pull request #112 from RandyChen1985/dev-agentscope |
| `82edb9fe` | docs: 更新自动化测试清单 tests/CHECKLIST.md |
| `72eb4719` | feat: 增加推理思考模型强制工具调用兼容层 (tool_choice_for_model) |
| `f6f316bd` | feat: 支持安全沙箱多策略(local/docker/e2b/ssh)与Docker预构建、输入框上下文浮标与系统配置折叠布局优化 |
| `76544896` | fix(frontend): 优化上下文水位线并隐藏内部标签 |
| `024917aa` | fix: align context budget with completion reserve |
| `589d57a8` | feat: 支持智能体上下文管理与溢出压缩、Bash执行环境横幅提示与模型管理上下文置空修复 |
| `7a0f5848` | docs: 新增 Bash 环境探测与输入框风险横幅设计文档 |
| `7f7a1b70` | feat: 工具确认框、AI提问卡与业务确认卡支持展开折叠与状态自适应 |
| `4ac378c8` | feat: 浏览器会话增强滑块拟人轨迹拖拽、元素可用性等待与执行期 Stale 恢复重试 |
| `17849683` | fix: 修复数据集 AI 补全描述确认弹窗点击开始生成后未关闭的问题 |
| `da7054f5` | Merge pull request #111 from RandyChen1985/dev-agentscope |
| `eed38eef` | feat: 元数据详情页紧凑布局优化、实体关系列表表名两行展示与变更日志时间线视图支持 |
| `88b73523` | feat: 优化 Todo 任务清单底部常驻、完成自动折叠与持久化关闭，增加快捷指令折叠引导与产物抽屉 |
| `f989c29f` | feat: 元数据管理支持数据表/指标/关系批量删除、跨库关系短路优化与行级权限N+1消除 |
| `41e3c01d` | feat: list_available_agents 包含自身并新增 is_current 标识，个人中心浏览器缓存清除增加二次确认弹窗 |
| `9a4d74a8` | feat: 新增 list_available_agents 目录工具、多智能体协同配置分组、路由追问粘性及 Toast 遮罩样式优化 |
| `638e36d3` | docs: 新增公众号连载 A07 用户工作空间与目录隔离全景指南并顺延后续篇目 |
| `a74a4d24` | Merge pull request #110 from RandyChen1985/dev-agentscope |
| `36ebab52` | feat(browser): 扩展浏览器自动化工具套件支持滚动/按键/悬停/文件操作/多标签页等能力 |
| `5d6c409f` | feat(browser): 浏览器面板地址栏支持自动补全https协议前缀 |
| `ce923051` | perf(browser): 降低面板轮询间隔至5秒并支持AI动作触发即时刷新 |
| `4d91338d` | feat(mcp): 支持MCP三步向导与发布引导，放开同地址多命名空间注册及全待发布提示 |
| `d5c21e37` | Merge pull request #109 from RandyChen1985/dev-agentscope |
| `c39b6e25` | feat(ai): 知识库目录门禁与精准检索路由强化 |
| `269cdb3e` | fix(chat): 修复消息编辑重发与会话记忆截断对齐问题 |
| `8e7580ea` | Merge pull request #108 from RandyChen1985/dev-agentscope |
| `37706325` | fix(browser): 优化防反爬指纹伪装、多快照LRU缓存与数据库长事务锁竞争 |
| `e5ca4feb` | feat(browser): 完善浏览器人机协同接管控制流与输入交互 |
| `9920ecc0` | fix(chatbi): 修复数据集歧义后无法继续查询 |
| `c53a0393` | fix(browser): 优化浏览器导航竞争、页面快照重试与指针拖拽交互 |
| `88df5df1` | fix(chatbi): 修复 ChatBI 查询总数统计错误 |
| `66b885c7` | fix(browser): 优化浏览器自动刷新控制为手动开关并移除鼠标聚焦误触发 |
| `cf90922c` | fix(browser): 优化浏览器输入权限判定、自动刷新暂停与会话关闭交互 |
| `4a0fe812` | feat(browser): 实现服务端持久化浏览器会话与前端右侧实时交互面板 |
| `e6c8c9cd` | fix(chat): 优化活跃任务清单计算范围仅绑定当前最新正在生成的消息 |
| `66e6d19e` | feat(chat): 思考卡展开信息新增复制浮标与 TODO 任务清单底部常驻交互优化 |
| `85384488` | feat(ai): 优化 ask_user_question 主动互动触发策略与多助手协同 |
| `189c7846` | fix(ai): 智能体未显式指定知识库时合并绑定知识库与用户权限知识库 |
| `581ec55d` | Merge pull request #106 from RandyChen1985/dev-agentscope |
| `23771a09` | fix(frontend): 补全生成文件私有下载链接 Host 并支持裸链接可点击渲染 |
| `fa67d525` | feat: 支持 Todo 任务清单工具与工具预检批量并行子代理委派 |
| `488a93ad` | fix(ai): 优化用户提问回执前置语义与取消消息标头展示 |
| `8f6da3e0` | feat(ai): 实现内置工具 ask_user_question 主动提问与选项交互 |
| `5b90d1e7` | feat(ai): 完善子代理独立会话与委派链路 |
| `d0762997` | fix(timeline): 实现子代理步骤嵌套收拢与历史会话回放展示 |
| `e9cbfe78` | feat(ai): 实现子代理委派协议与时间线展示优化并集成图片读取工具 |
| `1e34b466` | feat(ui): 聊天日志支持「对话/轨迹」双Tab切换与执行链路触发时间标注 |
| `f13ed894` | style(ui): 重构 Toast 提示为淡彩微磨砂与环境光质感，优化资源目录样本库过滤 |
| `aa5270c8` | feat(ai): 增加用户可访问资源目录提示，优化智能路由与提示词资产感知 |
| `2c11969e` | refactor(ai): 收敛单轨路由决策至 TurnDecision，优化 Prompt 分段组装与子代理委派协议 |
