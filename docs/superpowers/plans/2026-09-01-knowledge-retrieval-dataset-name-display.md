# 检索测试知识库名称展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在检索测试页以知识库名称展示多选结果，同时保持 Dataset ID 请求参数不变。

**Architecture:** 选择器继续负责加载和多选 RAGFlow Dataset；父页面维护 ID 数组，并通过选择器新增的名称结果建立 ID 到名称的映射。检索条件区使用名称标签和数量摘要渲染，无法解析名称时回退显示 ID。

**Tech Stack:** Vue 3、TypeScript、现有 `RagFlowResourceSelector`、pytest 前端契约测试。

---

### Task 1: 为选择结果增加名称映射并覆盖多选展示契约

**Files:**
- Modify: `frontend/src/components/RagFlowResourceSelector.vue`
- Modify: `frontend/src/views/KnowledgeRetrievalTest.vue`
- Test: `tests/frontend/test_knowledge_retrieval_dataset_display_contract.py`

- [ ] **Step 1: Write the failing contract tests**

```python
def test_retrieval_test_renders_dataset_names_and_keeps_ids_for_payload():
    source = retrieval_test_source()
    assert "datasetNameById" in source
    assert "datasetIds" in source
    assert "还有" in source
    assert "dataset_ids: datasetIds.value" in source


def test_selector_emits_selected_dataset_details_for_name_mapping():
    source = selector_source()
    assert "selectedDetails" in source
    assert "display_name" in source
    assert "@select-details" in retrieval_test_source()
```

测试通过 `Path` 读取两个 Vue 源文件，不连接 RAGFlow。

- [ ] **Step 2: Run the contract tests and confirm they fail**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_knowledge_retrieval_dataset_display_contract.py -q`

Expected: FAIL because the page currently renders `datasetIdsText` and the selector only emits IDs。

- [ ] **Step 3: Add the minimal selection-details event**

选择器加载 Dataset 后，根据 `selectedIds` 计算当前选中项，新增 `select-details` 事件并保留原有 `select` 事件；父页面接收 `Array<{ id: string; name: string }>`，以 `datasetNameById` 保存名称，调用接口仍使用 `datasetIds.value`。

- [ ] **Step 4: Implement the compact name-label display**

在 `KnowledgeRetrievalTest.vue` 中将只读 ID 输入替换为名称标签：最多直接显示 3 个名称，超过 3 个显示前 2 个名称和“还有 N 个”；标签区域限制高度并滚动；名称不存在时显示 Dataset ID。选择器弹窗继续接收 `:initial-selected="datasetIds"`。

- [ ] **Step 5: Run the contract tests and frontend type check**

Run:

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_knowledge_retrieval_dataset_display_contract.py -q
```

Then from `frontend` run: `./node_modules/.bin/vue-tsc --noEmit`

Expected: contract tests PASS and TypeScript exits 0。

### Task 2: 回归检查并保留未提交修改

**Files:**
- Review: `frontend/src/components/RagFlowResourceSelector.vue`
- Review: `frontend/src/views/KnowledgeRetrievalTest.vue`
- Review: `tests/frontend/test_knowledge_retrieval_dataset_display_contract.py`
- Review: `docs/superpowers/specs/2026-09-01-knowledge-retrieval-dataset-name-display-design.md`

- [ ] **Step 1: Run diff and targeted regression checks**

Run: `git diff --check`

Expected: no output。

- [ ] **Step 2: Verify request and fallback boundaries**

确认检索请求的 `dataset_ids` 仍是 `datasetIds.value`；确认名称仅用于展示；确认多选、取消选择、失联 Dataset 和长名称均有可读结果。

- [ ] **Step 3: Report the uncommitted worktree state**

不执行 `git add`、`git commit` 或 push；向用户报告修改文件和测试结果，等待用户明确要求后再提交。
