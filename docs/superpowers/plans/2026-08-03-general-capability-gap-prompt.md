# General Capability Gap Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a task-type-independent platform prompt that guides agents to compose existing capabilities or create a temporary script when no dedicated tool fully matches, without granting new permissions or silently installing dependencies.

**Architecture:** Add one static section to `AgentServicePrompts` and append it from `prepend_platform_global_system_prompt()` alongside the existing execution and tool-call sections. Keep runtime tool discovery, Tool Nudge scoring, permission checks, and code execution unchanged; use prompt contract tests to verify the new behavior and existing dynamic approval boundaries.

**Tech Stack:** Python 3.11+, pytest, existing `AgentServicePrompts` prompt assembler.

---

### Task 1: Add failing prompt contract tests

**Files:**
- Modify: `tests/ai/test_prompt_assembler.py`
- Test: `tests/ai/test_prompt_assembler.py`

- [x] **Step 1: Write the failing tests**

Add these tests after the existing global prompt contract tests:

```python
def test_platform_prompt_guides_generic_capability_gap_recovery():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=["Bash", "Write"]),
    )

    assert "任务能力缺口与临时方案" in prompt
    assert "优先使用当前已绑定的专用工具、Skill、MCP 和隐式工具" in prompt
    assert "检查命令、解释器和依赖" in prompt
    assert "优先使用已有依赖或标准库" in prompt
    assert "安装软件包、浏览器、命令行工具或其他运行依赖" in prompt
    assert "等待用户确认" in prompt
    assert "当前会话工作区" in prompt


def test_platform_prompt_degrades_without_execution_capability():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=[]),
    )

    assert "没有对应执行能力时，只能输出方案、代码或待执行文件" in prompt
    assert "不得声称已经完成" in prompt
    assert "不得通过提示词自行扩大工具权限" in prompt
    assert "注册正式工具或 MCP" in prompt


def test_platform_prompt_keeps_existing_sensitive_tool_confirmation():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=["Bash"]),
    )

    assert "## 任务能力缺口与临时方案" in prompt
    assert "## 工具确认" in prompt
    assert "不得声称已执行" in prompt
```

- [x] **Step 2: Run the focused tests and verify they fail for the intended reason**

Run:

```bash
venv/bin/python -m pytest tests/ai/test_prompt_assembler.py -q
```

Expected: the existing prompt tests pass, and the three new tests fail because the new section has not yet been added.

### Task 2: Implement the minimal generic prompt section

**Files:**
- Modify: `app/services/ai/agent_prompts.py:68-90,260-268`

- [x] **Step 1: Add the static prompt section**

Add this class constant after `_PLATFORM_TOOL_CALL_STYLE_SECTION`:

```python
    _PLATFORM_CAPABILITY_GAP_SECTION = """## 任务能力缺口与临时方案
- 先明确用户要交付的结果、输入、范围和可能的外部影响；优先使用当前已绑定的专用工具、Skill、MCP 和隐式工具。
- 如果没有完全匹配的能力，评估当前已绑定的工具能否组合完成；在具备 Bash、文件或代码执行能力时，可以生成临时脚本、配置或辅助程序，但不得把临时程序当成已注册的平台工具。
- 执行前先检查命令、解释器和依赖；优先复用已有依赖或标准库，避免不必要的安装。
- 如需安装软件包、浏览器、命令行工具或其他运行依赖，先说明名称、用途、来源、影响范围和风险，并等待用户确认；未确认前不得声称已安装或继续执行该安装动作。
- 获得确认后，临时脚本和辅助文件优先放入当前会话工作区；执行后验证实际结果，并按用户要求保存或交付。
- 涉及外部写入、批量修改、发送消息、删除文件、付费、生产变更或其他明显副作用时，必须单独请求确认。
- 没有对应执行能力时，只能输出方案、代码或待执行文件，并明确说明未实际执行；不得声称已经完成。
- 提示词不能扩大工具权限、访问其他用户或会话资源、注册正式工具或 MCP；长期复用需求应建议走正式工具、Skill 或 MCP 配置流程。
"""
```

- [x] **Step 2: Inject the section for every platform prompt**

Append the constant immediately after `_PLATFORM_TOOL_CALL_STYLE_SECTION` is appended:

```python
        prompt_parts.append(AgentServicePrompts._PLATFORM_CAPABILITY_GAP_SECTION)
```

Keep it unconditional so the no-tool branch receives the explicit “cannot claim execution” fallback, while the text itself distinguishes what is possible only when execution tools are bound.

- [x] **Step 3: Run the focused tests and verify they pass**

Run:

```bash
venv/bin/python -m pytest tests/ai/test_prompt_assembler.py -q
```

Expected: all tests in the file pass, including the three new capability-gap tests.

### Task 3: Validate the touched prompt module and worktree

**Files:**
- No additional files.

- [x] **Step 1: Compile the changed Python module**

Run:

```bash
venv/bin/python -m py_compile app/services/ai/agent_prompts.py tests/ai/test_prompt_assembler.py
```

Expected: exit code 0 and no output.

- [x] **Step 2: Run the related workspace prompt contracts**

Run:

```bash
venv/bin/python -m pytest tests/ai/test_prompt_assembler.py tests/ai/runtime/test_workspace_prompt.py -q
```

Expected: all tests pass; this confirms the new global section coexists with the existing workspace and tool-confirmation prompt behavior.

- [x] **Step 3: Check whitespace and review the diff**

Run:

```bash
git diff --check
git diff -- app/services/ai/agent_prompts.py tests/ai/test_prompt_assembler.py
```

Expected: no whitespace errors; only the new prompt section and its focused tests are changed. Do not start `./dev.sh` or any service script.
