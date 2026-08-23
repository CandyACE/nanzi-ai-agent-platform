# Docker 公共目录清单修正实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 Docker 沙箱目录清单对公共 docs 路径的错误声明，避免模型把平台宿主路径误当成沙箱内路径。

**Architecture:** 保持当前 Docker 沙箱只挂载当前用户工作区的设计，不增加公共目录 bind mount。目录清单在 Docker 模式下将公共 docs 的 `container_sandbox_path` 设为 `null`，并通过 `access_via` 明确它只能由宿主文件工具只读访问；公共 skills 保留 `/workspace/skills`，但标注为按用户工作区预置的副本。

**Tech Stack:** Python 3.11、FastAPI 工具返回 JSON、pytest。

---

### Task 1: 为 Docker 公共目录路径契约增加失败测试

**Files:**
- Modify: `tests/ai/test_directory_catalog_tool.py:75-100`
- Test target: `list_accessible_directories` Docker 模式返回的 `public_directories`

- [x] **Step 1: 修改测试断言，表达正确契约**

在现有 `test_list_accessible_directories_docker_sandbox_mode` 中读取公共目录映射，并增加以下断言：

```python
public_dirs = {
    item["directory_name"]: item
    for item in data["public_directories"]["directories"]
}
assert public_dirs["docs"]["container_sandbox_path"] is None
assert public_dirs["docs"]["access_via"] == ["Read", "Glob", "Grep"]
assert public_dirs["skills"]["container_sandbox_path"] == "/workspace/skills"
assert public_dirs["skills"]["path_semantics"] == "per_user_seeded_copy"
```

- [x] **Step 2: 运行该单测确认当前实现失败**

Run:

```bash
venv/bin/python -m pytest tests/ai/test_directory_catalog_tool.py::test_list_accessible_directories_docker_sandbox_mode -q
```

Expected: FAIL，当前公共 docs 的 `container_sandbox_path` 仍是 `/app/data/docs`，且没有新增契约字段。

### Task 2: 修正目录清单 Docker 路径声明

**Files:**
- Modify: `app/services/ai/tools/resource_catalog_tools.py:312-330`

- [x] **Step 1: 将公共 docs 标记为宿主文件工具访问**

公共 docs 条目调整为：

```python
{
    "directory_name": "docs",
    "container_sandbox_path": None if is_docker_sandbox else global_docs_service_path,
    "backend_service_path": global_docs_service_path,
    "host_physical_path": _to_host_path(global_docs_service_path),
    "access_via": ["Read", "Glob", "Grep"],
    "permission": "read_only",
    "category": "platform_global_docs",
    "description": (
        "平台全局公共文档与模板库（data/docs）。"
        "Docker 沙箱 Bash 不直接挂载此目录，请通过宿主文件工具只读查阅。"
    ),
    "recommended_for": ["查阅公共产品手册", "参考公共标准模板与制度文档"],
}
```

- [x] **Step 2: 明确公共 skills 是用户工作区内的预置副本**

公共 skills 条目保留 Docker 模式的 `/workspace/skills`，增加：

```python
"path_semantics": "per_user_seeded_copy" if is_docker_sandbox else "platform_directory",
```

并在描述中说明 Docker 模式访问的是当前用户沙箱内的预置副本，不是直接挂载 `/app/data/skills`。

- [x] **Step 3: 运行失败测试确认转为通过**

Run:

```bash
venv/bin/python -m pytest tests/ai/test_directory_catalog_tool.py::test_list_accessible_directories_docker_sandbox_mode -q
```

Expected: PASS。

### Task 3: 回归验证

**Files:**
- No additional files

- [x] **Step 1: 运行目录清单相关测试**

Run:

```bash
venv/bin/python -m pytest tests/ai/test_directory_catalog_tool.py -q
```

Expected: all tests pass。

- [x] **Step 2: 检查改动格式和范围**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors；只包含目录清单工具、对应测试和本实施计划的改动，不启动服务、不提交代码。
