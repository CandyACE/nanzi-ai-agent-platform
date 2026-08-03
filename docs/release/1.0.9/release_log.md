# 🎉 NanZi AI Agent Platform v1.0.9 Release Notes

**GitHub Repository**: [RandyChen1985/nanzi-ai-agent-platform](https://github.com/RandyChen1985/nanzi-ai-agent-platform)

v1.0.9 版本是一次以**PostgreSQL 作为平台智能体元数据库（主库）双引擎落地**为首要能力，并推进 **MCP 个人作用域与工具可用性治理、案例集/经验库检索、模型注册表安全与运行时身份透明、知识库与 Embed 交互升级，以及危险 Shell 删除护栏与事实取证提示**的迭代版本。在本次更新中，平台可通过 `DATABASE_TYPE=postgresql` 将系统配置、角色权限、审计日志与智能体元数据落在 PostgreSQL（`db-prod-pg/` 基线与增量并行于 MySQL `db-prod/`）；同时支持 MCP 公共/个人作用域与显示名全局唯一；远端已删除工具标记不可用仍保留可见；案例集通用化并新增 `search_qa_examples` / `get_myinfo`；模型注册表强化唯一性、Token 限额与运行时身份；记忆统一全局向量模型（默认 bge-m3 / 1024）；知识库工具步与 Embed 调度占位升级；并加固危险 Shell 护栏、取证分级与一批体验缺陷。

本次变更范围自 `a9fc4fef62127d068dfc051c08bde2aa26914dd5`（不含，为 v1.0.8 末相关提交）至 `cb36b9cc95770bdc5684575718f7158be054735f`（含），共 **60 个提交**（其中非 Merge 提交 48 个），涉及 234 个文件、约 19,562 行新增代码。

---

## 🚀 Key Features

### 1. 🐘 PostgreSQL 作为平台智能体元数据库（主库）
*   **双主库可选**：通过 `DATABASE_TYPE=mysql|postgresql` 选择平台主库；默认仍为 MySQL，可选切换为 PostgreSQL。
*   **元数据落库**：系统配置、角色权限、审计日志、智能体/版本/工具与会话等平台元数据均可运行在 PostgreSQL。
*   **独立初始化链**：新增 [`db-prod-pg/`](https://github.com/RandyChen1985/nanzi-ai-agent-platform/tree/main/db-prod-pg)（`V0-baseline` 当前态基线 + 后续 `V*.sql` 增量），与 MySQL `db-prod/` 历史迁移链并行维护、互不改写。
*   **运行时方言分支**：SQLAlchemy / APScheduler 与方言敏感 upsert、分区维护等按主库类型分支；审计日志与相关服务加固。
*   **安装与运维**：`HOW_TO_INSTALL.md` / Docker / `env.example` 补齐 `POSTGRES_*`；apply-sql 支持相对路径解析。

### 2. 🔌 MCP 作用域、可用性与管理体验
*   **个人作用域**：MCP 服务支持 `global` / `personal` 作用域与创建者隔离；完善重命名迁移与权限校验。
*   **显示名唯一**：强制服务显示名全局唯一（大小写不敏感）；历史重名自动追加 `legacy-*` 标记。
*   **远端可用性**：远端已删除工具标记 `is_available=false` 且保留可见；与发布状态解耦。
*   **管理台增强**：展示服务绑定智能体；修复禁用后误同步与发布状态生效；美化工具测试台结果与启停加载态。
*   **探测与权限**：优化 SSE/HTTP 探测与欢迎语文案；修复普通用户发布 MCP 工具权限；更新 Skills 官方市场链接。

### 3. 📚 案例集 / 经验库与内置工具
*   **案例集通用化**：案例集管理全面优化与通用化重构，支持分类（general / knowledge / data_query）。
*   **检索经验库**：新增内置工具 `search_qa_examples`，检索已验证问答案例与 SQL 口径参考。
*   **本人资料**：新增 `get_myinfo` 工具，并优先处理本人资料查询意图。

### 4. 🧠 模型注册表、运行时身份与向量模型
*   **注册表治理**：强化模型注册表安全与供应商接入；完善解析、管理台筛选与高级设置交互。
*   **唯一性与限额**：`model_id` 全局唯一；支持可选 `context_size` / `max_output_tokens`。
*   **使用关系**：完善模型使用关系展示，并消除管理页抖动。
*   **运行时身份**：支持查询本轮实际生效的运行时模型身份。
*   **全局向量模型**：记忆与系统配置统一使用全局向量模型；默认 Embedding 调整为 bge-m3、维度 1024。

### 5. 📖 知识库智能体与 EmbedChat 体验
*   **工具步体验**：知识库工具步增加绑定引导；默认折叠 ChatBI；支持隐藏 AI 消息外框。
*   **调度占位**：Embed 思考中显示调度占位（三点跳动与名称淡入上滑）；优化无边框消息样式。
*   **移动端表格**：Markdown 表格自适应卡片/表格切换；多主题表格样式与思考时间轴竖线淡化。
*   **技能计数**：智能体卡片技能数展示启用公共技能总量。

### 6. 🛡️ 安全、取证与 AI 契约
*   **危险 Shell 护栏**：拦截危险 Shell 删除操作，降低误删风险。
*   **取证分级提示**：全局事实取证风险提示按凭证重合度分级。
*   **检索与路由**：优化知识库检索触发与单轮意图解耦；事实证据契约与路由冲突治理。
*   **图表契约**：统一 ECharts 输出契约，修复 quick 括号截断；流式对账支持嵌套括号。

### 7. 🗄️ 运维与体验加固
*   **记忆索引**：记忆索引未就绪时提供快捷创建入口。
*   **AI 润色权限**：智能体版本编辑器 AI 润色不再依赖提示词工坊权限。

---

## 🐛 Bug Fixes

### MCP / 权限 / 运维
*   **普通用户发布 MCP**：修复普通用户发布 MCP 工具权限问题。
*   **禁用后误同步**：修复 MCP 服务禁用后仍误同步、发布状态未正确生效。
*   **apply-sql 相对路径**：MySQL / PostgreSQL 的 apply-sql 均可正确解析相对路径 SQL 文件。
*   **MCP 默认服务名**：规范默认服务名文案。

### AI / ChatBI / 知识库
*   **知识库工具步校验**：修复工具步校验、审计日志截断与 Markdown 表格滚动。
*   **知识库检索触发**：优化检索触发逻辑，与单轮意图解耦，减少误触发。
*   **事实证据与路由**：优化证据契约及路由冲突治理。
*   **ECharts / 流式对账**：修复 quick 目标括号截断；支持嵌套括号对账。
*   **已保存报告浮层**：打开报告详情时关闭浏览器浮层遮挡。

### 前端 / Embed / 管理端
*   **滚动条抖动**：修复鼠标悬停导致的页面滚动条抖动；消除模型管理页抖动。
*   **重复 Toast**：移除 Embed 多智能体开关的重复 Toast。
*   **模型表单文案**：移除 API 字段标签中多余的「可选」文案。
*   **注册表交互**：优化高级设置与选择器交互。

---

## ⚠️ Breaking Changes & Migration Notes

> 从 v1.0.8 升级至 v1.0.9 时，请特别注意以下变更：

| 项目 | 说明 |
| :--- | :--- |
| **平台主库可选 PostgreSQL** | 新增 `DATABASE_TYPE=postgresql` 与 `POSTGRES_*`；平台智能体元数据可落 PG。MySQL 与 PG **两套脚本链并行**，不可混用同一库。 |
| **MySQL 存量升级** | 继续使用 MySQL 时，须执行 `db-prod/` 的 `V105` ~ `V111`（见下方）。 |
| **PostgreSQL 新装 / 升级** | 新环境执行 `db-prod-pg/` 基线（`V0` 起）；已有 PG 环境执行对应增量（本版对齐能力见 `V3` ~ `V9`，以目录为准）。 |
| **MCP 作用域与命名** | 新增 `scope` / `user_id`；显示名全局唯一。历史重名会自动重命名为带 `legacy-*` 后缀，依赖旧重名配置的绑定请核对。 |
| **MCP 工具可用性** | 远端已删除工具不再静默消失，而以不可用状态保留；发布态与可用性分离，请回归同步与启停流程。 |
| **模型 model_id 唯一** | `ai_models.model_id` 强制全局唯一；存在重复时 MySQL **V110** / PG 对应脚本会失败，须先手工清理重复后再执行迁移。 |
| **模型 Token 限额** | 可选 `context_size` / `max_output_tokens`；`NULL` 保持供应商默认行为。 |
| **Embedding 默认** | 记忆服务默认模型改为 bge-m3、维度 1024；若已有记忆索引基于旧维度，需按运维指引重建或迁移向量。 |
| **案例集分类** | `ai_chatbi_examples` 新增 `category`；经验检索工具依赖注册脚本。 |

---

## 🗄️ Database Incremental Upgrades (数据库增量升级说明)

### MySQL（`db-prod/`，存量默认路径）

从 v1.0.8 升级至 v1.0.9，MySQL 主库引入 **7 个**增量脚本：

| 脚本文件 | 核心变更内容 |
| :--- | :--- |
| **[V105-add_mcp_scope_and_user_id.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V105-add_mcp_scope_and_user_id.sql)** | MCP 服务增加 `scope` / `user_id`；注册 MCP 管理菜单权限。 |
| **[V106-add_category_to_chatbi_examples.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V106-add_category_to_chatbi_examples.sql)** | ChatBI 案例表增加 `category` 分类列。 |
| **[V107-register_example_search_tool.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V107-register_example_search_tool.sql)** | 注册内置工具 `search_qa_examples`。 |
| **[V108-enforce_mcp_server_name_uniqueness.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V108-enforce_mcp_server_name_uniqueness.sql)** | MCP 显示名全局唯一；历史重名追加 `legacy-*`。 |
| **[V109-add_mcp_tool_availability.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V109-add_mcp_tool_availability.sql)** | MCP 工具缓存增加 `is_available`（远端是否仍存在）。 |
| **[V110-enforce_ai_model_id_uniqueness.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V110-enforce_ai_model_id_uniqueness.sql)** | `ai_models.model_id` 全局唯一索引（重复须先清理）。 |
| **[V111-add_ai_model_token_limits.sql](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod/V111-add_ai_model_token_limits.sql)** | 模型增加可选 `context_size` / `max_output_tokens`。 |

### PostgreSQL（`db-prod-pg/`，平台主库新选项）

新装 PostgreSQL 主库请按 [db-prod-pg/README.md](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/db-prod-pg/README.md) 执行 `V0-baseline` 及后续增量。本版能力对齐的增量包括（编号与 MySQL 不同）：

| 脚本（示例） | 核心变更内容 |
| :--- | :--- |
| **V0-baseline** | 平台当前态全量基线（智能体元数据等）。 |
| **V3 ~ V9** | MCP 作用域/唯一性/可用性、案例分类、经验检索工具、`model_id` 唯一与 Token 限额等（与 MySQL V105~V111 能力对齐）。 |

> [!WARNING]
> MySQL 请执行 `./db-prod/apply-sql-native.sh`；PostgreSQL 请执行 `./db-prod-pg/apply-sql.sh`。**勿**对同一实例混跑两套目录。执行 model_id 唯一约束前请确认不存在重复。

---

## 📦 Upgrade Guide

### 从 v1.0.8 升级（继续 MySQL）

```bash
# 1. 拉取最新代码
git fetch origin && git checkout main && git pull origin main

# 2. 更新依赖
source .venv/bin/activate
pip install -r requirements.txt

# 3. 执行数据库迁移（V105 ~ V111）
./db-prod/apply-sql-native.sh

# 4. 重新编译前端并启动
cd frontend && npm install && npm run build && cd ..
./dev.sh
```

### 新装 / 切换为 PostgreSQL 主库

```bash
# 配置 DATABASE_TYPE=postgresql 与 POSTGRES_*（见 env.example / HOW_TO_INSTALL.md）
./db-prod-pg/apply-sql.sh
# 然后编译前端并启动
```

---

## ✅ Test Checklist

升级后建议验证以下核心场景：

- [ ] **PostgreSQL 主库**：`DATABASE_TYPE=postgresql` 启动成功；登录、智能体 CRUD、会话与审计读写正常；与 MySQL 路径互不混用。
- [ ] **MCP 作用域**：创建个人/公共 MCP；显示名冲突拒绝；绑定智能体展示；禁用后不同步。
- [ ] **MCP 可用性**：远端删除工具后标记不可用仍可见；发布态与可用性独立。
- [ ] **案例集 / 经验库**：案例分类；`search_qa_examples` 可检索；`get_myinfo` 优先本人资料。
- [ ] **模型注册表**：`model_id` 唯一；Token 限额可选；使用关系展示；本轮运行时模型身份可查。
- [ ] **Embedding**：全局向量模型配置生效；记忆索引未就绪时快捷创建。
- [ ] **知识库 / Embed**：工具步绑定引导与折叠；调度占位动效；移动端表格自适应；无边框消息。
- [ ] **安全 / 取证**：危险 Shell 删除被护栏拦截；取证风险按重合度分级提示。
- [ ] **图表 / 流式**：ECharts quick 嵌套括号不截断；已保存报告详情无浮层遮挡。
- [ ] **缺陷回归**：滚动条/管理页不抖动；MCP 发布权限；apply-sql 相对路径；重复 Toast 已消除。
- [ ] **回归测试**：运行 `pytest tests/`，确保全部测试用例通过。

完整测试清单见 [tests/CHECKLIST.md](https://github.com/RandyChen1985/nanzi-ai-agent-platform/blob/main/tests/CHECKLIST.md)。

---

## 📋 Commit Log

| Hash | 描述 |
| :--- | :--- |
| `cb36b9cc` | docs: 更新微信交流群二维码图片 |
| `fcdc0cc8` | feat(agents): 智能体卡片技能数展示启用公共技能总量 |
| `13296432` | feat(embedding): 记忆与系统配置统一使用全局向量模型 |
| `a3f753f6` | fix(ui): 修复鼠标悬停导致的页面滚动条抖动 |
| `5d8cc855` | fix(ui): 移除模型表单 API 字段标签中的「可选」文案 |
| `563ee194` | docs(tests): 补充运行时模型查询与注册表治理验收清单 |
| `64077986` | feat(models): 完善模型使用关系展示并消除管理页抖动 |
| `9fa07996` | feat(models): 完善注册表解析与管理台筛选能力 |
| `5bfdfe26` | fix(ui): 优化模型注册表高级设置与选择器交互 |
| `4d3603a0` | feat(models): 强化模型注册表安全与供应商接入能力 |
| `16f6572d` | feat(ai): 支持查询本轮实际生效的运行时模型身份 |
| `ef1f8662` | fix(chatbi): 打开已保存报告详情时关闭浏览器浮层 |
| `6aa58ae1` | fix(ai): 流式对账支持 quick 目标内嵌套括号 |
| `7b113b99` | feat(chart): 统一 ECharts 输出契约并修复 quick 括号截断 |
| `29a6384d` | fix(ai): 优化事实证据契约与路由冲突治理 |
| `c4d8d0fb` | docs(tests): 补充危险 Shell 删除护栏验收清单条目 |
| `50f7ece9` | fix(ai): 优化知识库检索触发逻辑与单轮意图解耦 |
| `a908db18` | feat(security): guard dangerous shell deletions |
| `753fc8c3` | docs: define dangerous shell deletion guard |
| `f4031284` | feat(frontend): 移动端 AI 回复 Markdown 表格自适应卡片/表格切换 |
| `eca96cbf` | docs: 深化 A03/A04 公众号连载并补充克制配色版 |
| `6a32dd4f` | feat(embed): 优化调度占位动效，三点跳动与名称淡入上滑 |
| `5c70b7f7` | docs: 更新微信群二维码图片 |
| `13000424` | feat(grounding): 全局事实取证风险提示按凭证重合度分级 |
| `7c0a5e22` | feat(mcp): 远端已删除工具标记不可用并保留可见，完善重命名迁移与权限校验 |
| `09679703` | feat(mcp): 美化工具测试台结果展示，并完善启停加载态 |
| `750032e4` | feat(mcp): 展示服务绑定智能体，并修复禁用后误同步与发布状态生效 |
| `963830e0` | fix(ui): 记忆索引未就绪时提供快捷创建，并规范 MCP 默认服务名 |
| `198134c2` | feat(mcp): 强制服务显示名全局唯一，并优化 SSE/HTTP 探测与欢迎语文案 |
| `4c511416` | feat: 智能体版本编辑器 AI 润色不再依赖提示词工坊权限 |
| `fe13d8fa` | feat: 新增 get_myinfo 工具并优先处理本人资料查询 |
| `c12efe12` | fix: MySQL apply-sql 支持相对路径解析 SQL 文件 |
| `1354a3c8` | fix: PostgreSQL apply-sql 支持相对路径解析 SQL 文件 |
| `7814e95d` | fix(mcp,skills): 更新Skills官方市场链接并修复普通用户发布MCP工具权限问题 |
| `83c5bb5a` | UI: 淡化 EmbedChat 思考过程的时间轴竖线 |
| `be9a0ebc` | UI: 优化 EmbedChat 中 Markdown 多个主题的表格样式 |
| `f3f365e5` | fix: 移除 Embed 多智能体开关的重复 Toast 提示 |
| `9bf8cffa` | docs: 更新测试清单记录 Embed 调度占位与无边框样式 |
| `277089af` | fix: Embed 思考中显示调度占位并优化无边框消息样式 |
| `4ab64d0d` | feat: 知识库工具步默认折叠 ChatBI，并支持隐藏 AI 消息外框 |
| `2bedf2f0` | feat: 知识库智能体工具步增加绑定引导提示 |
| `47c89014` | fix: 知识库智能体工具步校验、审计日志截断与 Markdown 表格滚动优化 |
| `6dba8b22` | feat: 新增内置工具 search_qa_examples (检索经验库) |
| `b364c2be` | feat: 案例集管理全面优化、通用化重构及 MCP 个人作用域支持 |
| `04d4de62` | feat: 调整记忆服务 Embedding 默认模型为 bge-m3 与向量维度为 1024 |
| `6dc0e7ad` | feat: add PostgreSQL support and harden audit logs |
| `e1533ca4` | docs: 恢复 release_log_wechat.html 墨色版并新增灰蓝 v2 |
| `4e1fcade` | docs: 恢复 release_log_wechat.html 墨色版并新增灰蓝 v2 |

---

## 🤝 Contributors

感谢所有参与 v1.0.9 版本发布的开发者！
