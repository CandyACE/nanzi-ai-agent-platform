# 智能体版本 Diff 对比 Implementation Plan

> **For agentic workers:** 按本计划逐项执行；每一步完成后检查结果再进入下一步。实现过程中不启动服务，也不自动提交。

**Goal:** 在智能体“配置与发布”抽屉中，让归档或草稿版本能够与当前线上版本进行只读 Diff 对比。

**Architecture:** 使用一个纯 TypeScript 差异计算工具归一化版本配置，并由新的 AgentVersionDiffModal.vue 负责渲染字段级只读对比。AgentVersionsDrawer.vue 从已有版本列表中识别 status 为 PUBLISHED 的版本，向非线上版本提供入口；不新增 API、数据库迁移或网络请求。

**Tech Stack:** Vue 3、TypeScript、Tailwind CSS、现有 Modal.vue、Node assert TypeScript 脚本测试、pytest 前端源码契约测试。

---

## 文件结构

- Create: frontend/src/utils/agentVersionDiff.ts — 版本运行配置归一化、集合匹配和字段级 Diff 结果。
- Create: frontend/src/components/agent/AgentVersionDiffModal.vue — 居中只读 Diff 弹窗。
- Create: frontend/scripts/agentVersionDiff.test.ts — 差异计算行为测试，使用 Node 内置 assert。
- Create: tests/frontend/test_agent_version_diff_contract.py — Vue 入口、线上版本基准和只读弹窗源码契约。
- Modify: frontend/src/api/agent.ts — 将工具配置声明为字符串或 ToolConfigItem 联合类型。
- Modify: frontend/src/components/agent/AgentVersionsDrawer.vue — 添加 Diff 入口、线上版本计算和弹窗挂载；保留现有克隆相关改动。

## Task 1：为差异计算写失败测试

**Files:**
- Create: frontend/scripts/agentVersionDiff.test.ts
- Read: frontend/src/api/agent.ts

- [ ] **Step 1：Write the failing behavior test**

创建测试数据和断言，锁定标量修改、工具按名称匹配、工具新增/移除/修改、Skills 顺序无关、欢迎语卡片字段定位和完整相同配置：

```ts
import assert from "node:assert/strict";
import type { AIAgentVersion } from "../src/api/agent.ts";
import { buildAgentVersionDiff } from "../src/utils/agentVersionDiff.ts";

const makeVersion = (overrides: Partial<AIAgentVersion> = {}): AIAgentVersion => ({
  id: "v1",
  agent_id: "agent-1",
  version_number: 1,
  model_name: "model-a",
  temperature: 0.2,
  synthesis_model_name: "synth-a",
  synthesis_temperature: 0.7,
  system_prompt: "回答问题",
  tools: ["search", { name: "query", enabled: true, temperature: 0.1 }] as any,
  skills_custom: true,
  skills: ["skill-b", "skill-a"],
  welcome_config: {
    enabled: true,
    mode: "manual",
    generation_requirement: "保持简洁",
    cards: [{ icon: "chat", title: "问候", subtitle: "你好", prompt: "打个招呼" }],
  },
  status: "ARCHIVED",
  comment: "历史版本",
  created_at: "2026-08-23T12:00:00Z",
  ...overrides,
});

const same = buildAgentVersionDiff(
  makeVersion(),
  makeVersion({ id: "v2", version_number: 2, status: "PUBLISHED" }),
);
assert.equal(same.identical, true);
assert.equal(same.changedCount, 0);

const changed = buildAgentVersionDiff(
  makeVersion({
    temperature: 0.3,
    tools: [
      { name: "query", enabled: false, temperature: 0.1 },
      "history",
    ] as any,
    system_prompt: "回答问题并引用依据",
    skills: ["skill-a", "skill-b"],
    welcome_config: {
      enabled: true,
      mode: "manual",
      generation_requirement: "保持简洁",
      cards: [{ icon: "chat", title: "问候用户", subtitle: "你好", prompt: "打个招呼" }],
    },
  }),
  makeVersion({ status: "PUBLISHED", version_number: 3 }),
);
assert.equal(changed.identical, false);
assert.ok(changed.groups.find((group) => group.id === "model")?.items.some((item) => item.key === "temperature" && item.changed));
assert.ok(changed.groups.find((group) => group.id === "prompt")?.items.some((item) => item.changed));
assert.ok(changed.groups.find((group) => group.id === "tools")?.items.some((item) => item.change === "added" && item.label.includes("search")));
assert.ok(changed.groups.find((group) => group.id === "tools")?.items.some((item) => item.change === "removed" && item.label.includes("history")));
assert.ok(changed.groups.find((group) => group.id === "tools")?.items.some((item) => item.change === "modified" && item.label.includes("query")));
assert.equal(changed.groups.find((group) => group.id === "skills")?.changedCount, 0);
assert.ok(changed.groups.find((group) => group.id === "welcome")?.items.some((item) => item.key.includes("cards.0.title")));

console.log("agentVersionDiff.test.ts passed");
```

- [ ] **Step 2：Run the test and verify the failure is about the missing helper**

Run:

```bash
cd frontend && node --experimental-strip-types scripts/agentVersionDiff.test.ts
```

Expected: FAIL because frontend/src/utils/agentVersionDiff.ts does not exist. Do not add production code before observing this failure.

## Task 2：实现纯 Diff helper

**Files:**
- Create: frontend/src/utils/agentVersionDiff.ts
- Modify: frontend/src/api/agent.ts
- Test: frontend/scripts/agentVersionDiff.test.ts

- [ ] **Step 1：Implement the public result types and builder**

实现测试使用的 buildAgentVersionDiff(source, published)，返回固定结构：

```ts
export type VersionDiffChange = "added" | "removed" | "modified" | "unchanged";
export interface VersionDiffItem {
  key: string;
  label: string;
  change: VersionDiffChange;
  changed: boolean;
  sourceValue: unknown;
  publishedValue: unknown;
  sourceText: string;
  publishedText: string;
}
export interface VersionDiffGroup {
  id: "model" | "tools" | "skills" | "prompt" | "welcome";
  label: string;
  items: VersionDiffItem[];
  changedCount: number;
}
export interface AgentVersionDiff {
  groups: VersionDiffGroup[];
  changedCount: number;
  identical: boolean;
}
```

按以下规则实现：

1. model 组比较 model_name、temperature、synthesis_model_name、synthesis_temperature。
2. tools 将字符串和对象统一成带名称的条目，按工具名匹配和排序；仅线上存在为 added，仅历史存在为 removed，同名配置变化为 modified。
3. skills 去重并排序后比较，生成 skills_custom 和 skills 两个条目；只发生顺序变化时为 unchanged。
4. prompt 组比较 system_prompt。
5. welcome 组展平比较 enabled、mode、generation_requirement，以及每张卡片的 title、subtitle、prompt；缺失配置按空对象或空数组处理。
6. 对象递归按 key 排序；空字符串、null、undefined 展示为“未配置”；异常值转为 String(value)，不阻断其他字段。
7. 每组和整体计算 changedCount，identical 只由整体变化数是否为 0 决定。
8. 导出 findPublishedAgentVersion 和 getAgentVersionDiffPair，分别复用线上版本选择与“非线上源版本 → 当前线上版本”的入口配对规则，供抽屉和行为测试使用。

- [ ] **Step 2：Run the behavior test and verify it passes**

Run:

```bash
cd frontend && node --experimental-strip-types scripts/agentVersionDiff.test.ts
```

Expected: agentVersionDiff.test.ts passed。

## Task 3：为 UI 接线写失败契约测试

**Files:**
- Create: tests/frontend/test_agent_version_diff_contract.py
- Read: frontend/src/components/agent/AgentVersionsDrawer.vue
- Read: frontend/src/components/agent/AgentVersionDiffModal.vue

- [ ] **Step 1：Write the failing source contract**

```python
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def test_version_drawer_compares_non_published_versions_with_current_online_version():
    source = (ROOT / "frontend/src/components/agent/AgentVersionsDrawer.vue").read_text(encoding="utf-8")

    assert "const publishedVersion = computed" in source
    assert "status === 'PUBLISHED'" in source
    assert "const openDiff = (version: AIAgentVersion) =>" in source
    assert '@click="openDiff(v)"' in source
    assert "v.status !== 'PUBLISHED'" in source
    assert ">Diff<" in source
    assert ':source-version="diffVersion"' in source
    assert ':published-version="publishedVersion"' in source


def test_version_diff_modal_is_read_only_and_shows_runtime_config_groups():
    source = (ROOT / "frontend/src/components/agent/AgentVersionDiffModal.vue").read_text(encoding="utf-8")

    for label in ("版本 Diff", "模型策略", "工具", "Skills", "系统提示词", "欢迎语配置"):
        assert label in source
    assert "只读" in source
    assert "buildAgentVersionDiff" in source
    assert "v-model" not in source
    assert '@click="save"' not in source
```

- [ ] **Step 2：Run the contract and verify the failure is about missing Diff wiring**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_agent_version_diff_contract.py --confcutdir=tests/frontend -q
```

Expected: FAIL because the new modal and drawer Diff symbols do not exist yet.

## Task 4：实现只读弹窗并接入版本抽屉

**Files:**
- Create: frontend/src/components/agent/AgentVersionDiffModal.vue
- Modify: frontend/src/components/agent/AgentVersionsDrawer.vue
- Test: tests/frontend/test_agent_version_diff_contract.py

- [ ] **Step 1：Create the modal component**

使用现有 Modal.vue，接收 show、sourceVersion、publishedVersion 三个 props，通过 computed 调用 buildAgentVersionDiff。模板必须包含版本关系、变化统计、五个分组和每个条目的两列 pre：

```vue
<Modal
  v-if="show && sourceVersion && publishedVersion && diff"
  title="版本 Diff"
  size="max-w-5xl"
  :show="show"
  :z-index="70"
  @close="emit('close')"
>
  <div class="rounded-xl border border-indigo-100 bg-indigo-50/70 px-4 py-3">
    <div>V{{ sourceVersion.version_number }} → 当前线上 V{{ publishedVersion.version_number }}</div>
    <div>{{ diff.identical ? '配置一致' : diff.changedCount + ' 项变化' }}</div>
    <p>只读对比 · 历史/草稿版本 → 当前线上版本</p>
  </div>
  <div v-for="group in diff.groups" :key="group.id">
    <h3>{{ group.label }}</h3>
    <span>{{ group.changedCount ? group.changedCount + ' 项变化' : '无变化' }}</span>
    <div v-for="entry in group.items" :key="entry.key">
      <span>{{ entry.label }}</span>
      <span>{{ entry.change }}</span>
      <pre>{{ entry.sourceText }}</pre>
      <pre>{{ entry.publishedText }}</pre>
    </div>
  </div>
</Modal>
```

使用两列只读 pre 区域展示历史/草稿版本和当前线上版本，长文本用 max-height 与 overflow-auto，新增、移除、修改、无变化使用不同颜色徽标。不要使用 v-model、输入控件或保存按钮。

- [ ] **Step 2：Add drawer state and current-online selector**

在 AgentVersionsDrawer.vue 的 script setup 中加入：

```ts
import AgentVersionDiffModal from "./AgentVersionDiffModal.vue";
import {
  findPublishedAgentVersion,
  getAgentVersionDiffPair,
} from "../../utils/agentVersionDiff";

const diffVersion = ref<AIAgentVersion | null>(null);
const publishedVersion = computed(() => findPublishedAgentVersion(versions.value));

const openDiff = (version: AIAgentVersion) => {
  const pair = getAgentVersionDiffPair(versions.value, version.id);
  if (!pair) return;
  diffVersion.value = pair.sourceVersion;
};

const closeDiff = () => {
  diffVersion.value = null;
};
```

- [ ] **Step 3：Add Diff buttons without changing existing actions**

在 active draft 和 archived 行的查看/编辑操作旁加入：

```vue
<button
  v-if="publishedVersion && v.status !== 'PUBLISHED'"
  type="button"
  @click="openDiff(v)"
  class="text-xs font-medium text-blue-600 hover:text-blue-700"
  title="与当前线上版本对比"
>
  Diff
</button>
```

不要给当前线上版本增加 Diff；不要给 Diff 复用 agent.is_editable !== false 条件；保留现有克隆、删除、发布和查看行为。

- [ ] **Step 4：Mount the modal and run the contract**

在抽屉模板删除确认弹窗之后加入：

```vue
<AgentVersionDiffModal
  :show="!!diffVersion"
  :source-version="diffVersion"
  :published-version="publishedVersion"
  @close="closeDiff"
/>
```

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_agent_version_diff_contract.py --confcutdir=tests/frontend -q
```

Expected: 3 passed。

## Task 5：增加变化过滤开关

**Files:**
- Modify: frontend/src/components/agent/AgentVersionDiffModal.vue — 增加顶部“仅显示变化”开关、变化条目过滤和一致状态。
- Modify: tests/frontend/test_agent_version_diff_contract.py — 覆盖开关状态与过滤视图契约。

- [ ] **Step 1：Write the failing display contract**

在 `test_version_diff_modal_can_show_only_changed_items` 中锁定 `showOnlyChanges`、`visibleGroups`、`items.filter((item) => item.changed)`、开关文案和无差异状态；先运行该测试，确认因弹窗尚未提供这些符号而失败。

- [ ] **Step 2：Implement the display-only filter**

在弹窗内用 `ref(false)` 保存开关状态，默认显示完整分组；开启后将每组条目过滤为 `item.changed`，移除空分组，并在没有任何变化时显示“当前版本与线上版本一致”。开关关闭或弹窗重新打开时恢复完整对比视图，不改变底层 `buildAgentVersionDiff` 结果。

- [ ] **Step 3：Run the focused regression**

运行：

```bash
venv/bin/python -m pytest tests/frontend/test_agent_version_diff_contract.py tests/frontend/test_agent_version_clone_contract.py --confcutdir=tests/frontend -q
```

Expected: Diff、开关和既有克隆契约全部通过。

## Task 6：完成聚焦回归和静态验证

**Files:**
- Verify: frontend/src/utils/agentVersionDiff.ts
- Verify: frontend/src/components/agent/AgentVersionDiffModal.vue
- Verify: frontend/src/components/agent/AgentVersionsDrawer.vue
- Verify: frontend/scripts/agentVersionDiff.test.ts
- Verify: tests/frontend/test_agent_version_diff_contract.py

- [ ] **Step 1：Run pure helper behavior test**

Run:

```bash
cd frontend && node --experimental-strip-types scripts/agentVersionDiff.test.ts
```

Expected: agentVersionDiff.test.ts passed。

- [ ] **Step 2：Run focused frontend contracts, including the pre-existing clone contract**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_agent_version_diff_contract.py tests/frontend/test_agent_version_clone_contract.py --confcutdir=tests/frontend -q
```

Expected: Diff、开关和 clone contracts pass together; unrelated failures must be classified before additional changes.

- [ ] **Step 3：Run frontend type checking**

Run:

```bash
cd frontend && ./node_modules/.bin/vue-tsc --noEmit
```

Expected: type checking succeeds. Do not run npm run dev, ./dev.sh, deployment scripts, or database operations.

- [ ] **Step 4：Run whitespace and final worktree checks**

Run:

```bash
git diff --check -- frontend/src/components/agent/AgentVersionsDrawer.vue frontend/src/components/agent/AgentVersionDiffModal.vue frontend/src/utils/agentVersionDiff.ts frontend/scripts/agentVersionDiff.test.ts tests/frontend/test_agent_version_diff_contract.py
git status --short
```

Expected: no whitespace errors; existing dev.sh, tests/test_dev_sh_python_bootstrap.py, archived-version-clone test/docs and clone changes remain untouched. Report all uncommitted files and distinguish them from this Diff change.

- [ ] **Step 5：Report manual acceptance boundaries**

用户在控制台启动服务后确认：

1. V23 为 PUBLISHED 时，V22 归档和草稿行显示 Diff，V23 自身不显示。
2. 点击 V22 的 Diff 打开居中只读弹窗，显示“V22 → 当前线上 V23”、五个配置分组和字段变化。
3. 无编辑权限用户可以查看 Diff，但不会因此获得编辑、克隆、发布或删除权限。
4. 没有线上版本时不显示 Diff，其他版本操作仍可用。
5. 关闭 Diff 后版本抽屉和源版本状态不变。
