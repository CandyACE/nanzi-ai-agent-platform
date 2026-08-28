# 智能体版本级工具调用超时 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为智能体版本增加可选工具调用超时，并按版本级优先、全局次之统一生效。

**Architecture:** 在 `ai_agent_versions` 增加可空版本级秒数字段，沿现有 AgentManager/ChatConfig 链路传入 AgentScope runners。统一超时模块按版本级非空、全局、默认值的顺序选择单一超时；工具规格和工具 timeout 参数不覆盖该值；工具能力页签顶部使用继承开关、数字输入和 1 秒步进按钮编辑该字段。

**Tech Stack:** Python 3.11、FastAPI、Pydantic 2、SQLAlchemy 2 async、Vue 3、TypeScript、pytest、vue-tsc。

---

### Task 1: 为配置优先级和版本字段补充失败测试

**Files:**
- Modify: `tests/ai/runtime/test_agent_tool_timeout.py`
- Create: `tests/services/test_agent_version_toolcall_timeout.py`
- Create: `tests/test_agent_version_toolcall_timeout_migration_contract.py`
- Modify: `tests/frontend/test_agent_max_toolcall_timeout_contract.py`
- Create: `tests/frontend/test_agent_version_toolcall_timeout_contract.py`

- [ ] **Step 1: 写运行时红测**

在现有 `test_agent_tool_timeout.py` 中验证统一配置按优先级选择，不与工具配置取最大值，并增加版本值参与的断言：

```python
assert effective_tool_timeout(120.0, 30.0, 45.0) == 120.0
assert effective_tool_timeout(120.0, 300.0, 45.0) == 120.0
```

同时增加版本覆盖的调用断言，要求 `apply_configured_agent_tool_timeout(specs, agent_timeout=30)` 在全局 45 秒时仍将工具规格超时设为 30 秒。

- [ ] **Step 2: 写 schema/服务红测**

在 `tests/services/test_agent_version_toolcall_timeout.py` 中验证：

```python
from app.schemas.agent import AIAgentVersionBase

assert AIAgentVersionBase(system_prompt="x", toolcall_timeout_seconds=None).toolcall_timeout_seconds is None
assert AIAgentVersionBase(system_prompt="x", toolcall_timeout_seconds=86400).toolcall_timeout_seconds == 86400
```

并用 `pytest.raises` 验证 0、86401、1.5 和 `"abc"` 被拒绝。

- [ ] **Step 3: 写迁移和前端红测**

迁移契约测试要求 MySQL/PG 迁移包含 `toolcall_timeout_seconds`、可空定义和 86400 注释；前端契约测试要求工具页签在搜索框前出现该字段、继承开关、`type="number"`、`inputmode="numeric"`、`min="1"`、`max="86400"`、键盘/输入/失焦处理函数。

- [ ] **Step 4: 运行红测**

Run:

```bash
.venv/bin/python -m pytest --confcutdir=tests/frontend \
  tests/ai/runtime/test_agent_tool_timeout.py \
  tests/services/test_agent_version_toolcall_timeout.py \
  tests/test_agent_version_toolcall_timeout_migration_contract.py \
  tests/frontend/test_agent_max_toolcall_timeout_contract.py \
  tests/frontend/test_agent_version_toolcall_timeout_contract.py -q
```

Expected: FAIL，失败原因应是版本优先级尚未实现、schema 没有版本字段、迁移和版本工具页控件尚未存在。

### Task 2: 实现版本字段、接口链路和配置优先级运行时策略

**Files:**
- Modify: `app/models/agent.py`
- Modify: `app/schemas/agent.py`
- Modify: `app/services/ai/agent_manager.py`
- Modify: `app/services/ai/runtime/agentscope/tool_timeout.py`
- Modify: `app/services/ai/runtime/agentscope/tools.py`
- Modify: `app/services/ai/runners/assistant_agent_runner.py`
- Modify: `app/services/ai/runners/knowledge_agent_runner.py`
- Modify: `app/services/ai/runtime/agentscope/data_tools.py`
- Modify: `app/services/ai/runtime/agentscope/workspace.py`

- [ ] **Step 1: 增加可空版本字段**

在 SQLAlchemy 模型增加：

```python
toolcall_timeout_seconds = Column(Integer, nullable=True)
```

在 `AIAgentVersionBase` 和 `AIAgentVersionResponse` 链路增加 `Optional[int]`，用 Pydantic `Field(default=None, ge=1, le=86400)` 约束版本级值，并保留 `None` 表示继承全局。

- [ ] **Step 2: 让 AgentManager 创建/更新/读取字段**

在 `create_agent_version` 和 `update_agent_version` 分别写入 `data.toolcall_timeout_seconds`；在 `get_active_agent_config` 和 `get_version_config` 构造 `ChatConfig` 时传入 `getattr(version, "toolcall_timeout_seconds", None)`。旧数据库对象缺少/返回 NULL 时保持 `None`。

- [ ] **Step 3: 改造统一策略为配置优先级**

在 `tool_timeout.py` 增加版本级上限常量和解析函数；保留全局解析范围 1–3600。调整计算函数：版本级有效值优先，否则使用全局值，最后回退默认值；工具规格和显式工具参数不再抬高或降低统一值；`apply_agent_tool_timeout` 和 `apply_configured_agent_tool_timeout` 接收 `agent_timeout`。

目标接口：

```python
async def apply_configured_agent_tool_timeout(
    specs: Sequence[Any] | Iterable[Any],
    *,
    agent_timeout: Any = None,
) -> list[Any]:
    ...
```

并保证 `apply_agent_tool_timeout(specs, global_timeout, agent_timeout=30)` 传出的每个 spec 都为 30 秒，即使全局为 300 秒。

- [ ] **Step 4: 统一工具入参不再压短有效配置**

在 `_prepare_timeout_arguments` 中保留秒/毫秒单位转换，但始终用已选定的统一配置值重写显式 `timeout`；普通 callable、native 工具、异步生成器继续复用同一外层 timeout。

- [ ] **Step 5: 从 runners 和 workspace 传入版本值**

将 Assistant、Knowledge、ChatBI 和工作区构建入口调用统一策略时传入：

```python
getattr(self.config, "toolcall_timeout_seconds", None)
```

工作区工具和普通工具必须使用同一最终值，避免仅工具列表生效而 Bash/Read/Write 等 native 工具仍使用全局值。

- [ ] **Step 6: 运行后端红测转绿**

Run:

```bash
.venv/bin/python -m pytest --confcutdir=tests/frontend \
  tests/ai/runtime/test_agent_tool_timeout.py \
  tests/services/test_agent_version_toolcall_timeout.py -q
```

Expected: PASS。

### Task 3: 增加 MySQL/PostgreSQL 迁移

**Files:**
- Create: `db-prod/V133-add-agent-version-toolcall-timeout.sql`
- Create: `db-prod-pg/V33-add-agent-version-toolcall-timeout.sql`

- [ ] **Step 1: 写迁移**

MySQL 使用：

```sql
ALTER TABLE `ai_agent_versions`
  ADD COLUMN `toolcall_timeout_seconds` INT NULL
  COMMENT '智能体版本级工具调用超时时间（秒），NULL 表示跟随全局，范围 1-86400';
```

PostgreSQL 使用对应 `ALTER TABLE ... ADD COLUMN ... INTEGER NULL` 和 `COMMENT ON COLUMN`。遵循仓库迁移版本号，不修改基线 SQL。

- [ ] **Step 2: 运行迁移契约**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_version_toolcall_timeout_migration_contract.py -q
```

Expected: PASS。

### Task 4: 在工具能力页签增加版本级数字控件

**Files:**
- Modify: `frontend/src/api/agent.ts`
- Modify: `frontend/src/components/agent/AgentVersionEditorDrawer.vue`
- Modify: `frontend/src/views/AgentManagement.vue`

- [ ] **Step 1: 增加前端类型和表单默认值**

在 `AIAgentVersion` 增加：

```ts
toolcall_timeout_seconds?: number | null
```

新建版本默认设置为 `null`；编辑/克隆直接保留服务端字段；克隆版本只复制配置，不把历史发布状态带入。

- [ ] **Step 2: 实现数字输入归一化**

在 `AgentVersionEditorDrawer.vue` 增加开关、数字输入和按钮处理：键盘仅放行数字、编辑导航和快捷键；`input` 清除非数字；`blur` 将值收敛到 1–86400，空值回退 120；关闭专属配置时写回 `null`。

- [ ] **Step 3: 在工具页签顶部渲染控件**

将卡片放在工具搜索栏前，展示“跟随全局配置/使用智能体专属配置”状态。专属配置开启后显示 `−`、输入框、`+` 和“秒”，按钮步长 1，到达 1/86400 禁用；`canEditVersion` 为 false 时整体只读。

- [ ] **Step 4: 运行前端红测转绿**

Run:

```bash
.venv/bin/python -m pytest --confcutdir=tests/frontend \
  tests/frontend/test_agent_max_toolcall_timeout_contract.py \
  tests/frontend/test_agent_version_toolcall_timeout_contract.py -q
./node_modules/.bin/vue-tsc --noEmit
```

Expected: 两个契约测试 PASS，Vue 类型检查 PASS。

### Task 5: 聚焦回归与静态复核

**Files:**
- Review: all files listed above

- [ ] **Step 1: 运行聚焦测试**

Run:

```bash
.venv/bin/python -m pytest --confcutdir=tests/frontend \
  tests/ai/runtime/test_agent_tool_timeout.py \
  tests/services/test_agent_tool_timeout_config.py \
  tests/services/test_agent_version_toolcall_timeout.py \
  tests/test_agent_max_toolcall_timeout_migration_contract.py \
  tests/test_agent_version_toolcall_timeout_migration_contract.py \
  tests/frontend/test_agent_max_toolcall_timeout_contract.py \
  tests/frontend/test_agent_version_toolcall_timeout_contract.py \
  tests/frontend/test_system_config_save_bar_contract.py -q
```

Expected: 全部通过；如有基础设施连接失败，单独记录，不把它归因于本次改动。

- [ ] **Step 2: 做执行路径静态检查**

确认 `get_active_agent_config`、`get_version_config`、Assistant/Knowledge/ChatBI/workspace 都传递版本级字段，且所有工具包装最终调用 `effective_tool_timeout`。

- [ ] **Step 3: 做格式与状态检查**

Run:

```bash
git diff --check -- app frontend/src/api/agent.ts frontend/src/components/agent/AgentVersionEditorDrawer.vue frontend/src/views/AgentManagement.vue db-prod db-prod-pg tests docs/superpowers
git status --short
```

不执行 `./dev.sh`、部署、真实迁移，不自动暂存或提交。
