# 模型思考模式配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为模型管理高级设置增加思考模式配置的持久化、接口校验、表单编辑和测试，但不接入任何运行时请求逻辑。

**Architecture:** `AIModel` 保存三个布尔开关、一个默认强度字符串和一个 JSON 数组字符串；Pydantic Schema 对外暴露为强类型列表并负责校验，Portal endpoint 在写库时序列化列表、读库时反序列化。Vue 模型管理表单在现有高级设置面板中增加开关和强度控件，思考模式关闭时仅隐藏相关控件而保留值。

**Tech Stack:** Python 3.11、FastAPI、Pydantic 2、SQLAlchemy 2、MySQL/PostgreSQL 增量 SQL、Vue 3、TypeScript、pytest。

---

## 文件结构与职责

- Create: `db-prod/V116-add_ai_model_thinking_config.sql` — MySQL 幂等迁移。
- Create: `db-prod-pg/V15-add_ai_model_thinking_config.sql` — PostgreSQL 幂等迁移。
- Modify: `app/models/ai_model.py` — 增加模型配置列。
- Modify: `app/schemas/ai_model.py` — 增加强度常量、JSON 反序列化和请求校验。
- Modify: `app/api/portal/endpoints/models.py` — 创建/更新时把强度列表序列化为数据库文本。
- Modify: `frontend/src/api/model.ts` — 同步 API 类型。
- Modify: `frontend/src/components/system/ModelRegistry.vue` — 高级设置 UI、默认值、回显和保存 payload。
- Modify: `tests/test_model_management.py` — API 默认值、持久化和非法配置测试。
- Create: `tests/frontend/test_model_thinking_config_contract.py` — Vue 源码契约测试。

### Task 1: Write backend API tests first

**Files:**
- Modify: `tests/test_model_management.py`

- [ ] **Step 1: Add default and round-trip tests**

新增两个异步测试：创建模型时不传思考字段，断言响应为 `thinking_enabled=False`、`thinking_only=False`、`allow_disable_thinking=True`、`default_reasoning_effort="auto"`、`supported_reasoning_efforts=["low", "high", "max"]`；第二个测试传入完整配置后，断言创建响应和更新响应保持相同列表顺序和值。

- [ ] **Step 2: Add validation tests**

使用参数化请求覆盖三种 422 情况：`default_reasoning_effort="invalid"`、`supported_reasoning_efforts=[]`、默认强度为 `high` 但列表只有 `low`。请求仍使用现有 `admin_headers` fixture 和唯一 `model_id`。

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/test_model_management.py -k 'thinking or reasoning' -q
```

Expected: FAIL because the response schema、数据库模型和接口尚未包含新字段。

### Task 2: Add database migrations

**Files:**
- Create: `db-prod/V116-add_ai_model_thinking_config.sql`
- Create: `db-prod-pg/V15-add_ai_model_thinking_config.sql`

- [ ] **Step 1: Add MySQL migration**

为 `ai_models` 逐列执行“检查 `information_schema.columns` 后动态 `ALTER TABLE`”的幂等迁移，字段为：

```sql
thinking_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否启用思考模式'
thinking_only TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否仅允许思考模式'
allow_disable_thinking TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否允许用户关闭思考'
default_reasoning_effort VARCHAR(32) NOT NULL DEFAULT 'auto' COMMENT '默认思考强度'
supported_reasoning_efforts TEXT NULL COMMENT '支持的思考强度 JSON 数组'
```

迁移末尾用 `UPDATE ai_models SET supported_reasoning_efforts = '["low","high","max"]' WHERE supported_reasoning_efforts IS NULL OR supported_reasoning_efforts = ''` 补齐旧记录；不得修改 V111 或 V115。

- [ ] **Step 2: Add PostgreSQL migration**

使用 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 添加同名字段：布尔字段用 `BOOLEAN NOT NULL DEFAULT FALSE/TRUE`，默认强度用 `VARCHAR(32) NOT NULL DEFAULT 'auto'`，支持列表用 `TEXT`。使用一条幂等 `UPDATE` 为旧数据写入 JSON 数组，并用 `COMMENT ON COLUMN` 写入与 MySQL 对齐的说明。

- [ ] **Step 3: Run migration contract checks**

Run:

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/test_pg_prod_apply_sql.py -q
git diff --check
```

Expected: 迁移文件存在、只新增版本文件，空白检查通过；不启动服务、不连接真实数据库。

### Task 3: Implement backend model and schema contract

**Files:**
- Modify: `app/models/ai_model.py`
- Modify: `app/schemas/ai_model.py`

- [ ] **Step 1: Add ORM columns and schema constants**

在 `AIModel` 增加五列；在 Schema 文件增加固定顺序常量 `REASONING_EFFORT_VALUES = ("low", "high", "max")`，以及允许默认值的 `REASONING_EFFORT_OPTIONS = ("auto", *REASONING_EFFORT_VALUES)`。

- [ ] **Step 2: Add normalization and validation**

Schema 对外字段类型为 `list[str]`。使用 `mode="before"` 的字段校验器把 ORM 中的 JSON 文本解析为列表；请求列表必须是非空字符串列表、只能包含 `low`、`high`、`max` 三种强度、去重后按固定顺序输出。默认值允许为 `auto`，或必须存在于支持列表中。无效输入抛出 Pydantic 422。

- [ ] **Step 3: Extend create/update/response schemas**

`AIModelBase` 与 `AIModelUpdate` 增加五字段，默认值分别为设计文档定义的值；`AIModelResponse` 继承这些字段，保证旧数据库记录经过默认迁移后能正常返回列表而不是原始 JSON 文本。

### Task 4: Serialize the list at the Portal boundary

**Files:**
- Modify: `app/api/portal/endpoints/models.py`

- [ ] **Step 1: Add one serialization helper**

在 endpoint 文件中增加 `_serialize_reasoning_efforts(value: list[str]) -> str`，使用 `json.dumps(value, ensure_ascii=False, separators=(",", ":"))`，只负责数据库写入格式。

- [ ] **Step 2: Apply it on create and update**

创建接口在 `model_in.model_dump()` 后、构造 `AIModel` 前序列化 `supported_reasoning_efforts`；更新接口仅在该字段出现在 `exclude_unset=True` 的 payload 中时序列化，确保只更新名称或 API 地址不会覆盖原有强度配置。

- [ ] **Step 3: Keep connection tests unchanged**

不要把思考字段加入 `_test_model_connection` 或 `AIModelTestRequest` 的调用参数，保持本阶段“只配置、不接入运行时”的边界。

- [ ] **Step 4: Run backend tests and verify they pass**

Run:

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/test_model_management.py -k 'thinking or reasoning' -q
```

Expected: 新增测试 PASS。

### Task 5: Add frontend API types and form state

**Files:**
- Modify: `frontend/src/api/model.ts`
- Modify: `frontend/src/components/system/ModelRegistry.vue`

- [ ] **Step 1: Extend TypeScript model types**

增加 `ReasoningEffort = 'low' | 'high' | 'max'`，并在 `AIModel`、`AIModelCreate`、`AIModelUpdate` 中增加 `thinking_enabled`、`thinking_only`、`allow_disable_thinking`、`default_reasoning_effort` 和 `supported_reasoning_efforts`。

- [ ] **Step 2: Initialize defaults and constants**

在 `ModelRegistry.vue` 增加固定选项数组，包含 value/label；新建模型初始化为设计默认值。打开编辑、克隆时使用接口返回值；对缺失字段使用默认值，兼容迁移前缓存或旧响应。

- [ ] **Step 3: Preserve values when hidden**

将“思考模式”开关绑定到 `modelForm.thinking_enabled`。相关参数区域使用 `v-if` 或现有可访问性折叠模式，仅控制显示，不在关闭时修改 `thinking_only`、`allow_disable_thinking`、默认强度和支持列表。

### Task 6: Implement the advanced-settings UI

**Files:**
- Modify: `frontend/src/components/system/ModelRegistry.vue`

- [ ] **Step 1: Add thinking-mode capsule after token limits**

在现有“输出上限”之后增加与截图一致的胶囊式“思考模式”开关和说明；关闭时隐藏其他思考配置。

- [ ] **Step 2: Add dependent controls**

打开思考模式后显示“仅思考模式”“允许关闭思考”两个 checkbox，以及“默认思考强度”下拉和低/高/极致三个支持强度 checkbox。支持列表至少保留一个选项；取消当前默认强度时，自动切换到当前仍选中的第一个强度；默认值为 `auto` 时不需要选中 `auto`。

- [ ] **Step 3: Update configured indicator and save payload**

“高级设置”的已配置提示同时检查上下文、输出和五个新增字段；创建/更新 payload 原样发送五个字段，保留现有 API Key 脱敏和旧 provider/type 兼容逻辑。

### Task 7: Add frontend contract tests

**Files:**
- Create: `tests/frontend/test_model_thinking_config_contract.py`

- [ ] **Step 1: Assert the UI contract**

源码契约测试读取 `ModelRegistry.vue` 和 `frontend/src/api/model.ts`，断言存在五个字段、三个强度值、思考模式控制、依赖显示条件、编辑/克隆初始化路径和保存 payload 字段；同时断言没有把思考字段写入 Chat/Embed 请求路径。

- [ ] **Step 2: Run frontend contract and type checks**

Run:

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_model_thinking_config_contract.py -q
cd frontend && npm run type-check
```

Expected: 契约测试和 `vue-tsc --noEmit` PASS。

### Task 8: Run the focused regression suite and review the diff

**Files:**
- No new files; verify all files above.

- [ ] **Step 1: Run focused backend and frontend tests**

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/test_model_management.py tests/test_pg_prod_apply_sql.py -q
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_model_thinking_config_contract.py -q
```

- [ ] **Step 2: Review scope and whitespace**

```bash
git diff --check
git status --short
git diff --stat
```

确认没有修改模型运行时、聊天请求、Embed、AgentDebug 或 `docs/release/1.0.9`；不运行 `./dev.sh`、部署脚本或真实数据库迁移。

- [ ] **Step 3: Commit the implementation**

```bash
git add app db-prod db-prod-pg frontend/src tests
git commit -m "feat: 增加模型思考模式配置"
```
