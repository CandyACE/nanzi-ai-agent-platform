# 归档智能体版本复制新建 Implementation Plan

> **For agentic workers:** 按本计划逐项执行；每一步完成后检查结果再进入下一步。

**Goal:** 让有编辑权限的用户可以从归档智能体版本复制配置并新建草稿，同时保持归档版本只读。

**Architecture:** 只在 `AgentVersionsDrawer.vue` 的归档版本操作区增加 `create-version` 事件入口，复用 `AgentManagement.vue` 已有的克隆初始化逻辑。父层会清空源版本身份字段并将副本作为新草稿提交，后端现有创建接口负责分配版本号，因此不增加 API 或数据库变更。

**Tech Stack:** Vue 3、TypeScript、Vue SFC、pytest 前端源码契约测试、现有 `agentApi` 与 Agent 版本编辑器。

---

### Task 1: 增加归档版本克隆的失败契约测试

**Files:**
- Create: `tests/frontend/test_agent_version_clone_contract.py`
- Read: `frontend/src/components/agent/AgentVersionsDrawer.vue`
- Read: `frontend/src/views/AgentManagement.vue`

- [ ] **Step 1: Write the failing test**

创建源码契约测试，限定检查范围为 `<!-- Archived List -->` 之后的归档版本区域，确保该区域同时保留查看、按编辑权限显示克隆、并向父层传入当前归档版本：

```python
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def test_archived_versions_offer_clone_without_making_archive_editable():
    source = (ROOT / "frontend/src/components/agent/AgentVersionsDrawer.vue").read_text(encoding="utf-8")
    archived = source[source.index("<!-- Archived List -->"):]

    assert '@click="emit(\'edit-version\', v)"' in archived
    assert '@click="emit(\'create-version\', v)"' in archived

    clone_action = archived[archived.index('@click="emit(\'create-version\', v)"') - 300:]
    assert 'v-if="agent?.is_editable !== false"' in clone_action
    assert 'title="基于此版本新建"' in clone_action


def test_archived_clone_reuses_parent_new_draft_flow():
    management = (ROOT / "frontend/src/views/AgentManagement.vue").read_text(encoding="utf-8")

    assert "const handleDrawerCreateVersion = (baseVersion?: AIAgentVersion) =>" in management
    assert "openVersionModal(baseVersion, true);" in management
    assert "id: undefined, // Clear ID to create new" in management
    assert "version_number: undefined, // Let backend assign next" in management
    assert 'status: "DRAFT", // Reset status' in management
```

- [ ] **Step 2: Run the focused test to verify it fails for the missing UI entry**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_agent_version_clone_contract.py --confcutdir=tests/frontend -q
```

Expected: the second assertion in `test_archived_versions_offer_clone_without_making_archive_editable` fails because the archived list currently has no `emit('create-version', v)` action. The parent-flow test may pass because that flow already exists; the overall test command must still be red due to the missing archived action.

### Task 2: 在归档版本操作区接入现有克隆流程

**Files:**
- Modify: `frontend/src/components/agent/AgentVersionsDrawer.vue:242-260`

- [ ] **Step 1: Add the minimal archived clone button**

在归档版本现有“查看”按钮之后、删除按钮之前加入以下按钮，沿用活跃版本的事件、权限条件和按钮文案：

```vue
<button
    v-if="agent?.is_editable !== false"
    @click="emit('create-version', v)"
    class="text-xs text-blue-600 hover:text-blue-700 font-medium"
    title="基于此版本新建"
>
    克隆
</button>
```

不要给归档版本增加编辑或发布入口，也不要修改 `edit-version` 和删除按钮的行为。

- [ ] **Step 2: Run the focused test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_agent_version_clone_contract.py --confcutdir=tests/frontend -q
```

Expected: `2 passed`。

### Task 3: 完成回归与静态验证

**Files:**
- Verify: `frontend/src/components/agent/AgentVersionsDrawer.vue`
- Verify: `frontend/src/views/AgentManagement.vue`
- Verify: `tests/frontend/test_agent_version_clone_contract.py`

- [ ] **Step 1: Run all frontend contract tests**

Run:

```bash
venv/bin/python -m pytest tests/frontend --confcutdir=tests/frontend -q
```

Expected: 测试集合完成；若出现与本变更无关的收集或基线失败，记录具体失败文件和原因，不将其归因于本次克隆入口。

- [ ] **Step 2: Run the frontend type check**

Run:

```bash
cd frontend && ./node_modules/.bin/vue-tsc --noEmit
```

Expected: `vue-tsc --noEmit` 成功。

- [ ] **Step 3: Inspect the final diff and whitespace**

Run:

```bash
git diff --check -- frontend/src/components/agent/AgentVersionsDrawer.vue tests/frontend/test_agent_version_clone_contract.py
git diff -- frontend/src/components/agent/AgentVersionsDrawer.vue tests/frontend/test_agent_version_clone_contract.py
sed -n '1,220p' tests/frontend/test_agent_version_clone_contract.py
git status --short
```

Expected: 已跟踪文件差异只包含归档克隆按钮；源码契约测试内容与计划一致；工作区同时显示本次新增文档/测试以及已有的 `dev.sh` 和 `tests/test_dev_sh_python_bootstrap.py` 未相关改动，不覆盖这些已有改动，也不自动提交。

- [ ] **Step 4: Report manual acceptance boundary**

在交付说明中明确以下人工验收信号：

1. 有编辑权限时，归档历史行出现“查看 / 克隆 / 删除”；无编辑权限时不出现“克隆”。
2. 点击“克隆”打开新建草稿编辑器，版本状态为草稿，保存后版本号为新号。
3. 原归档版本仍可查看，查看页面控件不可编辑，且保存不会修改原版本。
