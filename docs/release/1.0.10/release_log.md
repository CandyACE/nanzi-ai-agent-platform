# 🎉 NanZi AI Agent Platform v1.0.10 Release Notes

**GitHub Repository**: [RandyChen1985/nanzi-ai-agent-platform](https://github.com/RandyChen1985/nanzi-ai-agent-platform)

v1.0.10 版本是一次以 **AgentScope 原生模型思考与推理流 (Thinking & Reasoning Stream) 贯通** 为核心领衔，并全面推进 **个人技能审核与版本治理全流程、代码画布多语言在线运行、黄金报表统一解读管线、轻量联网搜索与 MCP 会话挂载、Embed 我的资源与导航注入，以及平台全局时区（`platform_timezone`）和视觉体验升级** 的重磅迭代版本。

在本次更新中，平台原生对齐 AgentScope 思考参数与 6 档强度调优，支持流式下发并持久化回放历史推理过程 (`reasoning_content`)，消息与画布支持 KaTeX 数学公式渲染；落地个人技能申请、审核、发布、版本管理与撤销全流程（配合 `element:skills:admin` 权限）；代码画布支持 Python/JS 等多语言交互运行与工作区保存；黄金报表统一解读管线，支持延续走查数分析；新增百度/Bing HTTP 轻量联网搜索与会话级挂载 MCP 服务，支持粘贴 `mcpServers` JSON 登记；EmbedChat 接入「我的资源」卡片并支持导航注入；新增平台全局时区配置，重构仪表盘「活跃用户」卡片并升级登录页主视觉。

本次变更范围自 `50b56211273356c43a883976630c7834ca2a27b8`（不含，为 v1.0.9 末相关提交）至 `4aee62807c25be721cb94d8e0b3b410e548a0e56`（含），共 **81 个提交**（其中非 Merge 提交 73 个），涉及 324 个文件、约 25,276 行新增代码与 2,576 行删除。

---

## 🚀 Key Features

### 1. 🧠 AgentScope 原生思考模式与推理流 (Thinking & Reasoning Stream)
*   **原生思考参数**：平台全面对齐 AgentScope 原生思考配置，支持 6 档思考强度调节（`off`, `minimal`, `low`, `medium`, `high`, `deep`），可在智能体与任务中心灵活下发。
*   **流式推理展示**：后端流式下发 `reasoning_content`，前端实现思考推理面板的实时折叠/展开与优雅过渡动画。
*   **推理持久化与回放**：数据库下发与持久化扩展，支持历史会话中模型推理内容的存储、查询与完美回放。
*   **公式渲染**：消息面板与代码画布全面集成 KaTeX 数学公式渲染，优雅呈现科技与学术文本。
*   **路由解耦**：路由意图解析自动忽略会话级别的思考覆盖，确保路由精准度不受影响。

> 📷 **截图占位**：AgentScope 原生思考模式、强度选择与 reasoning_content 实时推理流展示  
> `![AgentScope 思考与推理流展示](https://via.placeholder.com/800x450?text=AgentScope+Thinking+%26+Reasoning+Stream)`

### 2. 🛠️ 个人技能审核发布与版本治理 (Skill Publication & Audit Governance)
*   **全流程贯通**：实现个人技能提交申请、管理员审核放开/驳回、版本更新、下架与撤销全流程。
*   **权限控制**：注册 `element:skills:admin` 管理员权限，普通用户免菜单权限可查询平台技能列表。
*   **环境与规范**：更新 Python 3.11+ 基础环境规范与文档，优化技能发布服务 metadata 拼接逻辑。

> 📷 **截图占位**：个人技能申请发布、管理员审核后台与版本记录展示  
> `![技能审核发布全流程展示](https://via.placeholder.com/800x450?text=Skill+Publication+%26+Audit+Governance)`

### 3. 💻 代码画布 (Code Canvas) 在线运行与工作区保存
*   **多语言运行**：新增代码画布多语言脚本（Python / JavaScript 等）在线交互式运行，运行结果自动回传工作区保存。
*   **Auto Pin 模式**：首次打开支持自动开启钉住固定模式（Auto Pin）；桌面端铺满可用宽度，移动端置顶且保留工作区。
*   **混合渲染**：画布 Markdown 预览完美支持 ECharts 数据图表与 Mermaid 流程图/架构图混合渲染。

> 📷 **截图占位**：代码画布在线脚本运行输出与图表混合渲染展示  
> `![代码画布多语言交互运行](https://via.placeholder.com/800x450?text=Code+Canvas+Execution+%26+Charts)`

### 4. 📊 黄金报表 (Golden Reports) 统一解读管线 & 走查数延续分析
*   **统一解读管线**：统一黄金报表执行解读管线，优化列语义理解与等待加载体验。
*   **延续走查数**：新增通用消息继续分析（continuation analysis），支持强制走查数智能体并保留可视化上下文。
*   **元数据扩展**：保存报表表结构增加 `column_meta` 列元数据与解读分析相关字段。

> 📷 **截图占位**：黄金报表统一解读与延续走查数交互展示  
> `![黄金报表统一解读管线](https://via.placeholder.com/800x450?text=Golden+Report+Interpretation+Pipeline)`

### 5. 🌐 联网搜索隐/显式工具、MCP 会话挂载与 JSON 快速登记
*   **轻量联网搜索**：新增百度/Bing HTTP 轻量联网搜索隐式/显式工具分组，升级 Prompt 动态装配与知识库检索误报净化。
*   **会话级 MCP**：支持在单次会话中动态挂载个人 MCP 服务，优化资源级联交互与浮层对齐。
*   **JSON 快速登记**：支持直接粘贴 `mcpServers` JSON 配置一键登记 MCP 服务，支持服务备注 (`remark`) 与固定命向前缀。

> 📷 **截图占位**：会话级 MCP 挂载、JSON 登记与联网搜索界面展示  
> `![MCP 会话挂载与 JSON 登记](https://via.placeholder.com/800x450?text=Session+MCP+Mount+%26+Search+Tools)`

### 6. 🎨 EmbedChat / 个人中心「我的资源」统计卡与导航注入
*   **我的资源卡片**：EmbedChat 初始页接入「我的资源」统计卡与弹层，与个人中心共享 `PersonalMemoryPanel`（采用 keep-alive 保留 Tab 状态）。
*   **导航与布局**：DataPortal / TaskCenter 支持 Embed 导航注入与布局拆分，优化思考步骤展示与站内消息独立弹层。

> 📷 **截图占位**：EmbedChat 我的资源统计卡片与弹层展示  
> `![Embed 我的资源统计卡片](https://via.placeholder.com/800x450?text=EmbedChat+My+Resources+Stats)`

### 7. ⏰ 平台全局时区系统配置与基础体验/视觉升级
*   **全局时区系统**：新增系统配置 `platform_timezone`（默认 `Asia/Shanghai`），贯通定时任务调度与日志/界面时间展示。
*   **活跃用户卡片**：将仪表盘原「最新用户」模块重构为「活跃用户」卡片，信息更贴合运维需要。
*   **品牌主视觉**：升级登录页品牌主视觉轮播（暗黑极客配色与平滑光晕），Dashboard 支持亮/暗色主题，修复 iOS home 图标暗色边框。

> 📷 **截图占位**：登录页暗黑极客主视觉与仪表盘活跃用户卡片展示  
> `![品牌极客主视觉与活跃用户](https://via.placeholder.com/800x450?text=Brand+Visuals+%26+Dashboard+Active+Users)`

---

## 🐛 Bug Fixes

### AI / ChatBI / 知识库
*   **检索误报净化**：修复知识库成功检索后的误报问题，动态过滤非本轮 Prompt 工具清单。
*   **工具挂载保留**：修复智能体版本发布时 DB 工具定义缓存清理，保留智能体显式配置的知识库工具挂载与 Prompt 装配。
*   **协程与快照**：修复 AgentScope 确认快照重复消费协程的问题。
*   **继续分析上下文**：修复黄金报表继续分析时可视化上下文丢失的问题。

### Canvas / 图表 / 消息
*   **画布分析消息**：修复代码画布执行结果触发重复自动发送分析消息的 Bug。
*   **K 线图空白**：修复 ECharts K 线图双 grid 空白问题，支持按数据自适应切换视图。
*   **复制按钮样式**：统一全局 UI 中的复制按钮图标为干净的双页图标。

### 前端 / 工作台 / 交互体验
*   **顶栏与通知**：修复移动端站内通知防裁切问题，普通用户隐蔽显示在线人数。
*   **页面页头折行**：统一工作台/概览刷新样式，修正概览标题与 MCP 页头折行。
*   **资源卡边框**：消除资源卡错误态下 dark 边框的样式冲突。
*   **Docker 导出**：Docker 构建镜像打包时排除 release 镜像导出压缩包。

---

## ⚠️ Breaking Changes & Migration Notes

> 从 v1.0.9 升级至 v1.0.10 时，请特别注意以下变更：

| 项目 | 说明 |
| :--- | :--- |
| **模型思考配置** | 引入 `thinking_mode`, `thinking_budget` 等字段；需执行 `db-prod/V116-V117` 或 `db-prod-pg/V15-V16` 升级。 |
| **推理历史持久化** | 历史表 `ai_agent_execution_history` 增加 `reasoning_content`；需执行 `db-prod/V100` 或 `db-prod-pg/V17` 升级。 |
| **技能审核权限** | 注册 `element:skills:admin` 权限控制；审核管理功能仅拥有该权限的角色可见。 |
| **MCP 服务备注** | `ai_mcp_servers` 增加 `remark` 字段；需执行 `db-prod/V114` 或 `db-prod-pg/V13` 升级。 |
| **平台全局时区** | `system_configs` 增加 `platform_timezone`（默认 `Asia/Shanghai`）；如需修改可通过控制台系统配置修改。 |
| **报表列元数据** | 保存报表增加 `column_meta` 与 `continuation_analysis` 等；需执行 `db-prod/V118` 或 `db-prod-pg/V18` 升级。 |

---

## 🗄️ Database Incremental Upgrades (数据库增量升级说明)

### MySQL（`db-prod/`）

从 v1.0.9 升级至 v1.0.10，MySQL 主库引入 **9 个**增量脚本：

| 脚本文件 | 核心变更内容 |
| :--- | :--- |
| **[V110-create-skill-publications.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V110-create-skill-publications.sql)** | 创建个人技能审核与版本记录表 `ai_skill_publications`。 |
| **[V112-add-skill-publication-withdrawal.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V112-add-skill-publication-withdrawal.sql)** | 增加技能下架/撤销字段 `is_withdrawn`。 |
| **[V113-register_skill_admin_permission.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V113-register_skill_admin_permission.sql)** | 注册技能审核管理员权限 `element:skills:admin`。 |
| **[V114-add_mcp_server_remark.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V114-add_mcp_server_remark.sql)** | MCP 服务表增加备注字段 `remark`。 |
| **[V115-add_platform_timezone_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V115-add_platform_timezone_config.sql)** | 新增平台全局时区配置 `platform_timezone`。 |
| **[V116-add_ai_model_thinking_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V116-add_ai_model_thinking_config.sql)** | AI 模型增加 AgentScope 思考模式与强度配置字段。 |
| **[V117-use_agentscope_reasoning_fields.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V117-use_agentscope_reasoning_fields.sql)** | 对齐 AgentScope 思考强度策略下发。 |
| **[V100-add-reasoning-content-to-history.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V100-add-reasoning-content-to-history.sql)** | 执行历史表增加 `reasoning_content` 列。 |
| **[V118-saved-report-column-meta-and-analysis.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V118-saved-report-column-meta-and-analysis.sql)** | 保存报表增加 `column_meta` 与 `continuation_analysis` 等列。 |

### PostgreSQL（`db-prod-pg/`）

PostgreSQL 对应的 9 个增量升级脚本如下：

| 脚本文件 | 核心变更内容 |
| :--- | :--- |
| **[V10-create-skill-publications.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V10-create-skill-publications.sql)** | 创建个人技能审核与版本记录表。 |
| **[V11-add-skill-publication-withdrawal.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V11-add-skill-publication-withdrawal.sql)** | 增加技能下架/撤销支持。 |
| **[V12-register_skill_admin_permission.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V12-register_skill_admin_permission.sql)** | 注册技能审核管理员权限。 |
| **[V13-add_mcp_server_remark.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V13-add_mcp_server_remark.sql)** | MCP 服务表增加备注列。 |
| **[V14-add_platform_timezone_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V14-add_platform_timezone_config.sql)** | 新增平台全局时区系统配置。 |
| **[V15-add_ai_model_thinking_config.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V15-add_ai_model_thinking_config.sql)** | AI 模型增加思考模式相关配置。 |
| **[V16-use_agentscope_reasoning_fields.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V16-use_agentscope_reasoning_fields.sql)** | 对齐 AgentScope 思考强度策略下发。 |
| **[V17-add-reasoning-content-to-history.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V17-add-reasoning-content-to-history.sql)** | 执行历史表增加 `reasoning_content` 列。 |
| **[V18-saved-report-column-meta-and-analysis.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/V18-saved-report-column-meta-and-analysis.sql)** | 保存报表增加 `column_meta` 及解读扩展字段。 |

> [!NOTE]
> MySQL 环境请运行 `./db-prod/apply-sql-native.sh`；PostgreSQL 环境请运行 `./db-prod-pg/apply-sql.sh`。

---

## 📦 Upgrade Guide

### 从 v1.0.9 升级（默认 MySQL 主库）

```bash
# 1. 拉取最新代码
git fetch origin && git checkout main && git pull origin main

# 2. 更新 Python 依赖
source .venv/bin/activate
pip install -r requirements.txt

# 3. 执行数据库迁移（自动跳过已执行脚本）
./db-prod/apply-sql-native.sh

# 4. 重新编译前端并启动
cd frontend && npm install && npm run build && cd ..
./dev.sh
```

### PostgreSQL 主库升级

```bash
# 配置 DATABASE_TYPE=postgresql
./db-prod-pg/apply-sql.sh
```

---

## ✅ Test Checklist

升级后建议验证以下核心场景：

- [ ] **模型思考与推理流**：设置智能体/模型思考强度（如 medium/high）；对话时能流式看到思考推理展开与折叠；历史记录完美回放推理过程；KaTeX 数学公式渲染正确。
- [ ] **技能审核发布**：个人提交技能申请；拥有 `element:skills:admin` 权限用户在后台审核/驳回；技能发布版本正常累加；支持技能下架与撤销。
- [ ] **代码画布在线运行**：代码画布在线运行 Python / JS 脚本，运行输出回写工作区保存；Auto Pin 钉住模式正常；ECharts / Mermaid 图表混合渲染流畅。
- [ ] **黄金报表解读**：黄金报表生成与统一解读管线正常；消息「继续分析」强制走查数智能体并保留可视化上下文。
- [ ] **搜索与 MCP 增强**：百度/Bing 轻量联网搜索生效；单次会话可挂载个人 MCP 服务；可复制粘贴 `mcpServers` JSON 登记并填写备注。
- [ ] **EmbedChat 与资源**：EmbedChat 初始页展示「我的资源」统计卡并能打开弹层；页面切换 Tab 状态保留；DataPortal 支持导航注入。
- [ ] **全局时区与体验**：`platform_timezone` 修改后生效；仪表盘「活跃用户」展示正常；登录页主视觉极客效果平滑。
- [ ] **自动化测试回归**：运行 `pytest tests/`，确保测试全量通过。

完整测试清单见 [tests/CHECKLIST.md](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/tests/CHECKLIST.md)。

---

## 📋 Commit Log

| Hash | 描述 |
| :--- | :--- |
| `4aee6280` | Merge pull request #94 from RandyChen1985/dev-agentscope |
| `38208c77` | fix(黄金报表): 继续分析强制走查数智能体并保留可视化上下文 |
| `1efae406` | feat(黄金报表): 统一执行解读管线并优化列语义与等待体验 |
| `ee70a122` | feat: add generic message continuation analysis |
| `917344e8` | fix(ui): 优化聊天文案、默认隐藏消息外框与任务资源弹层定位 |
| `84e8d04b` | feat(embed): 优化思考步骤展示并支持站内消息独立弹层 |
| `146f5f9c` | fix: prevent dark border on iOS home icon |
| `04e34090` | fix(chat): 将 thinking_only 改为默认思考状态并允许会话覆盖 |
| `65d10e90` | Merge pull request #93 from RandyChen1985/dev-agentscope |
| `b508ae27` | docs: 更新模型思考与推理展示 CHECKLIST |
| `d35d9716` | fix(chat): 路由意图忽略会话思考覆盖，推理面板文案改为思考推理 |
| `7fbd2fa8` | feat(chat): 持久化并回放会话中的模型推理内容 |
| `64e251aa` | feat(markdown): 消息与画布支持 KaTeX 数学公式渲染 |
| `ebc7238e` | feat(chat): 流式展示模型 reasoning_content 并下发思考模板参数 |
| `3130729f` | fix(UI): 优化模型思考选择交互与移动端底栏 |
| `01c48db4` | fix(UI): 思考强度改为直接展开选择，并修正开关滑块 |
| `b596f785` | feat(task): 支持任务配置模型思考参数 |
| `5123620e` | docs: 补充代码画布与工作区执行指南 |
| `9d1b4a86` | feat(model): 对齐 AgentScope 原生思考参数与六档强度 |
| `0d706884` | feat(model): 增加思考模式配置 |
| `136e2a9b` | docs: 调整模型思考强度档位 |
| `49f41f4a` | docs: 设计模型思考配置 |
| `ec032968` | docs: 补齐近期功能文档 |
| `f2e34f97` | fix(UI): 统一复制按钮为双页图标 |
| `03076a53` | fix(画布): 桌面铺满可用宽度，移动端置顶且保留工作区 |
| `70e490c4` | Merge pull request #92 from RandyChen1985/dev-agentscope |
| `bd8042d8` | docs: 更新 Embed 我的资源 CHECKLIST 描述 |
| `752b7994` | fix(UI): Embed 资源卡精简、能力面板默认钉住与记忆文案 |
| `ed98d0fd` | fix(UI): 资源卡加载占位与欢迎页加宽布局 |
| `0b4f2290` | feat: EmbedChat 初始页接入我的资源统计卡与弹层 |
| `86e8e255` | feat: 新增 Embed「我的资源」弹层 |
| `f096d2f8` | fix: DataPortal 拆分 embedded 布局与导航委托 |
| `ebb18340` | feat: DataPortal/TaskCenter 支持 Embed 导航注入 |
| `346c3e4a` | fix: PersonalMemoryPanel 用 keep-alive 保留 Tab 状态 |
| `09065d96` | refactor: 抽出 PersonalMemoryPanel 供个人中心与 Embed 共用 |
| `66a22c27` | fix(UI): 资源卡错误态 dark 边框避免冲突 |
| `84b82007` | refactor: 工作台资源卡解耦路由并抽出静态 defs |
| `0ab89f8a` | docs: 添加 EmbedChat 我的资源实现计划 |
| `05332ab4` | docs: 添加 EmbedChat 初始页「我的资源」设计稿 |
| `ac65188a` | fix(UI): 统一工作台/概览刷新样式，纠错概览标题与 MCP 页头折行 |
| `50a1967e` | fix(顶栏): 站内通知移动端防裁切，普通用户隐藏在线人数 |
| `6ca4a89e` | feat: 工作台最近任务三列、移动端体验与记忆索引防护 |
| `8e3c1cd3` | Merge pull request #91 from RandyChen1985/dev-agentscope |
| `244181e6` | feat(任务): 提示词资源范围、服务端收敛与执行记录 Tab |
| `9608cd1f` | feat(导航): Dashboard 支持亮暗色主题，工作台免菜单权限可进 |
| `2a50568f` | feat(工作台): 个人中心嵌入我的任务并展示资源统计卡 |
| `557a9a02` | feat(工作台): 个人工作台增加进行中任务并提升信息密度 |
| `90e0daaa` | fix(图表): 修复 K 线双 grid 空白并按数据自适应切换视图 |
| `465f7d2c` | feat(图表): 消息与画布 ECharts 支持 candlestick K 线 |
| `48b97c7a` | feat(MCP): 支持粘贴 mcpServers JSON 登记，级联分组默认折叠 |
| `176dfc6a` | Merge pull request #90 from RandyChen1985/dev-agentscope |
| `26124480` | feat(时区): 新增平台时区系统配置并贯通调度与展示 |
| `9cc7b454` | Merge pull request #89 from RandyChen1985/dev-agentscope |
| `803ee272` | feat(MCP): 服务备注、固定命名前缀与级联浮层对齐优化 |
| `abf103ed` | feat(会话/MCP): 支持会话级挂载个人 MCP 并优化资源级联交互 |
| `a0c21e32` | feat(ai): 联网搜索改为显式配置并独立工具分组 |
| `91e55e7d` | feat(ai): 新增百度/Bing HTTP 轻量联网搜索隐式工具 |
| `070f956e` | fix(ai): 知识库智能体保留全部系统隐式工具挂载 |
| `ea7d1ce0` | fix(ai): 保留智能体显式配置的知识库工具挂载与 Prompt 装配 |
| `5905f8da` | fix(ai): 智能体版本发布时自动清理 DB 工具定义缓存 |
| `d6471efa` | docs(tests): 更新 CHECKLIST.md 补充动态 Prompt 工具清单与知识库检索误报净化测试项 |
| `65ade273` | fix(ai & frontend): 动态过滤非本轮 Prompt 工具清单，修复知识库成功检索误报，并优化登录页平滑光晕跟随 |
| `9d33d596` | fix(frontend): 优化登录页视觉轮播暗黑极客配色并移除鼠标跟随移动 |
| `e9137135` | docs(html): 完善内置工具箱手册文档(A05-builtin-tools)的规范示例与使用说明 |
| `d171eac5` | fix(skills): 放开平台技能列表查询权限 |
| `aeed7424` | docs & refactor: 更新 Python 3.11+ 基础环境规范与文档，优化技能发布服务 metadata 拼接逻辑 |
| `084e698e` | Merge pull request #88 from RandyChen1985/dev-agentscope |
| `6f9b8973` | feat(skills): 实现个人技能审核发布、版本管理、撤销与管理员权限控制全流程 |
| `5191af29` | fix(canvas): 修复代码画布执行结果自动发送分析消息 |
| `1422be81` | docs: 设计个人技能审核发布流程 |
| `f6138cf1` | feat(canvas): 画布首次打开支持自动开启钉住固定模式 (Auto Pin) |
| `02963c98` | docs: 添加 D01-deepseek-v4-flash-0731-h800-clean HTML 文档 |
| `d3116d30` | feat(dashboard): 将仪表盘最新用户重构为活跃用户并同步更新测试与清单 |
| `313104fe` | feat(canvas): 画布 Markdown 预览支持 ECharts 数据图表与 Mermaid 图表混合渲染 |
| `ff7b6014` | feat(ai): 完善知识库执行器门禁与能力缺口全局 Prompt 降级 |
| `000b90ec` | docs: add general capability gap prompt design |
| `4c6d19e6` | Merge pull request #86 from RandyChen1985/feat/canvas-code-execution |
| `83cd1738` | feat(canvas): 新增代码画布多语言脚本在线运行与工作区保存功能 |
| `9010ef0f` | fix(docker): 排除 release 镜像导出包 |
| `98f04181` | fix(agentscope): 防止确认快照重复消费协程 |
| `be8839fa` | feat(login): 升级登录页品牌主视觉轮播并统一默认副标题 |

---

## 🤝 Contributors

感谢所有参与 v1.0.10 版本发布的开发者与贡献者！
