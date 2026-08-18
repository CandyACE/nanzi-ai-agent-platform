# ChatBI 精确总行数与样例行数 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 ChatBI 明确区分数据库匹配总数、实际返回明细数和模型分析样例数，禁止把 `LIMIT 1000` 后的返回行数当成总记录数。

**Architecture:** 在 SQL 执行完成权限重写和沙箱优化后，基于同一条最终 SQL 构造独立的精确 `COUNT(*)` 查询；明细查询仍保留最多 1,000 行的安全上限。执行结果统一携带 `total_count`、`returned_count`、`truncated` 和计数状态，ChatBI 压缩、依据卡、SSE 元数据和前端只消费这些显式字段，缺少精确计数时必须展示“总数未统计”，不能回退冒充总数。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.x、sqlglot、pytest、Vue 3、TypeScript。

---

### Task 1: 增加跨方言的精确 COUNT SQL 构造与执行结果元数据

**Files:**
- Modify: `app/services/sql_query_execution_service.py`
- Modify: `app/services/ai/tools/data_api.py`
- Create: `tests/services/test_sql_result_count.py`
- Test: `tests/test_sql_routing.py`
- Test: `tests/ai/tools/test_data_api.py`

- [ ] **Step 1: Write the failing tests**

覆盖以下事实：

```python
def test_build_count_sql_removes_top_level_limit_and_order_for_mysql():
    sql = "SELECT * FROM t WHERE event_date = '2025-11-01' ORDER BY id LIMIT 1000"
    count_sql = build_unbounded_count_sql(sql, dialect="mysql")
    assert count_sql == (
        "SELECT COUNT(*) FROM "
        "(SELECT * FROM t WHERE event_date = '2025-11-01') AS _count_query"
    )


def test_build_count_sql_uses_oracle_alias_syntax():
    sql = "SELECT * FROM t FETCH FIRST 1000 ROWS ONLY"
    count_sql = build_unbounded_count_sql(sql, dialect="oracle")
    assert "COUNT(*)" in count_sql.upper()
    assert "FETCH FIRST" not in count_sql.upper()
    assert " AS _COUNT_QUERY" not in count_sql.upper()


@pytest.mark.asyncio
async def test_local_sql_result_contains_exact_total_and_returned_count():
    adapter = MagicMock()
    adapter.execute_sql = AsyncMock(
        side_effect=[
            {"columns": [{"name": "_total_count"}], "items": [[238]]},
            {"columns": [{"name": "id"}], "items": [[1], [2]]},
        ]
    )
    result = await call_external_sql_api(
        "SELECT * FROM t WHERE event_date = '2025-11-01' LIMIT 1000",
        data_source="mysql_test",
    )
    payload = json.loads(result)
    assert payload["total_count"] == 238
    assert payload["returned_count"] == 2
    assert payload["truncated"] is False
    assert payload["count_status"] == "exact"
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
venv/bin/python -m pytest tests/test_sql_routing.py tests/ai/tools/test_data_api.py -q
```

Expected: FAIL because the current executor only returns `columns/items`; it does not expose a count builder or `total_count` metadata.

- [ ] **Step 3: Implement the smallest execution-layer change**

在 `app/services/sql_query_execution_service.py` 增加 `from sqlglot import exp`，并增加一个纯函数 `build_unbounded_count_sql(sql, dialect)`：

```python
def build_unbounded_count_sql(sql: str, dialect: str) -> str:
    expression = sqlglot.parse_one(sql.strip().rstrip(";"), read=to_sqlglot_dialect(dialect))
    expression.set("limit", None)
    expression.set("offset", None)
    expression.set("order", None)
    count_query = exp.select(exp.Count(this=exp.Star())).from_(expression.subquery("_count_query"))
    return count_query.sql(dialect=to_sqlglot_dialect(dialect))
```

改造 `call_external_sql_api` 时保留原明细查询的 1,000 行上限，但在最终明细执行前/后对同一条去掉顶层分页的 SQL 执行一次 `COUNT(*)`：

不要只修改数据源管理的 `adapter.preview(include_total=True)`：它是 SQL Lab 调试接口，ChatBI 主路径调用的是 `execute_sql_query` → `execute_sql_query_core` → `call_external_sql_api`，两条链路必须分别验证。

- 本地模式：使用同一个 adapter 执行 count SQL 和受限明细 SQL。
- 远程模式：对外部 SQL API 发起一次 count 请求和一次明细请求，并合并响应。
- count 成功时返回 `count_status="exact"`、`total_count`、`returned_count=len(items)`、`truncated=returned_count < total_count`。
- count 失败时仍返回明细，但返回 `count_status="unknown"`、`total_count=null`，不能把 `len(items)` 写成精确总数。
- count 失败只记录受控的 `count_error` 分类，不把外部数据库连接串、凭证或完整错误 SQL 回传给模型。
- 将缓存 key 升级为 `sql_result:v2:...`，避免旧的无总数缓存继续污染结果。

- [ ] **Step 4: Run the execution tests and verify they pass**

Run:

```bash
venv/bin/python -m pytest tests/test_sql_routing.py tests/ai/tools/test_data_api.py -q
```

Expected: PASS，并验证本地、远程、缓存隔离和跨方言分页 SQL 均保留原行为。

---

### Task 2: 修复模型结果压缩和 ChatBI SSE 元数据的总数口径

**Files:**
- Modify: `app/services/ai/runners/chatbi/sql_result_compact.py`
- Modify: `app/services/ai/runners/chatbi/insight_meta.py`
- Modify: `app/services/ai/chatbi_citation_utils.py`
- Modify: `app/services/ai/executors/prompts.py`
- Test: `tests/ai/runners/test_chatbi_sql_result_compact.py`
- Test: `tests/ai/runners/test_chatbi_insight_meta.py`
- Test: `tests/ai/test_chatbi_citation_utils.py`

- [ ] **Step 1: Write the failing regression tests**

新增一个“数据库总数 238、返回 238 行”和一个“数据库总数 5,000、返回 1,000 行”的结果样例：

```python
def test_compact_uses_explicit_exact_total_instead_of_len_rows():
    payload = {
        "columns": [{"name": "id"}],
        "items": [[i] for i in range(1000)],
        "total_count": 5000,
        "returned_count": 1000,
        "truncated": True,
        "count_status": "exact",
    }
    compact = json.loads(compact_sql_result_for_model(_FakeRunner(), json.dumps(payload)))
    assert compact["total_row_count"] == 5000
    assert compact["returned_row_count"] == 1000
    assert compact["sample_row_count"] == 500
    assert compact["truncated"] is True


def test_compact_does_not_claim_exact_total_when_count_is_unknown():
    payload = {
        "columns": [{"name": "id"}],
        "items": [[i] for i in range(1000)],
        "returned_count": 1000,
        "truncated": True,
        "count_status": "unknown",
    }
    compact = json.loads(compact_sql_result_for_model(_FakeRunner(), json.dumps(payload)))
    assert compact["total_row_count"] is None
    assert "总数未统计" in compact["_model_context_note"]


def test_model_result_scope_keeps_unknown_total_explicit():
    payload = json.dumps({
        "items": [[i] for i in range(1000)],
        "returned_count": 1000,
        "truncated": True,
        "count_status": "unknown",
    })
    scope = build_model_result_scope(_FakeRunner(), payload)
    assert scope["mode"] == "sample"
    assert scope["total_row_count"] is None
    assert scope["model_row_count"] == 500
    assert "总数未统计" in scope["user_notice"]
```

同步断言 `build_chatbi_insight_meta` 的 `table.total_row_count` 使用 `total_count`，`embedded_row_count` 使用实际嵌入行数；`execution` 同时输出 `total_row_count` 和 `returned_row_count`。

- [ ] **Step 2: Run the regression tests and verify they fail**

Run:

```bash
venv/bin/python -m pytest tests/ai/runners/test_chatbi_sql_result_compact.py tests/ai/runners/test_chatbi_insight_meta.py tests/ai/test_chatbi_citation_utils.py -q
```

Expected: FAIL because `sql_result_compact.py` 和 `insight_meta.py` 当前都使用 `len(rows)`。

- [ ] **Step 3: Implement explicit count precedence**

在 `sql_result_compact.py` 统一解析：

```python
explicit_total = parsed.get("total_count") if isinstance(parsed, dict) else None
count_status = parsed.get("count_status") if isinstance(parsed, dict) else None
total = int(explicit_total) if count_status == "exact" and explicit_total is not None else None
returned = len(rows)
```

规则固定为：

- `count_status == "exact"`：使用 `total_count`。
- `count_status == "unknown"`：`total_row_count` 保持 `None`，文案使用“已返回 N 行，数据库总数未统计”。
- 仅兼容没有分页/截断元数据的旧测试数据时，才允许 `len(rows)` 作为本地 full 结果；真实执行结果必须由 Task 1 写入计数状态。

修改 `_model_context_note`，明确区分“全部总数”“返回行数”“模型样例数”，禁止再生成“返回 1,000 行 = 总数 1,000”的提示。

修改 `insight_meta.py`：

- `table.total_row_count` 使用显式精确总数；
- `table.embedded_row_count` 使用实际嵌入行数；
- `table.truncated` 使用执行层 `truncated` 或 `total_count > returned_count`；
- `execution` 增加 `total_row_count`、`returned_row_count`、`truncated`；
- 既有 `row_count` 暂时保留，兼容前端，但语义改为返回行数并在下一任务切换显示。
- `analysis_scope.total_row_count` 和 `table.total_row_count` 允许为 `null`，总数未知时不能用返回行数填充。

修改 SQL citation 文案：有精确总数时显示“匹配总数 X，当前返回 Y 行”；没有精确总数时显示“当前返回 Y 行，总数未统计”。

更新 `GLOBAL_GUARDRAILS`：模型只能读取 `total_count` 作为总数，`items` 长度只能表示返回行数；若总数未知，必须如实说明。

- [ ] **Step 4: Run the ChatBI regression tests**

Run:

```bash
venv/bin/python -m pytest tests/ai/runners/test_chatbi_sql_result_compact.py tests/ai/runners/test_chatbi_insight_meta.py tests/ai/test_chatbi_citation_utils.py -q
```

Expected: PASS，并保留现有大结果抽样、重复 SQL 缓存和依据卡测试。

---

### Task 3: 修复前端展示契约并做端到端静态回归

**Files:**
- Modify: `frontend/src/types/chatbiInsight.ts`
- Modify: `frontend/src/components/chatbi/ChatBIInsightPanel.vue`
- Modify: `tests/frontend/test_chatbi_insight_contract.py`

- [ ] **Step 1: Write the failing frontend contract assertions**

断言类型和面板同时具备以下字段/文案：

```python
assert "total_row_count: number | null" in types
assert "returned_row_count?: number" in types
assert "truncated?: boolean" in types
assert "匹配总数" in panel
assert "已返回" in panel
assert "总数未统计" in panel
```

- [ ] **Step 2: Run the frontend contract test and verify it fails**

Run:

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chatbi_insight_contract.py -q
```

Expected: FAIL because the current panel只显示 `查询成功 · {{ rowCount }} 行`，没有区分总数和返回数。

- [ ] **Step 3: Implement the minimal frontend contract change**

将类型扩展为可兼容旧 SSE 的可选字段：

```typescript
execution: {
  mode: "direct" | "repaired" | "federated";
  row_count: number;
  total_row_count?: number | null;
  returned_row_count?: number;
  truncated?: boolean;
  repair_count?: number;
  federated?: boolean;
};

interface ChatBIResultTable {
  total_row_count: number | null;
  embedded_row_count: number;
  truncated?: boolean;
}

interface ChatBIAnalysisScope {
  mode: "full" | "sample";
  total_row_count: number | null;
  model_row_count: number;
  user_notice?: string;
}
```

面板展示规则：

- 精确总数存在：`查询成功 · 匹配总数 238 行`；
- 被截断：追加 `已返回 1,000 行`；
- 总数未知：显示 `已返回 1,000 行 · 总数未统计`；
- `AI 样例 500/总数未知` 或 `AI 样例 500/5000` 只表示模型上下文范围，不再承担数据库总数含义。

- [ ] **Step 4: Run the frontend contract test**

Run:

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chatbi_insight_contract.py -q
```

Expected: PASS。

---

### Task 4: 集中验证截图场景并交付

**Files:**
- Test: `tests/ai/runners/test_chatbi_sql_result_compact.py`
- Test: `tests/ai/runners/test_chatbi_insight_meta.py`
- Test: `tests/services/test_sql_result_count.py`
- Test: `tests/test_sql_routing.py`
- Test: `tests/ai/tools/test_data_api.py`
- Check: `git diff --check`

- [ ] **Step 1: Add the exact screenshot regression**

固定以下断言：同一过滤条件下真实总数为 238 时，最终模型上下文和 SSE 元数据均为 238；当明细返回达到 1,000 行时，只有 `returned_count` 是 1,000，`total_count` 必须来自独立 COUNT 查询。

- [ ] **Step 2: Run the focused validation set**

```bash
venv/bin/python -m pytest \
  tests/test_sql_routing.py \
  tests/ai/tools/test_data_api.py \
  tests/services/test_sql_result_count.py \
  tests/ai/runners/test_chatbi_sql_result_compact.py \
  tests/ai/runners/test_chatbi_insight_meta.py \
  tests/ai/test_chatbi_citation_utils.py \
  --confcutdir=tests/frontend -q
```

Expected: all selected tests pass；若需要真实数据库验证，再由用户启动服务并使用同一 `data_source`、`dataset_name` 执行截图中的 `COUNT(*)` 与明细 SQL 对照。

- [ ] **Step 3: Run static checks**

```bash
python3 -m compileall -q app/services/ai/tools/data_api.py app/services/sql_query_execution_service.py app/services/ai/runners/chatbi
git diff --check
```

Expected: no Python compilation error and no whitespace error.

- [ ] **Step 4: Stop for user review**

不自动运行 `./dev.sh`，不操作生产数据库，不 stage/commit。完成代码和测试后汇报变更文件、测试结果以及仍需用户在控制台验证的真实数据源结果。
