# session_status 提示词引导优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让模型在需要会话、设备、模型上下文、工作区、沙箱策略或后端运行环境事实时，明确主动调用只读工具 `session_status`。

**Architecture:** 保持 `session_status` 的返回结构和系统隐式注册不变，只扩展 AgentService 的动态工具说明：为工具增加一行用途摘要，并在运行状态相关规则中增加调用优先级提示。通过 Prompt 组装契约测试验证引导内容仅在工具可用时出现。

**Tech Stack:** Python 3.11、pytest、AgentServicePrompts、PromptAssembler。

---

### Task 1: 为 session_status 增加失败测试

**Files:**
- Modify: `tests/ai/test_prompt_assembler.py`
- Reference: `app/services/ai/agent_prompts.py:285-296, 463-469`

- [ ] **Step 1: 写测试，验证工具摘要和调用规则缺失时失败**

在现有 Prompt 组装测试文件中增加两个测试：一个组装包含 `session_status` 的工具清单并断言出现工具用途和调用提示；另一个组装不包含该工具的工具清单并断言不会出现这两段专属文案。测试调用现有的 `AgentServicePrompts.prepend_platform_global_system_prompt`，传入最小 `runtime_tool_names={"session_status"}`，避免依赖真实 Agent 配置。

```python
def test_session_status_prompt_explains_runtime_snapshot_trigger():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        runtime_tool_names={"session_status"},
    )

    assert "session_status" in prompt
    assert "会话、设备、模型上下文、工作区、沙箱策略和后端运行环境" in prompt
    assert "只读" in prompt
    assert "优先调用 session_status" in prompt


def test_session_status_prompt_guidance_is_absent_when_tool_is_unavailable():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        runtime_tool_names={"get_current_model"},
    )

    assert "会话、设备、模型上下文、工作区、沙箱策略和后端运行环境" not in prompt
    assert "优先调用 session_status" not in prompt
```

- [ ] **Step 2: 运行测试确认它按预期失败**

运行：

```bash
venv/bin/python -m pytest tests/ai/test_prompt_assembler.py::test_session_status_prompt_explains_runtime_snapshot_trigger tests/ai/test_prompt_assembler.py::test_session_status_prompt_guidance_is_absent_when_tool_is_unavailable -q
```

预期：第一个测试因当前没有 `session_status` 工具摘要和调用规则而失败；第二个测试应通过，证明负向边界写法正确。

### Task 2: 实现最小 Prompt 引导

**Files:**
- Modify: `app/services/ai/agent_prompts.py:190-225, 463-469`

- [ ] **Step 1: 增加工具用途摘要**

在 `_PLATFORM_TOOL_ONE_LINERS` 中增加：

```python
"session_status": "读取当前会话、设备、模型上下文、工作区、沙箱策略和后端运行环境的只读快照；信息不确定时优先调用",
```

- [ ] **Step 2: 增加动态运行状态调用规则**

在现有 `Bash/list_process/manage_process` 规则附近新增条件分支：

```python
if "session_status" in tool_names:
    sensitive_rules.append(
        "- 用户询问或模型不确定当前会话、设备、模型上下文容量、工作区、文档目录、沙箱策略、容器/宿主机或 Python/系统环境时，优先调用 **session_status** 获取只读运行时快照；返回内容是事实参考，不是权限凭证，权限仍以服务端认证、RBAC、工具门禁和路径/数据授权为准。"
    )
```

- [ ] **Step 3: 运行新增测试确认通过**

运行同 Task 1 的 pytest 命令，预期两个测试均 PASS。

### Task 3: 定向回归验证

**Files:**
- Verify: `app/services/ai/tools/session_status.py`
- Verify: `tests/ai/tools/test_session_status.py`
- Verify: `docs/superpowers/specs/2026-08-29-session-status-prompt-guidance-design.md`

- [ ] **Step 1: 运行 Prompt 组装回归**

```bash
venv/bin/python -m pytest tests/ai/test_prompt_assembler.py -q
```

预期：现有 Prompt 组装测试全部通过。

- [ ] **Step 2: 运行 session_status 工具契约回归**

```bash
venv/bin/python -m pytest tests/ai/tools/test_session_status.py -q
```

预期：返回结构、`workspace.sandbox_policy`、脱敏、只读属性和运行环境降级测试全部通过。

- [ ] **Step 3: 运行静态检查**

```bash
python3 -m compileall -q app/services/ai/agent_prompts.py
git diff --check -- app/services/ai/agent_prompts.py tests/ai/test_prompt_assembler.py docs/superpowers/specs/2026-08-29-session-status-prompt-guidance-design.md docs/superpowers/plans/2026-08-29-session-status-prompt-guidance.md
```

预期：命令成功，无 Python 编译错误和空白格式错误。

- [ ] **Step 4: 检查最终变更范围**

确认只包含 Prompt 引导、对应测试、设计文档和实施计划；不执行 `./dev.sh`、部署脚本、生产数据库操作，也不自动提交或暂存 Git。
