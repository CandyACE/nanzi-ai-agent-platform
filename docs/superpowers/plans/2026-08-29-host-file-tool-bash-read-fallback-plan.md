# 容器路径读工具 Bash 降级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 当 Docker 容器路径无法被宿主 Read/Glob/Grep 映射时，自动使用同一 Docker 沙箱的 Bash 完成只读操作，同时保持 Write/Edit 和越权路径的安全边界。

**Architecture:** 在 `workspace.py` 中把可选 sandbox Bash fallback 注入 Docker 文件工具包装器。包装器先执行宿主 LocalWorkspace；仅识别明确的 container-only 映射错误后，针对 Read/Glob/Grep 构造安全 Bash 命令并调用同一 Bash 工具。路径映射错误、宿主权限错误和 Bash 失败分别处理，不扩大授权范围。

**Tech Stack:** Python 3.11、AgentScope workspace/native tools、pytest、asyncio。

---

### Task 1: 明确并测试容器路径错误分类

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py`
- Test: `tests/ai/runtime/test_agentscope_workspace.py`

- [ ] **Step 1: Write the failing tests**

在 workspace 测试中增加一个明确的错误分类断言：只有包含 `container-only path cannot be used by host file tools` 的 `ValueError` 才允许进入 fallback；`path escapes Docker workspace` 和宿主权限错误不允许进入 fallback。

测试应调用待新增的 `_is_container_only_path_error(exc)`，并断言：

```python
assert _is_container_only_path_error(
    ValueError("container-only path cannot be used by host file tools: /workspace/skills/x")
)
assert not _is_container_only_path_error(ValueError("path escapes Docker workspace"))
assert not _is_container_only_path_error(PermissionError("文件访问被拒绝"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/frontend tests/ai/runtime/test_agentscope_workspace.py -k container_only_path_error`

Expected: FAIL，因为 `_is_container_only_path_error` 尚未定义。

- [ ] **Step 3: Write minimal implementation**

在 `workspace.py` 增加只按稳定错误文本判断的函数：

```python
def _is_container_only_path_error(exc: BaseException) -> bool:
    return (
        isinstance(exc, ValueError)
        and "container-only path cannot be used by host file tools" in str(exc).lower()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run同上，Expected: PASS。

### Task 2: 为读工具构造安全 Bash fallback 命令

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py`
- Test: `tests/ai/runtime/test_agentscope_workspace.py`

- [ ] **Step 1: Write the failing tests**

增加命令构造测试，覆盖 Read、Grep、Glob 和包含空格/引号的路径。测试只验证参数经过 `shlex.quote`，不执行任意拼接内容：

```python
read_command = _build_read_fallback_command("Read", {"file_path": "/workspace/public/docs/FAQ.md"})
assert read_command == "cat -- /workspace/public/docs/FAQ.md"

grep_command = _build_read_fallback_command(
    "Grep", {"pattern": "foo bar", "path": "/workspace/public/docs"}
)
assert grep_command == "grep -RIn --exclude-dir=.git -- 'foo bar' /workspace/public/docs"

glob_command = _build_read_fallback_command(
    "Glob", {"pattern": "*.md", "path": "/workspace/public/docs"}
)
assert "find /workspace/public/docs" in glob_command
assert "-name '*.md'" in glob_command
```

同时断言 `Write`/`Edit` 返回 `None`，不具备 fallback 命令。

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/frontend tests/ai/runtime/test_agentscope_workspace.py -k fallback_command`

Expected: FAIL，因为命令构造函数尚未定义。

- [ ] **Step 3: Write minimal implementation**

新增 `_build_read_fallback_command(tool_name, tool_input)`：

- Read：要求非空 `file_path`，生成 `cat -- <quoted-file-path>`；
- Grep：要求非空 `pattern`，默认路径 `/workspace`，生成固定参数的递归 `grep -RIn --exclude-dir=.git -- <pattern> <quoted-path>`；
- Glob：要求非空 `pattern`，默认路径 `/workspace`，生成 `find <quoted-path> -type f -name <quoted-pattern> -print`；
- 其他工具返回 `None`；
- 所有动态参数使用 `shlex.quote`，不接受命令片段或 shell 操作符。

- [ ] **Step 4: Run test to verify it passes**

Run同上，Expected: PASS。

### Task 3: 将 Bash fallback 注入 Docker 文件工具包装器

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py`
- Test: `tests/ai/runtime/test_agentscope_workspace.py`

- [ ] **Step 1: Write the failing tests**

新增绑定测试，使用 fake host Read 和 fake sandbox Bash：

- host Read 收到 `/workspace/skills/...` 时抛出 container-only `ValueError`；
- fallback Bash 记录命令并返回文本；
- `bound[0].callable(file_path=...)` 返回成功结果，且 Bash 被调用一次；
- host 可映射 `/workspace/sessions/...` 的 Read 仍只调用 host，不调用 Bash；
- Write/Edit 抛出同样错误时不调用 Bash，继续抛出原错误。

新增 `sandbox_bash` 参数到 `_DockerLogicalWorkspaceNativeTool`，并在 `bind_configured_tools_to_workspace()` 构造该包装器时传入已经解析出的 `sandbox_bash`。

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/frontend tests/ai/runtime/test_agentscope_workspace.py -k docker_file_tool_bash_fallback`

Expected: FAIL，因为现有 Docker wrapper 没有 fallback 参数或调用逻辑。

- [ ] **Step 3: Write minimal implementation**

实现逻辑：

```python
try:
    mapped_input = self._map(kwargs)
    result = await self._native_tool(**mapped_input)
except Exception as exc:
    if self.name not in {"Read", "Glob", "Grep"} or not _is_container_only_path_error(exc):
        raise
    command = _build_read_fallback_command(self.name, kwargs)
    if not command or self._fallback_bash is None:
        raise
    result = self._fallback_bash(command=command)
    if inspect.isawaitable(result):
        result = await result
```

fallback 只放在 `__call__` 的实际读取路径；权限预检仍由 `_WorkspaceFileAccessNativeTool` 执行。对于容器专属只读挂载，预检需要允许该特定映射错误到达 wrapper，但不允许普通越权路径通过。fallback 失败时保留原错误并追加 Bash 错误摘要，继续使用现有 `enhance_workspace_error_message()`。

- [ ] **Step 4: Run test to verify it passes**

Run同上，Expected: PASS。

### Task 4: 修正权限预检与结果包装的交互

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py`
- Test: `tests/ai/runtime/test_agentscope_workspace.py`

- [ ] **Step 1: Write the failing tests**

增加预检测试：

- 容器-only 的 Read 路径允许进入调用阶段，由 wrapper 负责 Bash fallback；
- `/workspace/other-user-secret`、`/tmp/secret` 和 `path escapes Docker workspace` 仍返回 DENY/抛出原错误；
- `check_permissions()` 不会因为 fallback 存在而把 Write/Edit 放宽。

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/frontend tests/ai/runtime/test_agentscope_workspace.py -k fallback_permission_boundary`

Expected: FAIL，现有路径预检会在 wrapper 之前阻断容器-only 路径，或测试暴露出授权范围扩大。

- [ ] **Step 3: Write minimal implementation**

只在 Docker 文件工具包装器的容器-only 映射错误场景下放行到调用层；保持 `_assert_workspace_file_access()` 对越界、其他用户目录和写操作的拒绝。Read/Glob/Grep 的 fallback 不得复用 `approval_mode` 绕过宿主授权；必须有明确的 Docker mount mapping 和已绑定的 sandbox Bash。

- [ ] **Step 4: Run test to verify it passes**

Run同上，Expected: PASS。

### Task 5: 回归验证并更新检查记录

**Files:**
- Modify: `tests/CHECKLIST.md`（仅当仓库约定要求本次测试项入表时）
- Test: `tests/ai/runtime/test_agentscope_workspace.py`, `tests/ai/runtime/test_agentscope_tooling.py`

- [ ] **Step 1: Run focused suite**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/frontend tests/ai/runtime/test_agentscope_tooling.py tests/ai/runtime/test_agentscope_workspace.py`

Expected: 所有相关测试通过，包含已有路径映射、权限边界和缺参测试。

- [ ] **Step 2: Run static checks**

Run: `git diff --check`

Expected: 无输出且退出码为 0。

- [ ] **Step 3: Review the final diff**

Run: `git status --short && git diff --stat && git diff -- app/services/ai/runtime/agentscope/workspace.py tests/ai/runtime/test_agentscope_workspace.py`

确认没有修改服务启动、部署、数据库或无关文件；不运行 `./dev.sh`。

- [ ] **Step 4: Commit the implementation**

仅在用户明确要求提交时执行：

```bash
git add app/services/ai/runtime/agentscope/workspace.py tests/ai/runtime/test_agentscope_workspace.py
git commit -m "fix: 容器路径读取失败时降级到 Bash"
```
