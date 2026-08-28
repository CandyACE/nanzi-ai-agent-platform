# Workspace Path Namespace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留 Bash 按沙箱策略执行、文件工具由后端侧执行的架构，同时让 Docker 沙箱路径与宿主文件工具路径可确定地互相转换。

**Architecture:** 建立以挂载点为来源的路径映射规则，采用最长前缀匹配处理 `/workspace/public/docs`、`/workspace/skills` 等覆盖挂载，再处理用户工作区主挂载。`Read/Write/Edit/Glob/Grep` 继续由后端 `LocalWorkspace` 执行，但可将属于共享用户工作区的 Docker 路径转换为后端路径；容器专属路径明确拒绝。`list_accessible_directories` 和提示词输出 `paths.bash`/`paths.file_tools` 与 `path_namespace`，不再让模型从多个同义字段猜用途。

**Tech Stack:** Python 3.11、FastAPI、AgentScope Workspace、pytest。

---

### Task 1: 固化路径命名空间与挂载映射行为

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py:2099-2154`
- Test: `tests/ai/runtime/test_agentscope_workspace.py`

- [x] **Step 1: Write the failing tests**

补充路径映射测试，覆盖最长前缀、共享用户目录和容器专属目录：

```python
def test_docker_path_mapping_prefers_public_docs_mount(tmp_path):
    host_root = tmp_path / "user"
    mapped = _map_docker_workspace_path(
        "/workspace/public/docs/FAQ.md",
        str(host_root),
        mount_mappings=[
            ("/workspace", str(host_root), "rw"),
            ("/workspace/public/docs", str(tmp_path / "data" / "docs"), "ro"),
        ],
    )
    assert mapped == str(tmp_path / "data" / "docs" / "FAQ.md")


def test_docker_path_mapping_keeps_shared_user_file_on_host_root(tmp_path):
    host_root = tmp_path / "user"
    mapped = _map_docker_workspace_path(
        "/workspace/docs/report.md",
        str(host_root),
        mount_mappings=[("/workspace", str(host_root), "rw")],
    )
    assert mapped == str(host_root / "docs" / "report.md")


def test_docker_path_mapping_rejects_unmapped_container_path(tmp_path):
    with pytest.raises(ValueError, match="container-only"):
        _map_docker_workspace_path(
            "/tmp/result.json",
            str(tmp_path / "user"),
            mount_mappings=[("/workspace", str(tmp_path / "user"), "rw")],
        )
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/ai/runtime/test_agentscope_workspace.py -q
```

Expected: FAIL because the current mapper accepts only `host_root`, has no child-mount table, and does not distinguish an unmapped container path.

- [x] **Step 3: Implement the minimal resolver behavior**

在 `workspace.py` 中增加内部挂载映射类型或等价的不可变结构，至少包含 `sandbox_prefix`、`backend_path`、`permission`；按 `sandbox_prefix` 长度降序匹配。用户主工作区作为兜底映射，未知的容器绝对路径不得被转换为用户路径。相对路径仍按当前文件工具根目录处理。

将 Docker 初始化时已有的主工作区、公共 docs、沙箱 skills 来源整理成同一份映射数据，避免 Docker 挂载配置和文件工具适配器各自维护路径规则。

- [x] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/ai/runtime/test_agentscope_workspace.py -q
```

Expected: PASS，且现有 workspace 工具测试不回归。

### Task 2: 让文件工具适配器使用统一映射，并保留 Bash 产物可读

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py:2130-2288, 2595-2670`
- Test: `tests/ai/runtime/test_agentscope_workspace.py`

- [x] **Step 1: Write the failing tests**

验证 Docker 模式下 `Read/Write/Glob/Grep` 的 native tool 收到的是后端路径，而不是 `/workspace` 路径；验证公共 docs 使用后端 docs 路径；验证 `/tmp` 等容器专属路径返回明确错误。

```python
@pytest.mark.asyncio
async def test_docker_read_maps_shared_workspace_path_to_backend_path(tmp_path):
    native = FakeReadTool()
    wrapped = _DockerLogicalWorkspaceNativeTool(
        native,
        str(tmp_path / "user"),
        mount_mappings=[
            ("/workspace", str(tmp_path / "user"), "rw"),
        ],
    )

    await wrapped(file_path="/workspace/docs/report.md")

    assert native.last_kwargs["file_path"] == str(
        tmp_path / "user" / "docs" / "report.md"
    )


@pytest.mark.asyncio
async def test_docker_read_rejects_container_only_path(tmp_path):
    native = FakeReadTool()
    wrapped = _DockerLogicalWorkspaceNativeTool(
        native,
        str(tmp_path / "user"),
        mount_mappings=[
            ("/workspace", str(tmp_path / "user"), "rw"),
        ],
    )

    with pytest.raises(ValueError, match="container-only"):
        await wrapped(file_path="/tmp/result.json")
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/ai/runtime/test_agentscope_workspace.py -q -k "docker_read or docker_path"
```

Expected: FAIL because the current wrapper maps only the generic `/workspace` prefix and does not use the child mount table or reject unmapped container paths.

- [x] **Step 3: Implement the minimal adapter change**

让 `_DockerLogicalWorkspaceNativeTool` 接收统一映射；对 `Read/Write/Edit` 的 `file_path` 和 `Glob/Grep` 的 `path` 使用同一解析器。映射完成后再执行现有 `_WorkspaceFileAccessNativeTool` 的用户权限检查，确保路径安全校验顺序不被绕过。

对共享用户工作区路径继续支持 `/workspace/docs/...`、`/workspace/sessions/...` 等输入，以便 Bash 创建的文件可以被宿主侧 Read 读取。对未挂载的 `/tmp/...`、其他容器根路径返回包含可用工具建议的错误，不执行 native tool。

- [x] **Step 4: Run focused workspace tests**

Run:

```bash
pytest tests/ai/runtime/test_agentscope_workspace.py tests/ai/runtime/test_agentscope_workspace_toolkit.py -q
```

Expected: PASS。

### Task 3: 修正目录清单的工具路径契约

**Files:**
- Modify: `app/services/ai/tools/resource_catalog_tools.py:245-420`
- Test: `tests/ai/test_directory_catalog_tool.py`

- [x] **Step 1: Write the failing tests**

在 Docker 目录清单测试中要求每个目录返回明确的 `bash_path`、`file_tool_path` 和 `path_namespace`，并验证公共 docs 的文件工具路径不是 `/workspace/public/docs`。

```python
assert subdirs["docs"]["paths"]["bash"] == "/workspace/docs"
assert subdirs["docs"]["paths"]["file_tools"] == "docs"
assert public_dirs["docs"]["paths"]["bash"] == "/workspace/public/docs"
assert public_dirs["docs"]["paths"]["file_tools"] == data["public_directories"]["directories"][0]["backend_service_path"]
assert public_dirs["docs"]["path_namespace"]["bash"] == "docker_sandbox"
assert public_dirs["docs"]["path_namespace"]["file_tools"] == "backend_service"
```

- [x] **Step 2: Run the catalog tests to verify they fail**

Run:

```bash
pytest tests/ai/test_directory_catalog_tool.py -q
```

Expected: FAIL because the current response has separate path fields and ambiguous `access_via` semantics.

- [x] **Step 3: Implement the explicit path fields**

保持已有字段兼容，同时增加：

```json
{
  "paths": {
    "bash": "/workspace/docs",
    "file_tools": "docs"
  },
  "path_namespace": {
    "bash": "docker_sandbox",
    "file_tools": "backend_service"
  }
}
```

用户目录的 `file_tools` 使用用户工作区相对路径；公共 docs/branding 使用 `backend_service_path`；容器专属资源的 `file_tools` 为 `null` 并从 `access_via` 移除宿主工具，或明确返回其后端等价路径。更新 `usage_guidelines`，明确 Bash 路径不能直接作为文件工具路径，但共享用户目录可由适配器转换。

- [x] **Step 4: Run catalog regression tests**

Run:

```bash
pytest tests/ai/test_directory_catalog_tool.py -q
```

Expected: PASS，且保留旧字段的现有断言继续通过。

### Task 4: 修正提示词和 Bash 结果中的路径说明

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py:1991-2032`
- Modify: `app/services/ai/agent_prompts.py:770-805`
- Test: `tests/ai/runtime/test_agentscope_workspace.py`
- Test: `tests/ai/test_directory_catalog_tool.py`

- [x] **Step 1: Write the failing tests**

验证 Docker 模式的系统提示词同时包含沙箱路径和文件工具路径规则，并明确禁止直接把容器专属路径交给 `Read`。

```python
assert "Bash 使用沙箱路径" in prompt
assert "Read/Write/Edit/Glob/Grep 使用文件工具路径" in prompt
assert "不要将 /tmp 等容器专属路径交给 Read" in prompt
```

- [x] **Step 2: Run the prompt contract tests to verify they fail**

Run:

```bash
pytest tests/ai/runtime/test_agentscope_workspace.py tests/ai/test_directory_catalog_tool.py -q -k "prompt or catalog"
```

Expected: FAIL because the current prompt states that Bash and file tools share a logical root without declaring separate tool namespaces.

- [x] **Step 3: Implement the prompt contract**

扩展 `append_session_workspace_sandbox_to_system_prompt()`，在 Docker 模式传入逻辑路径信息，并将提示词改为：Bash 使用 `bash_path`，文件工具使用 `file_tool_path`；共享用户挂载可以转换，容器临时路径只能由 Bash 访问。对本地模式保持现有相对路径行为。

若 Bash 结果包装层能够可靠识别共享挂载路径，则附加 `sandbox_path` 与 `file_tool_path`；不能可靠识别的普通文本不强行重写，只依赖文件工具适配器的统一映射和错误提示。

- [x] **Step 4: Run prompt and workspace tests**

Run:

```bash
pytest tests/ai/runtime/test_agentscope_workspace.py tests/ai/test_directory_catalog_tool.py -q
```

Expected: PASS。

### Task 5: 完成整体回归与人工验收说明

**Files:**
- Test: `tests/ai/runtime/test_agentscope_workspace.py`
- Test: `tests/ai/test_directory_catalog_tool.py`
- Modify: `tests/CHECKLIST.md` only if the repository workflow requires recording this change

- [x] **Step 1: Run focused backend regression**

```bash
pytest --confcutdir=tests/ai tests/ai/runtime/test_agentscope_workspace.py tests/ai/runtime/test_agentscope_workspace_toolkit.py tests/ai/test_directory_catalog_tool.py -q
```

Expected: PASS；若出现 Redis、Docker daemon 或其他基础设施错误，单独记录为环境阻塞，不修改测试规避。

- [x] **Step 2: Run static checks on changed Python files**

```bash
python3 -m compileall -q app/services/ai/runtime/agentscope/workspace.py app/services/ai/tools/resource_catalog_tools.py
git diff --check -- app/services/ai/runtime/agentscope/workspace.py app/services/ai/tools/resource_catalog_tools.py app/services/ai/agent_prompts.py tests/ai/runtime/test_agentscope_workspace.py tests/ai/test_directory_catalog_tool.py
```

Expected: 命令成功，无语法错误和 diff 空白错误。

- [x] **Step 3: Prepare manual acceptance cases without starting services**

由用户在真实 Docker 环境验证：

1. Bash 在 `/workspace/docs/a.md` 创建文件，Read 使用映射后路径读取成功。
2. Bash 读取 `/workspace/public/docs/FAQ.md` 成功，Read 使用后端 docs 路径读取成功。
3. Read 误传 `/tmp/a.md` 时明确拒绝，不访问后端宿主路径。
4. Read 误传其他用户路径或 `../` 越界路径时仍被现有权限层拒绝。
5. local 模式下现有相对路径和文件工具行为不变。

不主动执行 `./dev.sh`、部署脚本或生产数据库操作。
