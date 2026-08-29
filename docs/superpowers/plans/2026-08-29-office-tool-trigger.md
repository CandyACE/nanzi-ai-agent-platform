# Office 工具自然语言触发优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户使用中文自然语言表达 Word/Excel 读取、生成、保存、导出或修改意图时，稳定优先调用当前运行时已绑定的对应 Office 工具。

**Architecture:** 在现有 `resolve_tool_nudge()` 的通用相关度匹配之前增加一个仅针对四个 Office 工具的确定性意图解析器。解析器只从本轮实际 `tools` 集合中选择工具，并通过现有 `ToolNudge(force_first_call=True)` 接入 `AssistantAgentRunner`；写入工具继续走现有 `ask` 权限确认。动态系统提示增加与运行时工具集合一致的 Office 使用规则，并明确 Office 写工具已经返回工件下载地址，避免重复调用通用发布工具。

**Tech Stack:** Python 3.11、FastAPI 服务层、AgentScope 工具运行时、pytest。

---

## 文件边界

- Modify: `app/services/ai/tool_nudge_policy.py`，新增 Office 文件类型、读写动作和显式工具名的确定性解析，保留现有通用匹配及其他专用规则。
- Modify: `app/services/ai/agent_prompts.py`，按运行时工具集合注入 Office 读写规则，并处理 Office 写工具与 `publish_generated_file` 的边界。
- Test: `tests/ai/test_tool_nudge_policy.py`，覆盖四个工具、显式工具名、未挂载工具、歧义和下载误判。
- Test: `tests/ai/test_prompt_assembler.py`，覆盖动态 Office 提示和通用文件发布提示的兼容性。
- Reference only: `docs/superpowers/specs/2026-08-29-office-tool-trigger-design.md`，实现依据，不修改设计目标。

### Task 1: Add failing deterministic Office nudge tests

**Files:**
- Modify: `tests/ai/test_tool_nudge_policy.py`

- [ ] **Step 1: Add a helper fixture set and failing cases for Word/Excel read/write intent**

在现有 `_tool()` helper 和工具促发测试附近加入以下测试。测试使用 `SimpleNamespace` 模拟 AgentScope 工具，只验证预检结果，不启动模型或服务：

```python
def _office_tools(*names):
    descriptions = {
        "word_document_read": "读取 Word 文档结构或内容",
        "word_document_write": "创建或修改 Word 文档并生成可下载文件",
        "excel_document_read": "读取 Excel 工作簿结构或单元格区域",
        "excel_document_write": "创建或修改 Excel 副本并生成可下载文件",
    }
    return [_tool(name, descriptions[name]) for name in names]


@pytest.mark.parametrize(
    ("query", "tool_name"),
    [
        ("读取这个 Word 文档的内容", "word_document_read"),
        ("帮我查看 Excel 的 A1:C10", "excel_document_read"),
        ("把刚才内容保存为 Word 文档并给我下载地址", "word_document_write"),
        ("把这些数据导出为 Excel 文件", "excel_document_write"),
    ],
)
def test_office_nudge_uses_deterministic_chinese_intent(query, tool_name):
    nudge = resolve_tool_nudge(query, _office_tools(
        "word_document_read",
        "word_document_write",
        "excel_document_read",
        "excel_document_write",
    ))

    assert nudge is not None
    assert nudge.tool_name == tool_name
    assert nudge.should_force_first_call is True


def test_office_explicit_tool_name_keeps_original_tool_name():
    nudge = resolve_tool_nudge(
        "请调用 word_document_write 保存这份内容",
        _office_tools("word_document_write"),
    )

    assert nudge is not None
    assert nudge.tool_name == "word_document_write"
    assert "word_document_write" in nudge.message
    assert nudge.should_force_first_call is True


def test_office_nudge_requires_the_target_tool_to_be_mounted():
    assert resolve_tool_nudge(
        "把内容保存为 Word 文档",
        _office_tools("excel_document_write"),
    ) is None


def test_existing_file_download_request_does_not_force_office_write():
    assert resolve_tool_nudge(
        "请给我这个已有 Word 文件的下载地址",
        _office_tools("word_document_write"),
    ) is None


def test_office_type_ambiguity_does_not_force_a_tool():
    assert resolve_tool_nudge(
        "请把这份文档保存并提供下载地址",
        _office_tools("word_document_write", "excel_document_write"),
    ) is None
```

- [ ] **Step 2: Run only the new tests and verify they fail for the intended reason**

Run:

```bash
.venv/bin/pytest tests/ai/test_tool_nudge_policy.py -k 'office_nudge or office_explicit or existing_file_download or office_type_ambiguity' -q
```

Expected before implementation: the natural-language cases return `None` or the generic matcher returns no deterministic Office nudge, so at least the first parameterized test and the `force_first_call` assertions fail. No unrelated test failure should be introduced by this step.

### Task 2: Implement the Office intent resolver

**Files:**
- Modify: `app/services/ai/tool_nudge_policy.py: around _resolve_explicit_user_question_nudge and resolve_tool_nudge`

- [ ] **Step 1: Add explicit Office vocabularies and four-tool mapping**

在现有通用常量之后增加稳定、可审计的映射和动作词：

```python
_OFFICE_TOOL_NAMES = frozenset({
    "word_document_read",
    "word_document_write",
    "excel_document_read",
    "excel_document_write",
})
_OFFICE_EXPLICIT_TOOL_NAMES = (
    "word_document_read",
    "word_document_write",
    "excel_document_read",
    "excel_document_write",
)
_OFFICE_WORD_TERMS = ("word", "docx", "word文档", "文字文档")
_OFFICE_EXCEL_TERMS = ("excel", "xlsx", "excel表格", "电子表格", "工作簿")
_OFFICE_READ_TERMS = (
    "读取", "查看", "看看", "打开", "解析", "检查结构", "查看内容",
    "读取段落", "读取单元格", "查看工作表",
)
_OFFICE_WRITE_TERMS = (
    "生成", "创建", "制作", "保存", "保存为", "保存到", "导出为", "导出成",
    "转成", "转换为", "修改", "替换", "追加", "整理成", "编辑",
)
_OFFICE_DOWNLOAD_TERMS = ("给我下载地址", "提供下载", "下载链接", "下载地址")
```

动作词必须在 `_normalize()` 后比较；显式工具名则直接从规范化查询中匹配完整工具名。目标工具只能从当前传入的 `tools` 集合中选择。

- [ ] **Step 2: Implement `_resolve_office_tool_nudge()` with explicit-name priority and safe write detection**

新增函数签名和核心逻辑如下，函数返回 `Optional[ToolNudge]`，不修改工具对象：

```python
def _resolve_office_tool_nudge(
    query: str,
    tools: List[Any],
    metadata_by_name: Optional[Mapping[str, ToolMetadata]] = None,
) -> Optional[ToolNudge]:
    normalized = _normalize(query)
    available = {
        str(getattr(tool, "name", "") or "").strip(): tool
        for tool in tools or []
        if str(getattr(tool, "name", "") or "").strip() in _OFFICE_TOOL_NAMES
    }
    if not available:
        return None

    explicit_name = next(
        (
            name
            for name in _OFFICE_EXPLICIT_TOOL_NAMES
            if name in normalized and name in available
        ),
        None,
    )
    if explicit_name:
        return _build_office_tool_nudge(
            explicit_name, available[explicit_name], score=1.0,
            explicit=True, metadata_by_name=metadata_by_name,
        )

    if any(term in normalized for term in _OFFICE_WORD_TERMS):
        family = "word"
    elif any(term in normalized for term in _OFFICE_EXCEL_TERMS):
        family = "excel"
    else:
        return None

    has_read = any(term in normalized for term in _OFFICE_READ_TERMS)
    has_write = any(term in normalized for term in _OFFICE_WRITE_TERMS)
    has_download = any(term in normalized for term in _OFFICE_DOWNLOAD_TERMS)
    if not has_write and not has_download and not has_read:
        return None
    if not has_write and has_download:
        return None

    operation = "write" if has_write else "read"
    tool_name = f"{family}_document_{operation}"
    tool = available.get(tool_name)
    if tool is None:
        return None
    return _build_office_tool_nudge(
        tool_name, tool, score=1.0, explicit=False,
        metadata_by_name=metadata_by_name,
    )
```

`_build_office_tool_nudge()` 负责生成中文提示，写入提示必须包含现有确认和 `artifact.download_url` 约束，读取提示必须强调以工具真实结果为准；两者都设置 `force_first_call=True` 并调用 `resolve_tool_metadata()`。显式工具名的循环要按固定元组顺序实现，避免使用无序 set 导致结果不稳定。

- [ ] **Step 3: Insert the resolver after multi-step/todo precedence and before generic relevance matching**

在 `resolve_tool_nudge()` 中保留现有顺序：互动提问、子代理显式委派、`todo_write` 多步骤、知识/目录/通知等特殊规则先处理；在进入 `signals = _query_signals(query)` 之前加入：

```python
    office_nudge = _resolve_office_tool_nudge(
        query,
        tools,
        metadata_by_name=tool_metadata,
    )
    if office_nudge is not None:
        return office_nudge
```

这样“先读取再生成”的多步骤请求仍由已存在的 `todo_write` 规则优先；单步骤 Office 请求才由 Office 解析器确定性选择。更新 `resolve_tool_nudge()` 的 docstring，说明通用相关度之外存在已绑定 Office 工具的专用预检规则。

- [ ] **Step 4: Run the focused nudge tests and the complete nudge module**

Run:

```bash
.venv/bin/pytest tests/ai/test_tool_nudge_policy.py -k 'office_nudge or office_explicit or existing_file_download or office_type_ambiguity' -q
.venv/bin/pytest tests/ai/test_tool_nudge_policy.py -q
```

Expected: new cases and all existing tool-nudge tests pass. If an existing special-rule test fails, adjust only the Office insertion point or guard so that non-Office requests retain their previous result.

### Task 3: Add failing dynamic-prompt contract tests

**Files:**
- Modify: `tests/ai/test_prompt_assembler.py`

- [ ] **Step 1: Add tests for bound Office tools and publish compatibility**

在现有 `publish_generated_file` 提示测试之后加入：

```python
def test_platform_prompt_describes_bound_office_read_write_tools():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        runtime_tool_names={
            "word_document_read",
            "word_document_write",
            "excel_document_read",
            "excel_document_write",
        },
    )

    assert "word_document_read" in prompt
    assert "word_document_write" in prompt
    assert "excel_document_read" in prompt
    assert "excel_document_write" in prompt
    assert "Word/Excel" in prompt
    assert "artifact.download_url" in prompt
    assert "必须优先调用对应的 *_read 工具" in prompt
    assert "必须优先调用对应的 *_write 工具" in prompt


def test_platform_prompt_does_not_claim_unbound_office_tools():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        runtime_tool_names={"word_document_write"},
    )

    assert "word_document_write" in prompt
    assert "excel_document_write" not in prompt
    assert "excel_document_read" not in prompt


def test_platform_prompt_office_write_does_not_require_duplicate_publish():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        runtime_tool_names={"word_document_write", "publish_generated_file"},
    )

    assert "word_document_write" in prompt
    assert "不要再次调用 publish_generated_file" in prompt
```

- [ ] **Step 2: Run the new prompt tests and verify they fail before implementation**

Run:

```bash
.venv/bin/pytest tests/ai/test_prompt_assembler.py -k 'bound_office or unbound_office or office_write' -q
```

Expected: the new Office-specific assertions fail because当前动态提示没有 Office 规则；原有 `publish_generated_file` 测试应继续通过。

### Task 4: Implement dynamic Office prompt rules without changing tool schemas

**Files:**
- Modify: `app/services/ai/agent_prompts.py: around dynamic table_rows construction`

- [ ] **Step 1: Add bound Office tool detection and prompt rows**

在动态 `table_rows` 构建前计算当前实际绑定的工具：

```python
        office_read_tools = {
            name for name in (
                "word_document_read",
                "excel_document_read",
            ) if name in tool_names
        }
        office_write_tools = {
            name for name in (
                "word_document_write",
                "excel_document_write",
            ) if name in tool_names
        }
        office_tools = office_read_tools | office_write_tools

        if office_tools:
            table_rows.append(
                "| 用户要求读取、查看或解析 Word/Excel 文件 | "
                "必须优先调用当前已绑定的对应 `*_read` 工具获取真实内容；"
                "不要仅凭模型记忆或普通文字承诺已读取 |"
            )
            table_rows.append(
                "| 用户要求生成、创建、保存、导出或修改 Word/Excel 文件 | "
                "必须优先调用当前已绑定的对应 `*_write` 工具；"
                "写入仍需遵循工具权限确认 |"
            )
```

只在对应工具名存在时注入规则，不能因为只绑定 Word 写工具就声称 Excel 读写能力可用。工具清单仍由原有 `runtime_tool_names`/配置解析逻辑决定。

- [ ] **Step 2: Make the generic publish row explicitly compatible with Office writes**

替换现有 `publish_generated_file` 单一提示分支，使包含 Office 写工具时使用兼容文案：

```python
        if "publish_generated_file" in tool_names:
            if office_write_tools:
                table_rows.append(
                    "| 用户要求保存、交付、导出或下载已生成文件 | "
                    "普通文件工具生成文件后才调用 `publish_generated_file(path=...)`；"
                    "Word/Excel 的 `*_write` 已经登记 artifact 并返回 `artifact.download_url`，"
                    "不要再次调用 `publish_generated_file`；只有拿到真实 `download_url` 才能向用户提供下载地址 |"
                )
            else:
                table_rows.append(
                    "| 用户要求保存、交付、导出或下载已生成文件 | "
                    "文件写入/生成完成后必须调用 **publish_generated_file(path=...)**；"
                    "只有返回 `status=ok` 且包含 `download_url` 才能声称已生成下载地址；"
                    "最终必须原样复制 `download_url`，不得返回物理路径或臆造链接 |"
                )
```

不要更改 `ToolMetadata`、工具 schema、Office 工具的 artifact 注册或通用发布工具执行逻辑。

- [ ] **Step 3: Run prompt and existing prompt-assembler tests**

Run:

```bash
.venv/bin/pytest tests/ai/test_prompt_assembler.py -k 'office or publish_generated_file' -q
.venv/bin/pytest tests/ai/test_prompt_assembler.py -q
```

Expected: new Office prompt assertions和全部已有 prompt assembler tests均通过。

### Task 5: Full focused verification and review

**Files:**
- No new production files.
- Review: `app/services/ai/tool_nudge_policy.py`, `app/services/ai/agent_prompts.py`, `tests/ai/test_tool_nudge_policy.py`, `tests/ai/test_prompt_assembler.py`

- [ ] **Step 1: Run the combined regression set**

Run:

```bash
.venv/bin/pytest tests/ai/test_tool_nudge_policy.py tests/ai/test_prompt_assembler.py -q
git diff --check -- app/services/ai/tool_nudge_policy.py app/services/ai/agent_prompts.py tests/ai/test_tool_nudge_policy.py tests/ai/test_prompt_assembler.py
```

Expected: both test modules pass and `git diff --check`无输出、退出码为 0。

- [ ] **Step 2: Manually review behavior-preserving boundaries**

核对以下结果后再交付：

```text
自然语言“保存为 Word 并给下载地址” + word_document_write 已绑定
  => ToolNudge(word_document_write, force_first_call=True)

自然语言“读取 Excel 的 A1:C10” + excel_document_read 已绑定
  => ToolNudge(excel_document_read, force_first_call=True)

自然语言“给已有 Word 文件下载地址” + 仅 word_document_write 已绑定
  => Office nudge 为 None

未绑定目标 Office 工具
  => 不注入虚假 Office 规则，不产生 Office nudge

Office 写工具成功
  => 继续使用现有 ask 权限和 artifact.download_url，不增加第二次发布调用
```

- [ ] **Step 3: Report scope and live-acceptance boundary**

汇报修改文件、聚焦测试结果和未执行的 live acceptance。根据仓库协作规则，不自动执行 `./dev.sh`、Docker 部署、服务重启、暂存或提交；如需提交，等待用户明确要求。

## Review hardening applied

代码审查后补充了以下安全边界，并已加入回归测试：

- 否定表达（如“无需调用”“请勿调用”）不会触发 Office 工具。
- 工具说明、工具比较和同时点名多个 Office 工具不会强制选择其中一个。
- 只有文件类型、没有读取/写入动作时，Office 工具不会落入通用相关度匹配；其他明确相关工具仍可正常匹配。
- 动态提示按实际绑定的 Word/Excel 工具家族生成，不夸大未绑定的文件类型能力。
