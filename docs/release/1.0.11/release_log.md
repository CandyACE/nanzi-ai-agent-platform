# 🎉 NanZi AI Agent Platform v1.0.11 Release Notes

**GitHub Repository**: [RandyChen1985/nanzi-ai-agent-platform](https://github.com/RandyChen1985/nanzi-ai-agent-platform)

v1.0.11 版本是一次以 **AgentScope 2.0.6 深度升级与通用业务数据确认卡（Human-in-the-Loop）** 为核心领衔，并全面推进 **双重路由优化与意图识别合并、非多模态模型图片旁路解析、思考卡过程话术入卡与时间线历史回放、Embed Ticket 临时嵌入凭证体系与 24h 滑动续期、ChatBI 明细/依据/引用多维交互与健壮性收口，以及工作空间与任务中心体验优化** 的重磅里程碑版本。

在本次更新中，平台全面升级至 AgentScope 2.0.6，接入结构化输出、权限中间件与运行时状态可配置注入；落地通用业务数据确认卡（`request_user_confirmation`）与模型驱动回传机制，支持交互式字段修改与取消硬拦截；将独立意图识别收拢合并至单次路由 LLM 调用，并引入单候选/业务确认回执短路；新增系统默认多模态模型配置（`multimodal_model_name`），支持纯文本大模型无缝旁路解析图片；过程话术收拢入折叠思考卡，新增 `process_timeline` 快照字段支持历史会话全景回放；新增 Embed Ticket 代客签发与白名单权限校验，Session Token 支持 24 小时滑动续期；ChatBI 气泡下方聚合明细/依据/引用合一面板，大结果集抽样（500 行）与自动缓存合成收口；工作空间 Bash 工具严格绑定会话目录，站内通知支持 Mermaid 与 ECharts 富文本渲染。

本次变更范围自 `89e88d493c3d7298f10227862a2f986c1ae6641e`（不含，为 v1.0.10 末相关提交）至 `2c8a3fbf00e42d7681329ee44243a41ef6be64b2`（含），共 **53 个提交**（其中非 Merge 提交 45 个），涉及 229 个文件、约 20,320 行新增代码与 2,312 行删除。

---

## 🚀 Key Features

### 1. 🤖 AgentScope 2.0.6 深度集成与内核优势 (AgentScope 2.0.6 & Runtime State Injection)
*   **内核升级与优势**：主编排框架升级至 AgentScope 2.0.6，带来多项关键架构进化与性能跃升：
    *   **原生结构化输出（Structured Output）**：底层深度接入严格 JSON Schema 强约束生成，替代易受幻觉干扰的松散文本正则匹配，使 ChatBI 语义意图解析与多轮状态分类的解析准确率提升至接近 100%。
    *   **洋葱圈架构中间件（Onion-chain Middleware）**：利用 2.0.6 的中间件钩子系统（`extra_agent_middlewares`），实现 `ToolPermissionMiddleware`（工具级权限预检与禁用策略硬拦截）和 `ModelCallStatsMiddleware`（调用耗时与 Token 统计）的无侵入挂载，大幅强化多智能体执行安全与审计能力。
    *   **流式聚合与 ReAct 轮次治理**：底层以片段聚合（Fragment Joining）替代高频字符串拼接，彻底修复工具错误态处理、多次工具并发调用的状态重置以及推理-行动（Reasoning-acting）轮次计数偏差，显著提升高并发流式输出稳定性。
*   **可配置运行时状态注入（`InjectionConfig`）**：新增系统配置 `agentscope_inject_runtime_state` 与 `agentscope_inject_time_interval_hours`，支持向 Agent 运行上下文按需注入当前时间、任务态及上下文占用，时区精准绑定平台全局时区 `platform_timezone`，且与工具链/HITL 完全解耦。
*   **会话事实工具与思考调优**：新增平台只读 `session_status` 工具，供模型在长对话中精准查询当前会话事实（时间、模型、权限、任务态等）；关闭思考模式时显式传递 `false`，全面对齐各模型厂商的思考参数下发协议。

### 2. ⏱️ 思考卡演进：过程话术入卡与时间线历史回放 (Process Timeline & Thinking Card Evolution)
*   **过程话术入卡**：模型在执行过程中的规划、反思、过渡语与工具步骤统一归入折叠思考卡，保持主消息正文纯净清爽。
*   **思考时间线快照**：执行历史表增加 `process_timeline` JSON 快照字段，刷新页面或加载历史会话时可完整回放思考卡与步骤时间线。
*   **真实生成中断**：点击「停止」按钮真正向后端下发任务取消信号，立即终止 LLM 推理与工具执行，避免无效资源消耗。

### 3. 🎫 Embed Ticket 临时嵌入凭证与 24h 滑动续期 (Embed Ticket & Security Governance)
*   **临时凭证体系**：新增 Embed Ticket 临时嵌入凭证体系与服务端代客签发接口，支持白名单域名校验与权限隔离。
*   **兼容性与生产推荐**：原有的静态 Token 嵌入集成方式已做平滑兼容保留，现有对接代码无需改动即可平稳运行；生产环境强烈推荐使用安全性更高的 Embed Ticket 代客签发方式。
*   **滑动续期机制**：Session Token 滑动续期调整为 24 小时，保障长效嵌入会话的平滑交互体验。
*   **调试台全面升级**：组件调试台（Widget Debugger）支持 `strict_token` 严格校验模式与 Token 必填校验，升级嵌入集成开发指南。
*   **移动端排版对齐**：修复移动端 AIChat 横向溢出问题，全面对齐 EmbedChat 上行事件协议与会话数据隔离。

### 4. 📋 通用业务数据确认卡与人机协同治理 (Business Data Confirmation & HITL Collaboration)
*   **通用确认工具**：新增平台通用只读确认工具 `request_user_confirmation` 与 SSE 事件出卡机制。
*   **可交互编辑确认卡**：前端在 AI 消息下方渲染可交互确认卡片，支持用户直接修改关键业务字段并点击「确认执行」或「取消」。
*   **模型驱动回传**：操作结果以【业务确认】+ 字段快照消息结构化回传模型继续驱动执行，与底层工具执行确认（Tool Approval）清晰解耦。
*   **防重复与硬拦截**：有确认卡时自动收起 quick 引导避免重复入口；用户取消后前端硬拦截禁止再次弹出同一卡片。
*   **粘性路由短路**：业务确认回执会话具备粘性（Sticky Routing），直接短路跳过路由 LLM，保障人机协同流程无缝顺畅。

### 5. ⚡ 双重路由优化与意图识别合并 (Smart Multi-Agent Routing & Intent Merging)
*   **意图识别深度收敛**：将原独立意图识别与意图分类收拢合并至单次路由 LLM 调用，大幅削减首字返回延迟与 Token 开销。
*   **结构短路直达**：单一候选智能体或特定短路规则直接跳过路由 LLM，响应速度提升 50%+。
*   **偏好持久化与隔离**：支持用户路由偏好持久化存储与会话级实例隔离。

### 6. 👁️ 纯文本模型图片旁路解析 (Bypass Multimodal Vision Understanding)
*   **旁路多模态解析**：新增系统配置 `multimodal_model_name`；当会话使用的当前模型不支持视觉识图（如 DeepSeek-V3 等纯文本模型）时，系统自动调用默认多模态模型旁路解析图片。
*   **无缝文字注入**：将图片解析为结构化文字上下文后再交由主模型回答，打破大模型模态限制，彻底消除非多模态模型的图片理解断点。

### 7. 📊 ChatBI 健壮性与明细/依据/引用多维交互 (ChatBI Multi-view Panel & Robustness)
*   **合一展示面板**：气泡下方聚合「明细数据 / 执行依据 / 引用来源」多维度合一面板，抽样阈值调整至 500 行，兼顾前端渲染性能与全量数据概览。
*   **大结果集兜底**：大结果集自动抽样兜底，彻底解决长查询半截回复与前端假死问题。
*   **自动缓存合成收口**：纠正空结果误述，当 SQL 成功晚于可见正文时强制缓存合成收口，增强连续可视化分析与追问体验。

### 8. 🛠️ 工作空间、数据门户与任务调度体验优化 (Workspace, DataPortal & Task Center)
*   **工作空间交互精简**：快捷入口收拢为下拉菜单，类型筛选默认折叠，「含子目录」改为勾选交互；已配置的 Bash 工具严格绑定到会话工作区目录执行。
*   **黄金报表时间预设**：运行参数新增「今年（年初至今天）」快捷预设日期范围。
*   **数据门户状态治理**：未启用数据集显式标记不可用，并在目录工具中仅返回已启用项。
*   **任务调度与站内通知**：提示词约束最终推送通知禁止夹带中间思考，修复 resize 监听与 runNow 定时器卸载泄漏；站内消息详情支持 Mermaid 与 ECharts 富文本渲染。
*   **菜单体验优化**：将原「智能体测评」更名为「智能体调试」（Agent Debug），输入框未选模型时优雅显示「默认模型」。

---

## 🐛 Bug Fixes

### AI / 路由 / 业务确认
*   **业务确认防重复出卡**：修复用户在确认卡点击取消后可能再次弹出相同确认卡的问题，增加前端硬拦截机制。
*   **确认卡位置对齐**：将确认卡调整到 AI 消息正文下方展示，并在存在确认卡时隐藏 quick 引导避免重复入口。
*   **非多模态报错**：修复纯文本模型在用户发送图片时直接报错的问题，实现自动旁路多模态模型解析。
*   **真取消停止**：修复点击「停止」按钮仅前端断开连接的问题，实现真正取消后端生成协程。
*   **思考参数下发**：修复模型关闭思考时未显式传递 `false` 导致部分厂商模型默认打开思考的问题。

### Embed / 调试台 / 移动端
*   **EmbedChat 空用户报错**：修复嵌入聊天中用户信息为空时的报错问题，补充代客签发与白名单权限校验。
*   **移动端横向溢出**：修复移动端 AIChat 聊天容器宽度计算错误导致的横向滚动条溢出问题。
*   **Session Token 续期**：将 Session Token 滑动续期周期延长并调整为 24 小时。
*   **调试台严格模式**：组件调试台（Widget Debugger）补充 `strict_token` 严格校验模式与 Token 必填检查。

### ChatBI / 任务中心 / 工作区
*   **SQL 收口延迟**：修复 SQL 执行成功晚于可见正文时导致的回复截断与状态不一致问题，强制缓存合成收口。
*   **ChatBI 空结果误述**：纠正 ChatBI 在平台自动重试成功后误报空结果的问题。
*   **任务中心通知正文**：提示词强化约束调度任务，仅投递最终分析正文，彻底消除通知中夹带中间规划与思考内容的问题。
*   **定时器卸载泄漏**：修复任务中心窗口 resize 监听与 runNow 定时器在组件卸载时未正确清理导致的内存泄漏问题。
*   **工作区 Bash 绑定**：修复已配置的 Bash 工具未绑定到会话目录执行的问题，严格锁定当前会话的工作区路径。
*   **技能统计权限**：将技能调用统计接口调整为登录用户即可读。
*   **元数据实体关系**：统一实体关系一对多展示与 `join_type` 归一化。

---

## ⚠️ Breaking Changes & Migration Notes

> 从 v1.0.10 升级至 v1.0.11 时，请特别注意以下变更：

| 项目 | 说明 |
| :--- | :--- |
| **AgentScope 运行时注入配置** | 系统配置新增 `agentscope_inject_runtime_state` 与 `agentscope_inject_time_interval_hours`；需执行 `db-prod/V119` 或 `db-prod-pg/V19` 升级。 |
| **系统默认多模态模型配置** | 系统配置新增 `multimodal_model_name`，用于纯文本模型会话的图片旁路解析；需执行 `db-prod/V120` 或 `db-prod-pg/V20` 升级。 |
| **思考时间线快照字段** | 执行历史表 `ai_agent_execution_history` 新增 `process_timeline` JSON 字段；需执行 `db-prod/V121` 或 `db-prod-pg/V21` 升级。 |
| **菜单名称变更** | 原「智能体测评」菜单正式更名为「智能体调试」（Agent Debug）。 |
| **Embed 鉴权与 Ticket 机制** | 引入 Embed Ticket 代客签发权限与域名白名单校验；原有的静态 Token 验证集成方式兼容保留，生产环境推荐迁移至更安全的 Ticket 方式。 |

---

## 🗄️ Database Incremental Upgrades (数据库增量升级说明)

### MySQL（`db-prod/`）

从 v1.0.10 升级至 v1.0.11，MySQL 主库引入 **3 个**增量脚本：

| 脚本文件 | 核心变更内容 |
| :--- | :--- |
| **[V119-add_agentscope_injection_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V119-add_agentscope_injection_config.sql)** | 新增 AgentScope 运行时状态注入开关与时间注入间隔配置。 |
| **[V120-add_default_multimodal_model_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V120-add_default_multimodal_model_config.sql)** | 新增系统默认多模态模型配置 `multimodal_model_name`。 |
| **[V121-add_process_timeline_to_history.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V121-add_process_timeline_to_history.sql)** | 执行历史表 `ai_agent_execution_history` 增加 `process_timeline` JSON 快照字段。 |

### PostgreSQL（`db-prod-pg/`）

PostgreSQL 对应的 3 个增量升级脚本如下：

| 脚本文件 | 核心变更内容 |
| :--- | :--- |
| **[V19-add_agentscope_injection_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V19-add_agentscope_injection_config.sql)** | 新增 AgentScope 运行时状态注入开关与时间间隔配置。 |
| **[V20-add_default_multimodal_model_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V20-add_default_multimodal_model_config.sql)** | 新增系统默认多模态模型配置。 |
| **[V21-add_process_timeline_to_history.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V21-add_process_timeline_to_history.sql)** | 执行历史表增加 `process_timeline` JSON 列。 |

> [!NOTE]
> MySQL 环境请运行 `./db-prod/apply-sql-native.sh`；PostgreSQL 环境请运行 `./db-prod-pg/apply-sql.sh`。

---

## 📦 Upgrade Guide

### 方式一：源码直接升级（本地 / 虚机部署）

#### 1. MySQL 主库（默认）

```bash
# 1. 拉取最新代码
git fetch origin && git checkout main && git pull origin main

# 2. 更新 Python 依赖（升级至 AgentScope 2.0.6 等）
source .venv/bin/activate
pip install -r requirements.txt

# 3. 执行数据库迁移（自动跳过已执行脚本）
./db-prod/apply-sql-native.sh

# 4. 重新编译前端并启动
cd frontend && npm install && npm run build && cd ..
./dev.sh
```

#### 2. PostgreSQL 主库

```bash
# 配置 DATABASE_TYPE=postgresql
./db-prod-pg/apply-sql.sh
```

---

### 方式二：Docker 容器化升级（生产环境 / 容器集群）

#### 1. 场景 A：下载官方 Release 镜像归档（推荐生产/离线环境）

从 [GitHub Releases v1.0.11](https://github.com/RandyChen1985/nanzi-ai-agent-platform/releases/tag/1.0.11) 下载对应架构的 Docker 镜像归档包：

```bash
# 1. 执行数据库迁移（使用宿主机或临时容器）
./db-prod/apply-sql-native.sh  # PG: ./db-prod-pg/apply-sql.sh

# 2. 导入 Docker 镜像归档（按服务器架构选择对应文件）
# x86_64 服务器
docker load -i nanzi-ai-agent_1.0.11_linux-amd64_*.tar

# ARM64 服务器（鲲鹏 / Ampere 等）
docker load -i nanzi-ai-agent_1.0.11_linux-arm64_*.tar

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

# 2. 进入 docker 目录构建 v1.0.11 镜像
cd docker

# x86_64 Linux 服务器
./build_linux_x86.sh 1.0.11

# ARM64 Linux 服务器（鲲鹏 / Ampere / M 芯片）
./build_linux_arm.sh 1.0.11

# 3. 启动 / 重启容器服务
./start-nanzi-ai-agent.sh
```

---

## 💾 Downloads / Assets

本项目 v1.0.11 发布版本关联的源码、Docker 镜像资产归档包及配置文件如下：

* 📦 **Source Code (zip)**: `nanzi-ai-agent-platform-1.0.11.zip`
* 📦 **Source Code (tar.gz)**: `nanzi-ai-agent-platform-1.0.11.tar.gz`
* 🐳 **Docker Image for Linux amd64 (x86_64)**: `nanzi-ai-agent_1.0.11_linux-amd64_*.tar`
* 🐳 **Docker Image for Linux arm64 (aarch64)**: `nanzi-ai-agent_1.0.11_linux-arm64_*.tar`
* ⚙️ **Docker Compose YAML file**: `docker-compose.ai-agent.yml` / `docker-compose.yml`

🔗 **下载地址**: [GitHub Releases v1.0.11](https://github.com/RandyChen1985/nanzi-ai-agent-platform/releases/tag/1.0.11)

---

## ✅ Test Checklist

升级后建议验证以下核心场景：

- [ ] **AgentScope 2.0.6 运行时与注入**：检查系统配置中 `agentscope_inject_runtime_state` 开关；模型对话正常，且可通过 `session_status` 工具查询当前会话事实。
- [ ] **业务数据确认卡**：触发需要业务确认的操作时，前端在 AI 消息下方正常出卡；可修改字段并点击「确认」或「取消」；回传消息格式正确；取消后不再重复弹出。
- [ ] **单次路由与短路**：单候选智能体或确认卡回执能快速短路跳过路由 LLM；意图识别单次调用无异常。
- [ ] **纯文本模型旁路识图**：配置 `multimodal_model_name`；切换为纯文本大模型并上传图片，模型能通过旁路解析正常回答图片内容。
- [ ] **思考卡与时间线回放**：模型规划与工具步骤折叠在思考卡内；刷新页面后能从 `process_timeline` 完整回放历史步骤与时间线。
- [ ] **停止按钮真取消**：对话流式输出中点击「停止」按钮，后端任务与流式生成立即终止。
- [ ] **Embed Ticket 与调试台**：通过 Embed Ticket 签发访问嵌入式聊天；在 Widget Debugger 中测试 `strict_token` 模式与 Token 必填校验；移动端排版无横向溢出。
- [ ] **ChatBI 气泡面板与抽样**：查询大数据集时自动抽样至 500 行，气泡下方正常切换「明细数据 / 执行依据 / 引用来源」；重试与缓存合成收口流畅。
- [ ] **工作空间与数据门户**：工作空间快捷入口与筛选工作正常；Bash 在会话目录执行；未启用数据集在数据门户与目录工具中标记不可用。
- [ ] **自动化测试回归**：运行 `pytest tests/`，确保测试全量通过。

完整测试清单见 [tests/CHECKLIST.md](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/tests/CHECKLIST.md)。

---

## 📋 Commit Log

| Hash | 描述 |
| :--- | :--- |
| `2c8a3fbf` | feat(embed): 支持用户路由偏好持久化与实例会话隔离，优化思考时间线对齐 |
| `1ec005b6` | fix(embed): 加固 Embed Ticket 代客签发权限校验与白名单支持 |
| `b26ce1fc` | fix(embed): 修复EmbedChat空用户信息报错并将Session Token滑动续期调整为24小时 |
| `0e934551` | Merge pull request #104 from RandyChen1985/dev-agentscope |
| `0e36a0ca` | feat(embed): 新增Embed Ticket临时嵌入凭证与滑动续期机制，升级调试台与集成指南 |
| `3ecdfa86` | fix(embed): 修复移动端AIChat横向溢出问题并对齐EmbedChat上行事件协议文档 |
| `2354a18f` | feat(widget-debugger): 调试台支持 strict_token 严格校验模式与 Token 必填校验 |
| `ddee8966` | feat(工具): 新增只读 session_status 供模型查询当前会话事实 |
| `f727f30a` | docs(文章): 新增 DeepSeek Harness 与 Qwen3.8-27B 开源解读稿 |
| `8e402406` | feat(模型): 关思考显式传 false，并优化思考配置开关 |
| `4097a398` | feat(数据门户): 未启用数据集标记不可用并标明目录工具仅返回已启用项 |
| `1b927b37` | Merge pull request #102 from RandyChen1985/dev-agentscope |
| `ff803552` | feat(路由): 合并意图识别到一次路由 LLM |
| `40d0fb8b` | feat(对话): 过程话术进思考卡并支持历史回放 |
| `1f4a0d21` | fix(菜单): 将「智能体测评」更名为「智能体调试」 |
| `9dd5f0cb` | fix(对话): 输入框未选模型时显示「默认模型」 |
| `75a19f03` | merge: 将非多模态图片旁路解析合入 main |
| `09cbb6e9` | feat(对话): 非多模态会话自动旁路解析图片 |
| `dca73f0f` | docs(连载): 新增 C03 Prompt 到 Loop 原理文 |
| `d1674ad9` | Merge pull request #101 from RandyChen1985/dev-agentscope |
| `af671d1d` | feat(对话): 点停止真正取消本轮生成 |
| `27c35a38` | fix(工作区): 将已配置的 Bash 绑定到会话目录执行 |
| `eb0b537b` | fix(任务中心): 修复 resize 监听与 runNow 定时器卸载泄漏 |
| `aecf8711` | docs(连载): 重构 Skills 全景文并补充 WorkBuddy 对比 |
| `ccbaad47` | fix(技能): 调用统计接口改为登录可读 |
| `2c561c2c` | fix(元数据): 统一实体关系一对多展示与 join_type 归一化 |
| `a377f568` | docs(readme): 补充微信实战连载合集入口 |
| `99596ef5` | fix(任务中心): 通知仅投递最终分析正文 |
| `6ca42b97` | fix(chatbi): SQL 成功晚于可见正文时强制缓存合成收口 |
| `5d26dc58` | fix(chatbi): 纠正空结果误述，平台自动重试成功后改为缓存合成 |
| `dee2cdce` | Merge pull request #99 from RandyChen1985/dev-agentscope |
| `4eb2e73c` | feat(chatbi): 气泡下明细/依据/引用合一面板，抽样阈值调至 500 |
| `abec3811` | feat(chatbi): 大结果抽样兜底半截回复，并加厚可视化分析追问 |
| `d74ab4a6` | Merge pull request #98 from RandyChen1985/dev-agentscope |
| `ecfdeb64` | docs(测试): 更新业务确认与路由短路自动化清单 |
| `c55f1a75` | fix(业务确认): 有确认卡时隐藏 quick 引导避免重复操作入口 |
| `6f93490e` | docs(A06): 调整 MCP 文章截图占位到各章节与步骤后 |
| `093deee8` | fix(业务确认): 确认卡改到 AI 正文下方展示 |
| `9fa99ecd` | feat(路由): 唯一候选结构短路跳过路由 LLM |
| `0c43deab` | feat(路由): 业务确认回执会话粘性跳过路由 LLM |
| `d5468b36` | test(业务确认): 补充取消后前端硬拦截契约断言 |
| `41aad46a` | fix(业务确认): 取消后硬拦截再次出确认卡 |
| `ca6d2fc7` | fix(业务确认): 取消后禁止立刻再次弹出确认卡 |
| `f4bc1ae5` | Merge pull request #97 from RandyChen1985/dev-agentscope |
| `e288c279` | feat(业务确认): 通用业务数据确认卡与 request_user_confirmation |
| `221ea8f3` | docs: 新增业务数据确认卡设计规格 |
| `112e5bc2` | feat(agentscope): 升级 2.0.6 并接入结构化输出、权限中间件与可配置运行时注入 |
| `2840f060` | feat(站内消息/欢迎页): 详情支持 Mermaid 与 ECharts，并补快捷入口标题 |
| `1d95463d` | fix(任务中心): 提示词约束最终正文禁止夹带中间思考 |
| `98d09c53` | docs: README 联系区补充免费体验账号说明并同步英文版 |
| `fb7dddac` | Merge pull request #96 from RandyChen1985/dev-agentscope |
| `df22a9f7` | docs(tests): 同步任务调度、工作空间与黄金报表相关测试清单 |
| `407a7d14` | feat(工作空间/黄金报表): 精简浏览侧栏并支持今年日期范围 |
