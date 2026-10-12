# 移动端 AI 消息操作栏与操作抽屉 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让移动端（<640px）AI 消息的操作入口可见、不横向滚动、交互统一——新增带计数徽标的「▤ 数据」入口与一个四组内容的底部操作抽屉，桌面端零改动。

**Architecture:** 新增一个纯壳组件 `MobileActionSheet.vue`（遮罩 + 贴底容器 + 安全区 + 滚动锁 + Esc/点遮罩关闭）和一个内容组件 `MobileMessageActionsSheet.vue`（数据/文件、继续分析、本次调用、沉淀 四组）。`EmbedChat` 只在 `sm:` 移动端分支新增两个按钮并挂载抽屉，桌面侧原有元素用 `hidden sm:flex` 包裹后保持原样。两个既有抽屉（继续分析 / ChatBI 继续分析）改用同一个壳。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript + Tailwind CSS 3；测试用 pytest 契约测试（源码结构断言）+ `vue/compiler-sfc` + esbuild + `@vue/server-renderer` 真渲染探针；`vue-tsc --noEmit` 做类型检查。

**Spec:** `docs/superpowers/specs/2026-10-12-mobile-message-actions-design.md`

---

## 开工前必读（本项目约定）

1. **不要执行 `git commit`**：计划里每个 Task 末尾的 Commit 步骤只给建议 message，由用户自己提交。
2. **不要执行 `./dev.sh`** 或任何部署 / 启动脚本。
3. 契约测试跑法（在**仓库根**）：
   ```bash
   .venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend -q
   ```
4. node 探针的 **cwd 必须是 `frontend`**（`vue/compiler-sfc`、`esbuild` 装在 `frontend/node_modules`）。
5. 前端类型检查（在 `frontend/`）：
   ```bash
   npx vue-tsc --noEmit
   ```
6. 行号基于改动前的 HEAD，改动过程中会漂移；**以代码片段为准，不要只信行号**。

## 关键符号表（已核对，改动前位置）

| 符号 | 位置 | 用途 |
| --- | --- | --- |
| `hasConversationDataFile` | `EmbedChat.vue:3942`（computed） | 会话级：本会话有数据 / 文件 |
| `hasConversationReusableResult` | `EmbedChat.vue:3933`（computed） | 会话级：有可复用结果 |
| `hasConversationArtifact` | `EmbedChat.vue:3938`（computed） | 会话级：有文件产物 |
| `conversationReusableResultCount` | `EmbedChat.vue:3931`（ref） | 会话级条数 |
| `conversationArtifactCount` | `EmbedChat.vue:3940`（computed） | 会话级个数 |
| `currentMessageReusableCount(msg)` | `EmbedChat.vue:2694` | 当前消息可复用条数（徽标用） |
| `artifactCount(traceId)` | `EmbedChat.vue:3929` | 该 trace 的产物数（徽标用） |
| `getMessageTokenAmount(msg)` | `EmbedChat.vue:2777` | 「用量 12.4K tok」文本 |
| `openReusableResults(resultId, traceId, status)` | `EmbedChat.vue:2917` | 打开可复用结果 |
| `openMessageArtifacts(traceId)` | `EmbedChat.vue:2925` | 打开文件产物 |
| `openEmbedTrace(traceId)` | `EmbedChat.vue:3176` | 打开执行链路 |
| `exportData(traceId, format)` | `EmbedChat.vue:8293` | 导出 Excel |
| `openModelCallStats(msg)` | `EmbedChat.vue:8379` | 打开调用详情 |
| `handleQuickQuestion(query, mode, body)` | `EmbedChat.vue:8732` | 通用继续分析 |
| `handleChatBIContinueSelect(query)` | `EmbedChat.vue:5544` | ChatBI 追问 |
| `handleChatBIResultAction(action, msg)` | `EmbedChat.vue:8570` | ChatBI 本地动作 |
| `handleSaveReportFromMessage(msg)` | `EmbedChat.vue:9078` | 添加固化报表 |
| `canSaveGoldenReportFromMessage(msg)` | 同文件 | 固化报表权限判定 |
| `checkRole(msg, role)` | `EmbedChat.vue:2704` | 角色判定 |
| `isGeneralAgentMessage(msg)` | `EmbedChat.vue:5401` | 通用智能体判定 |
| `visibleStreamBody(msg)` | `EmbedChat.vue:2729` | 是否有可见正文 |
| `isMobile` / `windowWidth` / `updateWidth` | `EmbedChat.vue:6970` / `:6969` / `:6971-6979` | 断点（<640px） |
| `MessageContinueAnalysis` 四个动作 | `MessageContinueAnalysis.vue:90-115` | 待抽成共享模块 |
| ChatBI 动作图标映射 | `ChatBIContinueAnalysis.vue:104-107` | 待抽成共享模块 |
| 消息循环 | `EmbedChat.vue:519-520`：`v-for="msg in displayMessages" :key="msg.id"` | 抽屉用 `msg.id` 定位当前消息 |

## 文件结构（先锁定职责）

| 文件 | 责任 |
| --- | --- |
| `frontend/src/components/chat/continueAnalysisActions.ts`（新） | 「继续分析」动作数据与两类图标映射的唯一来源 |
| `frontend/src/components/chat/MobileActionSheet.vue`（新） | 底部抽屉**壳**：只负责外观、关闭、滚动锁、可访问性，不含业务 |
| `frontend/src/components/chat/MobileMessageActionsSheet.vue`（新） | 抽屉**内容**：四组渲染、`focus` 高亮、事件上抛 |
| `frontend/src/views/EmbedChat.vue`（改） | 移动端两个入口按钮 + 抽屉挂载 + 状态；桌面侧不动 |
| `frontend/src/components/chat/MessageContinueAnalysis.vue`（改） | 移动端分支换用壳；桌面浮层不变 |
| `frontend/src/components/chatbi/ChatBIContinueAnalysis.vue`（改） | 同上 |
| `tests/frontend/test_mobile_actions_sheet_contract.py`（新） | 全部结构契约 |
| `tests/frontend/mobile_action_sheet_ssr.cjs`（新） | 壳的真渲染探针 |
| `tests/CHECKLIST.md`（改） | 追加一行记录 |

---

### Task 1: 「继续分析」动作与图标抽成唯一来源

**Files:**
- Create: `frontend/src/components/chat/continueAnalysisActions.ts`
- Modify: `frontend/src/components/chat/MessageContinueAnalysis.vue:77-115,137`
- Modify: `frontend/src/components/chatbi/ChatBIContinueAnalysis.vue:104-107`
- Test: `tests/frontend/test_mobile_actions_sheet_contract.py`（新建）

- [ ] **Step 1: 写失败的契约测试**

新建 `tests/frontend/test_mobile_actions_sheet_contract.py`：

```python
"""移动端 AI 消息操作栏与操作抽屉的展示契约。

移动端此前把「数据 / 文件」藏在「⋯ 更多」浮层里、看不到计数徽标，一行还要横向
滚动；本组契约把「移动端两个入口 + 一个四组抽屉 + 桌面侧不被误伤」钉在源码结构上。
"""

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_continue_actions_live_in_one_shared_module():
    source = _read("frontend/src/components/chat/continueAnalysisActions.ts")
    assert "export const CONTINUE_ANALYSIS_ACTIONS" in source
    assert "export const continueActionIcon" in source
    assert "export const chatbiActionIcon" in source
    for action_id in ("visual_report", "save_markdown", "save_word", "create_skill"):
        assert f'id: "{action_id}"' in source, f"{action_id} 必须留在共享模块里"


def test_both_continue_consumers_import_the_shared_module():
    continue_source = _read("frontend/src/components/chat/MessageContinueAnalysis.vue")
    chatbi_source = _read("frontend/src/components/chatbi/ChatBIContinueAnalysis.vue")
    assert "continueAnalysisActions" in continue_source
    assert "continueAnalysisActions" in chatbi_source
    # 文案与图标映射不得再各留一份
    assert "请基于当前这条 AI 回复中已经存在的文本" not in continue_source
    assert 'visual_report: "▥"' not in continue_source
    assert 'trend: "↗"' not in chatbi_source
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q`
Expected: FAIL —— `FileNotFoundError`（`continueAnalysisActions.ts` 还不存在）。

- [ ] **Step 3: 创建共享模块**

新建 `frontend/src/components/chat/continueAnalysisActions.ts`。四个 `query` 字符串请从 `frontend/src/components/chat/MessageContinueAnalysis.vue:90-115` 的 `actions` 数组里**原样整段搬移，一字不改**（含中文标点），只保留 `id` / `label` / `description` 的写法不变：

```ts
/**
 * 「继续分析」动作与图标的唯一来源。
 *
 * 文案很长（每个 query 都是一段完整指令），曾经只活在 MessageContinueAnalysis.vue 里；
 * 移动端操作抽屉要复用同一批动作，所以抽到这里，避免第二份副本漂移。
 */
export type ContinueAction = {
  id: string;
  label: string;
  description: string;
  query: string;
};

export const CONTINUE_ANALYSIS_ACTIONS: ContinueAction[] = [
  {
    id: "visual_report",
    label: "生成可视化分析报告",
    description: "基于当前回复中的数据生成图表和结构化结论",
    query: "<从 MessageContinueAnalysis.vue:90-115 原样搬移>",
  },
  {
    id: "save_markdown",
    label: "保存为 Markdown",
    description: "保存到工作区 docs 目录并返回实际路径",
    query: "<从 MessageContinueAnalysis.vue:90-115 原样搬移>",
  },
  {
    id: "save_word",
    label: "保存为 Word",
    description: "生成 .docx 文件并返回下载地址",
    query: "<从 MessageContinueAnalysis.vue:90-115 原样搬移>",
  },
  {
    id: "create_skill",
    label: "提炼生成 Skill",
    description: "按 create_skills 工具规范生成个人 Skill",
    query: "<从 MessageContinueAnalysis.vue:90-115 原样搬移>",
  },
];

const CONTINUE_ACTION_ICONS: Record<string, string> = {
  visual_report: "▥",
  save_markdown: "M",
  save_word: "W",
  create_skill: "✦",
};

/** 通用沉淀动作的图标（原先内联在 MessageContinueAnalysis.vue:137）。 */
export const continueActionIcon = (id: string): string => CONTINUE_ACTION_ICONS[id] ?? "→";

const CHATBI_ACTION_ICONS: Record<string, string> = {
  trend: "↗",
  ranking: "#",
  contribution: "%",
  anomaly: "!",
  visualize: "▥",
  summary: "≡",
  brief: "▤",
  monitor: "◉",
};

/** ChatBI 追问动作的图标（原先内联在 ChatBIContinueAnalysis.vue:104-107）。 */
export const chatbiActionIcon = (id: string): string => CHATBI_ACTION_ICONS[id] ?? "→";
```

> 注意：上面四个 `query` 字段的 `<...>` 是**占位说明**，不是要写进文件的内容——落笔时必须是真的文案。搬完用 Step 2 的测试兜底（它断言组件里不再有那段文案）。

- [ ] **Step 4: 让 `MessageContinueAnalysis.vue` 引用共享模块**

删除该文件中的 `type ContinueAction = {...}`（第 77-82 行）、整个 `actions` 数组（第 90-115 行）与内联的 `actionIcon`（第 137 行），并在 `<script setup>` 的 import 区加上：

```ts
import { CONTINUE_ANALYSIS_ACTIONS as actions, continueActionIcon as actionIcon } from "./continueAnalysisActions";
```

- [ ] **Step 5: 让 `ChatBIContinueAnalysis.vue` 引用共享图标**

删除第 104-107 行的内联 `actionIcon`，改为：

```ts
import { chatbiActionIcon as actionIcon } from "@/components/chat/continueAnalysisActions";
```

- [ ] **Step 6: 跑测试确认通过**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q`
Expected: 2 passed。

同时确认没有别的地方还在用旧内联导出：
Run: `cd frontend && npx vue-tsc --noEmit`
Expected: exit 0。

- [ ] **Step 7: Commit（由用户执行）**

```bash
git add frontend/src/components/chat/continueAnalysisActions.ts \
        frontend/src/components/chat/MessageContinueAnalysis.vue \
        frontend/src/components/chatbi/ChatBIContinueAnalysis.vue \
        tests/frontend/test_mobile_actions_sheet_contract.py
# 建议 message: refactor(chat): 继续分析动作与图标抽成共享模块
```

---

### Task 2: 底部抽屉壳 `MobileActionSheet`

**Files:**
- Create: `frontend/src/components/chat/MobileActionSheet.vue`
- Create: `tests/frontend/mobile_action_sheet_ssr.cjs`
- Test: `tests/frontend/test_mobile_actions_sheet_contract.py`（追加）

- [ ] **Step 1: 写真渲染探针（先让它失败）**

新建 `tests/frontend/mobile_action_sheet_ssr.cjs`：

```js
/**
 * 真渲染 MobileActionSheet.vue：验证抽屉只在 open 时出现，且带着壳应有的语义。
 *
 * 为什么用真编译而不是字符串断言：这是单文件组件，Node 不能直接 require。
 * 这里用 vue/compiler-sfc 编译真实源码、esbuild 剥 TS、@vue/server-renderer 真渲染，
 * 不复制任何模板逻辑。
 *
 * 为什么看 ctx.teleports：壳把内容 Teleport 到 body，SSR 下 teleport 内容不落在
 * renderToString 的返回值里，而在 SSR context 的 teleports 上。
 *
 * 事件绑定（点击遮罩关闭）SSR 渲染不出来，那部分由 pytest 的源码契约覆盖。
 *
 * 输出 JSON（断言交给 pytest）：{ closed: {...}, opened: {...} }
 * cwd 必须是 frontend。
 */
const fs = require("fs");
const path = require("path");

const fromFrontend = (name) => require(require.resolve(name, { paths: [process.cwd()] }));
const { parse, compileScript, compileTemplate } = fromFrontend("vue/compiler-sfc");
const Vue = fromFrontend("vue");
const { renderToString } = fromFrontend("@vue/server-renderer");
const esbuild = fromFrontend("esbuild");

const COMPONENT = path.resolve("src/components/chat/MobileActionSheet.vue");
const VUE_IMPORT = /import\s*\{([^}]*)\}\s*from\s*['"]vue['"];?/g;

function buildComponent(source) {
  const { descriptor, errors } = parse(source, { filename: COMPONENT });
  if (errors.length) throw new Error("parse: " + errors.map(String).join("; "));

  const script = compileScript(descriptor, { id: "mobile-action-sheet" });
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename: COMPONENT,
    id: "mobile-action-sheet",
    compilerOptions: { bindingMetadata: script.bindings },
  });
  if (tpl.errors.length) throw new Error("template: " + tpl.errors.map(String).join("; "));

  const toDestructure = (code) =>
    code
      .replace(VUE_IMPORT, (_match, names) => `const {${names.replace(/\s+as\s+/g, ": ")}} = Vue;`)
      .replace("export default", "const __sfc =")
      .replace("export function render", "function render");

  const tsCode = toDestructure(script.content) + "\n" + toDestructure(tpl.code);
  const jsCode = esbuild.transformSync(tsCode, { loader: "ts", format: "esm" }).code;
  return new Function("Vue", `${jsCode}\n__sfc.render = render;\nreturn __sfc;`)(Vue);
}

async function render(source, props) {
  const app = Vue.createSSRApp({
    render: () => Vue.h(buildComponent(source), props, { default: () => "抽屉内容占位" }),
  });
  const ctx = {};
  const html = await renderToString(app, ctx);
  const teleport = (ctx.teleports && ctx.teleports.body) || "";

  return {
    bodyHtml: html,
    teleportHtml: teleport,
    hasDialog: /role="dialog"/.test(teleport),
    hasAriaModal: /aria-modal="true"/.test(teleport),
    hasBackdrop: /fixed inset-0 z-\[260\]/.test(teleport),
    hasSafeArea: /safe-area-inset-bottom/.test(teleport),
    hasTitle: teleport.includes("更多操作"),
    hasSubtitle: teleport.includes("解释一行"),
    hasSlot: teleport.includes("抽屉内容占位"),
    hasCancel: teleport.includes("取消"),
  };
}

(async () => {
  const source = fs.readFileSync(COMPONENT, "utf8");
  const closed = await render(source, { open: false, title: "更多操作" });
  const opened = await render(source, { open: true, title: "更多操作", subtitle: "解释一行" });
  process.stdout.write(JSON.stringify({ closed, opened }, null, 2));
})();
```

- [ ] **Step 2: 跑探针确认失败**

Run: `cd frontend && node ../tests/frontend/mobile_action_sheet_ssr.cjs`
Expected: FAIL —— `ENOENT: no such file or directory .../MobileActionSheet.vue`。

- [ ] **Step 3: 实现壳组件**

新建 `frontend/src/components/chat/MobileActionSheet.vue`：

```vue
<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[260] flex items-end bg-black/35 backdrop-blur-[1px]"
      @click.self="close"
    >
      <div
        ref="sheetRef"
        class="w-full rounded-t-2xl border-t border-gray-100 bg-white p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-2xl dark:border-gray-800 dark:bg-gray-900"
        role="dialog"
        aria-modal="true"
        :aria-label="title || '操作面板'"
        tabindex="-1"
      >
        <div class="mx-auto mb-3 h-1 w-10 rounded-full bg-gray-300 dark:bg-gray-600" />
        <div v-if="title || subtitle" class="mb-2 flex items-center justify-between gap-3">
          <div class="min-w-0">
            <h3 v-if="title" class="text-sm font-bold text-gray-800 dark:text-gray-100">{{ title }}</h3>
            <p v-if="subtitle" class="mt-0.5 text-[11px] text-gray-400">{{ subtitle }}</p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-full p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
            aria-label="关闭"
            @click="close"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div class="max-h-[70vh] overflow-y-auto">
          <slot />
        </div>
        <button
          type="button"
          class="mt-3 w-full rounded-xl py-2 text-center text-xs text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          @click="close"
        >
          {{ closeLabel }}
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, onUnmounted, ref, watch } from "vue";

/**
 * 移动端底部操作抽屉的壳。
 *
 * 只负责：Teleport 到 body、遮罩、贴底容器、安全区、点遮罩 / Esc / 取消关闭、
 * 打开期间锁背景滚动、可访问性属性。业务内容一律走默认插槽。
 *
 * 使用约束：请**常驻挂载**、用 :open 切换显隐（不要 v-if 包住本组件）——
 * 壳靠 open 的变化来锁/放背景滚动，挂载时 open 已经是 true 的话不会触发 watch。
 */
const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    subtitle?: string;
    closeLabel?: string;
  }>(),
  { title: "", subtitle: "", closeLabel: "取消" },
);
const emit = defineEmits<{ (event: "close"): void }>();

const sheetRef = ref<HTMLElement | null>(null);
let previousBodyOverflow: string | null = null;

const close = () => emit("close");

const lockBodyScroll = () => {
  // SSR / 单测环境没有 document
  if (typeof document === "undefined" || previousBodyOverflow !== null) return;
  previousBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
};
const unlockBodyScroll = () => {
  if (typeof document === "undefined" || previousBodyOverflow === null) return;
  document.body.style.overflow = previousBodyOverflow;
  previousBodyOverflow = null;
};
const onKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape") close();
};

watch(
  () => props.open,
  async (open) => {
    if (open) {
      lockBodyScroll();
      document.addEventListener("keydown", onKeydown);
      await nextTick();
      sheetRef.value?.focus();
      return;
    }
    unlockBodyScroll();
    document.removeEventListener("keydown", onKeydown);
  },
);

onUnmounted(() => {
  unlockBodyScroll();
  if (typeof document !== "undefined") document.removeEventListener("keydown", onKeydown);
});
</script>
```

- [ ] **Step 4: 跑探针确认通过**

Run: `cd frontend && node ../tests/frontend/mobile_action_sheet_ssr.cjs`
Expected: 输出 JSON，且 `opened.hasDialog` / `hasAriaModal` / `hasBackdrop` / `hasSafeArea` / `hasTitle` / `hasSlot` / `hasCancel` 全为 `true`，`opened.hasSubtitle` 为 `true`；`closed.teleportHtml` 为空串。

- [ ] **Step 5: 追加壳的契约测试**

在 `tests/frontend/test_mobile_actions_sheet_contract.py` 末尾追加：

```python
import json
import shutil
import subprocess


def _can_render_sfc() -> bool:
    if shutil.which("node") is None:
        return False
    node_modules = ROOT / "frontend/node_modules"
    return all((node_modules / name).exists() for name in ("vue", "esbuild", "@vue/server-renderer"))


def test_action_sheet_shell_owns_appearance_close_and_scroll_lock():
    source = _read("frontend/src/components/chat/MobileActionSheet.vue")
    assert "<Teleport to=\"body\">" in source
    assert 'role="dialog"' in source
    assert 'aria-modal="true"' in source
    assert '@click.self="close"' in source
    assert "z-[260]" in source
    assert "env(safe-area-inset-bottom)" in source
    assert 'event.key === "Escape"' in source
    assert "document.body.style.overflow = \"hidden\"" in source
    # 常驻挂载约束必须写在注释里，避免后来者用 v-if 包住它导致不锁滚动
    assert "常驻挂载" in source


@pytest.mark.skipif(not _can_render_sfc(), reason="前端依赖未安装，跳过真渲染探针")
def test_action_sheet_only_renders_when_open():
    script = ROOT / "tests/frontend/mobile_action_sheet_ssr.cjs"
    proc = subprocess.run(["node", str(script)], cwd=ROOT / "frontend", capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)

    closed = data["closed"]
    assert closed["teleportHtml"] == "", "open=false 时不得渲染遮罩与内容"

    opened = data["opened"]
    assert opened["hasDialog"] is True
    assert opened["hasAriaModal"] is True
    assert opened["hasBackdrop"] is True, "遮罩必须带 z-[260] 全屏定位"
    assert opened["hasSafeArea"] is True, "贴底容器必须处理 iPhone 安全区"
    assert opened["hasTitle"] is True
    assert opened["hasSubtitle"] is True
    assert opened["hasSlot"] is True, "默认插槽内容必须真的渲染"
    assert opened["hasCancel"] is True
```

- [ ] **Step 6: 跑契约测试确认通过**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q`
Expected: 4 passed。

- [ ] **Step 7: Commit（由用户执行）**

```bash
git add frontend/src/components/chat/MobileActionSheet.vue \
        tests/frontend/mobile_action_sheet_ssr.cjs \
        tests/frontend/test_mobile_actions_sheet_contract.py
# 建议 message: feat(chat): 抽出移动端底部操作抽屉壳组件
```

---

### Task 3: 抽屉内容 `MobileMessageActionsSheet`

**Files:**
- Create: `frontend/src/components/chat/MobileMessageActionsSheet.vue`
- Test: `tests/frontend/test_mobile_actions_sheet_contract.py`（追加）

- [ ] **Step 1: 追加失败的契约测试**

```python
def test_actions_sheet_content_has_four_sections_and_focus_highlight():
    source = _read("frontend/src/components/chat/MobileMessageActionsSheet.vue")
    for anchor in ("data", "continue", "call", "report"):
        assert f'data-section="{anchor}"' in source, f"缺少分组锚点 {anchor}"
    assert 'props.focus === "data"' in source, "focus=data 时必须走高亮分支"
    assert "border-l-2 border-primary" in source
    # 空组不渲染
    assert "v-if=\"canExport\"" in source
    assert "v-if=\"hasTrace\"" in source
    # ChatBI 与通用两套动作共用同一渲染，但事件要分开
    assert "chatbiAction" in source
    assert "continueAnalysis" in source
    assert "continueActionIcon" in source
    assert "chatbiActionIcon" in source
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q -k four_sections`
Expected: FAIL —— `FileNotFoundError`。

- [ ] **Step 3: 实现内容组件**

新建 `frontend/src/components/chat/MobileMessageActionsSheet.vue`：

```vue
<template>
  <div class="space-y-3">
    <!-- ① 数据 / 文件 -->
    <section
      v-if="hasConversationDataFile"
      data-section="data"
      class="space-y-0.5"
      :class="props.focus === 'data' ? 'rounded-xl border-l-2 border-primary bg-primary/5 py-1.5 pl-2 pr-1' : ''"
    >
      <div class="flex items-center gap-1.5 px-0.5 pb-1">
        <span class="text-[10px] font-semibold tracking-wide text-gray-400 dark:text-gray-500">数据 / 文件</span>
        <span v-if="reusableCount > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">数据 {{ reusableCount }}</span>
        <span v-if="artifactCount > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">文件 {{ artifactCount }}</span>
      </div>
      <button v-if="hasReusableResultEntry" type="button" class="sheet-row" @click="emit('openReusableResults')">
        <span>▤ 查看可复用结果</span>
        <span v-if="conversationReusableCount > 0" class="text-[10px] text-gray-400">{{ conversationReusableCount }} 条</span>
      </button>
      <button v-if="canExport" type="button" class="sheet-row" @click="emit('exportData')">
        <span>↓ 导出数据（Excel）</span>
      </button>
      <button v-if="hasArtifactEntry" type="button" class="sheet-row" @click="emit('openArtifacts')">
        <span>▣ 查看文件产物</span>
        <span v-if="conversationArtifactCount > 0" class="text-[10px] text-gray-400">{{ conversationArtifactCount }} 个</span>
      </button>
    </section>

    <!-- ② 继续分析（通用四件套 / ChatBI 推荐追问） -->
    <section v-if="continueActions.length" data-section="continue" class="space-y-0.5">
      <div class="px-0.5 pb-1 text-[10px] font-semibold tracking-wide text-gray-400 dark:text-gray-500">继续分析</div>
      <button
        v-for="action in continueActions"
        :key="action.id"
        type="button"
        class="flex w-full items-start gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
        @click="selectContinue(action)"
      >
        <span class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-gray-100 text-[11px] text-gray-500 dark:bg-gray-800 dark:text-gray-400">{{ iconFor(action.id) }}</span>
        <span class="min-w-0">
          <span class="block text-xs font-semibold text-gray-700 dark:text-gray-200">{{ action.label }}</span>
          <span v-if="action.description" class="mt-0.5 block text-[10px] leading-relaxed text-gray-400">{{ action.description }}</span>
        </span>
      </button>
    </section>

    <!-- ③ 本次调用 -->
    <section v-if="hasTokenStats || hasTrace" data-section="call" class="space-y-0.5">
      <div class="px-0.5 pb-1 text-[10px] font-semibold tracking-wide text-gray-400 dark:text-gray-500">本次调用</div>
      <button v-if="hasTokenStats" type="button" class="sheet-row" @click="emit('openStats')">
        <span>▤ 查看调用详情</span>
        <span class="text-[10px] text-gray-400">{{ tokenLabel }}</span>
      </button>
      <button v-if="hasTrace" type="button" class="sheet-row" @click="emit('openTrace')">
        <span>↗ 查看执行链路</span>
      </button>
    </section>

    <!-- ④ 沉淀 -->
    <section v-if="canSaveReport" data-section="report" class="space-y-0.5">
      <div class="px-0.5 pb-1 text-[10px] font-semibold tracking-wide text-gray-400 dark:text-gray-500">沉淀</div>
      <button type="button" class="sheet-row" @click="emit('saveReport')">
        <span>☆ 添加固化报表</span>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ChatBIInsightAction } from "@/types/chatbiInsight";
import {
  CONTINUE_ANALYSIS_ACTIONS,
  chatbiActionIcon,
  continueActionIcon,
  type ContinueAction,
} from "./continueAnalysisActions";

/**
 * 移动端操作抽屉的内容：四组（数据 / 文件、继续分析、本次调用、沉淀）。
 *
 * 空组不渲染；focus === "data" 时数据组高亮（点操作栏「▤ 数据」进来时）。
 * ChatBI 追问与通用沉淀动作共用同一套渲染，但事件分开上抛：ChatBI 的
 * local_action 需要原始 action 对象才能分派。
 */
const props = defineProps<{
  focus: "data" | null;
  hasConversationDataFile: boolean;
  reusableCount: number;
  artifactCount: number;
  hasReusableResultEntry: boolean;
  hasArtifactEntry: boolean;
  conversationReusableCount: number;
  conversationArtifactCount: number;
  canExport: boolean;
  hasTrace: boolean;
  hasTokenStats: boolean;
  tokenLabel: string;
  canSaveReport: boolean;
  chatbiActions: ChatBIInsightAction[];
  showGenericContinue: boolean;
}>();

const emit = defineEmits<{
  (event: "exportData"): void;
  (event: "openReusableResults"): void;
  (event: "openArtifacts"): void;
  (event: "openTrace"): void;
  (event: "openStats"): void;
  (event: "saveReport"): void;
  (event: "continueAnalysis", query: string): void;
  (event: "chatbiAction", action: ChatBIInsightAction): void;
}>();

const isChatbi = computed(() => props.chatbiActions.length > 0);
const continueActions = computed<(ContinueAction | ChatBIInsightAction)[]>(() => {
  if (isChatbi.value) return props.chatbiActions.slice(0, 6);
  return props.showGenericContinue ? CONTINUE_ANALYSIS_ACTIONS : [];
});
const iconFor = (id: string) => (isChatbi.value ? chatbiActionIcon(id) : continueActionIcon(id));
const selectContinue = (action: ContinueAction | ChatBIInsightAction) => {
  if (isChatbi.value) {
    emit("chatbiAction", action as ChatBIInsightAction);
    return;
  }
  emit("continueAnalysis", (action as ContinueAction).query);
};
</script>

<style scoped>
/* 抽屉行样式：与桌面 MessageActionMenus 的菜单项视觉保持一致 */
.sheet-row {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  border-radius: 0.75rem;
  padding: 0.625rem 0.75rem;
  text-align: left;
  font-size: 0.75rem;
  line-height: 1rem;
  color: rgb(75 85 99);
  transition: background-color 150ms;
}
.sheet-row:hover {
  background-color: rgb(249 250 251);
}
:global(.dark) .sheet-row {
  color: rgb(209 213 219);
}
:global(.dark) .sheet-row:hover {
  background-color: rgb(31 41 55);
}
</style>
```

- [ ] **Step 4: 跑契约测试确认通过**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q`
Expected: 5 passed。

- [ ] **Step 5: 类型检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: exit 0。

- [ ] **Step 6: Commit（由用户执行）**

```bash
git add frontend/src/components/chat/MobileMessageActionsSheet.vue \
        tests/frontend/test_mobile_actions_sheet_contract.py
# 建议 message: feat(chat): 新增移动端消息操作抽屉内容组件（四组）
```

---

### Task 4: `EmbedChat` 接入移动端入口与抽屉

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`（import 区、断点状态区、操作栏、`updateWidth`）
- Test: `tests/frontend/test_mobile_actions_sheet_contract.py`（追加）

- [ ] **Step 1: 追加失败的契约测试**

```python
def test_embedchat_mobile_bar_exposes_data_entry_and_sheet_trigger():
    source = _read("frontend/src/views/EmbedChat.vue")
    # 移动端「▤ 数据」入口：会话有数据/文件时才出现
    assert 'v-if="hasConversationDataFile"' in source
    assert '@click="openMobileActions(msg, \'data\')"' in source
    assert 'aria-label="查看本会话的数据和文件"' in source
    # 移动端「⋯ 更多」改为打开抽屉
    assert '@click="openMobileActions(msg, null)"' in source
    assert 'v-if="hasMobileSheetContent(msg)"' in source
    assert ":open=\"mobileActionsMessageId === msg.id\"" in source
    # 抽屉与两个入口都只作用于移动端
    assert 'class="sm:hidden flex shrink-0 items-center gap-1 rounded-md border border-primary/30' in source


def test_embedchat_mobile_bar_drops_inline_usage_and_continue_entries():
    source = _read("frontend/src/views/EmbedChat.vue")
    # 移动端单独的用量图标按钮必须消失（能力进了抽屉）
    assert 'class="flex sm:hidden shrink-0 items-center justify-center text-gray-400 hover:text-primary transition-colors rounded hover:bg-gray-100 dark:hover:bg-gray-800 p-2.5"' not in source
    # 桌面侧的用量 / 继续分析 / 更多浮层保持原样，但被 CSS 限制在 sm 以上
    assert 'class="hidden sm:flex shrink-0 items-center space-x-1"' in source


def test_embedchat_mobile_sheet_content_and_breakpoint_close():
    source = _read("frontend/src/views/EmbedChat.vue")
    assert "MobileActionSheet" in source
    assert "MobileMessageActionsSheet" in source
    assert "const hasMobileSheetContent = (msg: Message): boolean" in source
    assert "const handleSheetChatbiAction = (action: ChatBIInsightAction, msg: Message)" in source
    # 跨断点必须关掉抽屉
    assert "if (wasMobile !== isMobile.value) closeMobileActions();" in source
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q -k embedchat`
Expected: FAIL —— 三个 `test_embedchat_*` 全部失败。

- [ ] **Step 3: 加 import**

在 `frontend/src/views/EmbedChat.vue` 里 `import ChatBIContinueAnalysis from "@/components/chatbi/ChatBIContinueAnalysis.vue";` 之后追加：

```ts
import MobileActionSheet from "@/components/chat/MobileActionSheet.vue";
import MobileMessageActionsSheet from "@/components/chat/MobileMessageActionsSheet.vue";
import type { ChatBIInsightAction } from "@/types/chatbiInsight";
```

- [ ] **Step 4: 加抽屉状态与方法**

找到 `const windowWidth = ref(window.innerWidth);`（约第 6969 行），在它**之前**插入：

```ts
// —— 移动端操作抽屉（<640px 专用）：一个抽屉、两个入口 ——
const mobileActionsMessageId = ref<string | null>(null);
const mobileActionsFocus = ref<"data" | null>(null);

const openMobileActions = (msg: Message, focus: "data" | null) => {
  mobileActionsMessageId.value = msg.id;
  mobileActionsFocus.value = focus;
};
const closeMobileActions = () => {
  mobileActionsMessageId.value = null;
  mobileActionsFocus.value = null;
};

/** 抽屉里至少有一组内容时，「⋯ 更多」才出现（对齐桌面 MessageActionMenus 的 hasMore 语义）。 */
const hasMobileSheetContent = (msg: Message): boolean =>
  Boolean(
    hasConversationDataFile.value ||
      msg.chatbiInsight?.actions?.length ||
      (checkRole(msg, "agent") &&
        isGeneralAgentMessage(msg) &&
        !msg.chatbiInsight?.actions?.length &&
        !msg.isThinking &&
        visibleStreamBody(msg)) ||
      msg.trace_id ||
      msg.prompt_tokens !== undefined ||
      msg.completion_tokens !== undefined ||
      (canSaveGoldenReportFromMessage(msg) && checkRole(msg, "agent") && !msg.isThinking)
  );

/** ChatBI 追问分派：local_action 需要原始 action，其余走查询追问（与 ChatBIContinueAnalysis 内部一致）。 */
const handleSheetChatbiAction = (action: ChatBIInsightAction, msg: Message) => {
  if (action.action_type === "local_action") {
    handleChatBIResultAction({ ...action, result_id: action.result_id || msg.chatbiInsight?.result_id }, msg);
    return;
  }
  handleChatBIContinueSelect(action.query);
};
```

- [ ] **Step 5: 跨断点关抽屉**

把 `updateWidth` 改成：

```ts
const updateWidth = () => {
  const wasMobile = isMobile.value;
  windowWidth.value = window.innerWidth;
  // 跨过 640px 断点时必须收起抽屉，否则状态会悬空
  if (wasMobile !== isMobile.value) closeMobileActions();
  // Inject device context
  injectedContext.value = {
    ...injectedContext.value,
    device_type: isMobile.value ? '移动端(小屏幕)' : '桌面端(大屏幕)',
    display_hint: isMobile.value ? '窄屏排版优化' : '宽屏详尽展示'
  };
};
```

- [ ] **Step 6: 删掉移动端用量图标按钮**

在操作栏里把这段（移动端专用用量按钮 + 紧跟其后的桌面按钮开头）整体替换：

```vue
              <!-- Token 消耗：移动端展示图标，桌面端展示 数据库图标 + 用量 12.4K tok -->
              <button
                v-if="msg.prompt_tokens !== undefined || msg.completion_tokens !== undefined || msg.total_tokens !== undefined"
                @click="openModelCallStats(msg)"
                class="flex sm:hidden shrink-0 items-center justify-center text-gray-400 hover:text-primary transition-colors rounded hover:bg-gray-100 dark:hover:bg-gray-800 p-2.5"
                :title="getMessageTokenTooltip(msg)"
              >
                <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                  <ellipse cx="12" cy="5" rx="9" ry="3" />
                  <path d="M3 5v14a9 3 0 0 0 18 0V5" />
                  <path d="M3 12a9 3 0 0 0 18 0" />
                </svg>
              </button>
              <button
```

替换为：

```vue
              <!-- Token 消耗（桌面）：移动端不再占操作栏位置，能力进操作抽屉 -->
              <button
```

- [ ] **Step 7: 插入移动端「▤ 数据」入口**

在上一处的注释**之前**插入移动端数据按钮：

```vue
              <!-- 数据 / 文件（移动端）：入口提到明面上，带计数徽标 -->
              <button
                v-if="hasConversationDataFile"
                type="button"
                class="sm:hidden flex shrink-0 items-center gap-1 rounded-md border border-primary/30 bg-primary/5 px-2 py-1.5 text-[11px] font-medium text-primary transition-colors"
                aria-label="查看本会话的数据和文件"
                @click="openMobileActions(msg, 'data')"
              >
                <span aria-hidden="true">▤</span>
                <span v-if="currentMessageReusableCount(msg) > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">数据 {{ currentMessageReusableCount(msg) }}</span>
                <span v-if="msg.trace_id && artifactCount(msg.trace_id) > 0" class="rounded-full bg-primary px-1.5 py-0.5 text-[9px] font-semibold leading-none text-white">文件 {{ artifactCount(msg.trace_id) }}</span>
              </button>
              <!-- Token 消耗（桌面）：移动端不再占操作栏位置，能力进操作抽屉 -->
              <button
```

- [ ] **Step 8: 把桌面侧的三个入口收进 `sm` 分支**

把：

```vue
              <!-- 业务扩展与更多操作（保持完整宽度，随操作栏滚动） -->
              <div class="flex shrink-0 items-center space-x-1">
```

改成：

```vue
              <!-- 业务扩展与更多操作（桌面：保持完整宽度，随操作栏滚动；移动端改由操作抽屉承载） -->
              <div class="hidden sm:flex shrink-0 items-center space-x-1">
```

- [ ] **Step 9: 加移动端「⋯ 更多」按钮并把抽屉移到操作栏容器之外**

把操作栏那一段的结尾：

```vue
                  @save-report="handleSaveReportFromMessage(msg)"
                />
              </div>
            </div>
```

替换为：

```vue
                  @save-report="handleSaveReportFromMessage(msg)"
                />
              </div>
              <!-- 移动端：⋯ 更多（打开底部操作抽屉） -->
              <button
                v-if="hasMobileSheetContent(msg)"
                type="button"
                class="sm:hidden flex min-h-8 shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-medium text-gray-500 transition-colors hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
                aria-haspopup="dialog"
                :aria-expanded="mobileActionsMessageId === msg.id"
                @click="openMobileActions(msg, null)"
              >⋯ 更多</button>
            </div>
            <!-- 移动端操作抽屉（Teleport 到 body，不参与操作栏布局） -->
            <MobileActionSheet
              :open="mobileActionsMessageId === msg.id"
              title="更多操作"
              @close="closeMobileActions"
            >
              <MobileMessageActionsSheet
                :focus="mobileActionsFocus"
                :has-conversation-data-file="hasConversationDataFile"
                :reusable-count="currentMessageReusableCount(msg)"
                :artifact-count="msg.trace_id ? artifactCount(msg.trace_id) : 0"
                :has-reusable-result-entry="hasConversationReusableResult"
                :has-artifact-entry="hasConversationArtifact"
                :conversation-reusable-count="conversationReusableResultCount"
                :conversation-artifact-count="conversationArtifactCount"
                :can-export="Boolean(msg.trace_id)"
                :has-trace="Boolean(msg.trace_id)"
                :has-token-stats="msg.prompt_tokens !== undefined || msg.completion_tokens !== undefined"
                :token-label="getMessageTokenAmount(msg)"
                :can-save-report="canSaveGoldenReportFromMessage(msg) && checkRole(msg, 'agent') && !msg.isThinking"
                :chatbi-actions="msg.chatbiInsight?.actions || []"
                :show-generic-continue="checkRole(msg, 'agent') && isGeneralAgentMessage(msg) && !msg.chatbiInsight?.actions?.length && !msg.isThinking && visibleStreamBody(msg)"
                @export-data="msg.trace_id && exportData(msg.trace_id, 'xlsx')"
                @open-reusable-results="openReusableResults(msg.reusableResultStatus?.resultId, msg.trace_id, msg.reusableResultStatus?.status)"
                @open-artifacts="openMessageArtifacts(msg.trace_id)"
                @open-trace="msg.trace_id && openEmbedTrace(msg.trace_id)"
                @open-stats="openModelCallStats(msg)"
                @save-report="handleSaveReportFromMessage(msg)"
                @continue-analysis="(query) => handleQuickQuestion(query, 'send', visibleStreamBody(msg))"
                @chatbi-action="(action) => handleSheetChatbiAction(action, msg)"
              />
            </MobileActionSheet>
```

- [ ] **Step 10: 跑契约测试与类型检查**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q`
Expected: 8 passed。

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: exit 0（若报 `ChatBIInsightAction` 未使用等，检查 Step 3 的 import 是否加在正确位置）。

- [ ] **Step 11: Commit（由用户执行）**

```bash
git add frontend/src/views/EmbedChat.vue tests/frontend/test_mobile_actions_sheet_contract.py
# 建议 message: feat(chat): 移动端消息操作栏新增数据入口并接入操作抽屉
```

---

### Task 5: 两个既有抽屉改用公共壳

**Files:**
- Modify: `frontend/src/components/chat/MessageContinueAnalysis.vue:28-70`
- Modify: `frontend/src/components/chatbi/ChatBIContinueAnalysis.vue:28-70`
- Test: `tests/frontend/test_mobile_actions_sheet_contract.py`（追加）

- [ ] **Step 1: 追加失败的契约测试**

```python
def test_existing_drawers_reuse_the_shared_shell():
    continue_source = _read("frontend/src/components/chat/MessageContinueAnalysis.vue")
    chatbi_source = _read("frontend/src/components/chatbi/ChatBIContinueAnalysis.vue")
    for name, source in (("MessageContinueAnalysis", continue_source), ("ChatBIContinueAnalysis", chatbi_source)):
        assert "MobileActionSheet" in source, f"{name} 应复用公共抽屉壳"
        # 自绘遮罩必须消失，只剩桌面浮层
        assert 'class="fixed inset-0 z-[260] flex items-end bg-black/35 backdrop-blur-[1px]"' not in source, f"{name} 仍在自绘移动端遮罩"
        assert 'bg-black/35' not in source, f"{name} 的遮罩应完全交给壳"
        # 桌面浮层保留
        assert "absolute bottom-full right-0" in source, f"{name} 的桌面浮层不得被删掉"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q -k reuse`
Expected: FAIL。

- [ ] **Step 3: 改造 `MessageContinueAnalysis.vue`**

把 `<template v-if="open">` 整段（移动端抽屉 + 桌面浮层）替换为下面两块——壳**常驻挂载**，桌面浮层用 `v-if` 控制：

```vue
    <!-- 移动端底部抽屉：常驻挂载（靠 :open 切换），这样壳才能正确锁/放背景滚动 -->
    <MobileActionSheet
      :open="open && props.isMobile"
      title="继续分析"
      subtitle="将当前回答沉淀成可复用内容"
      @close="closeChooser"
    >
      <div class="space-y-1">
        <button v-for="action in actions" :key="action.id" type="button" class="group w-full rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-gray-100 dark:hover:bg-gray-800" @click="selectAction(action)">
          <div class="text-sm font-semibold text-gray-700 group-hover:text-gray-900 dark:text-gray-200 dark:group-hover:text-gray-100">{{ action.label }}</div>
          <div class="mt-0.5 text-xs leading-relaxed text-gray-400">{{ action.description }}</div>
        </button>
      </div>
    </MobileActionSheet>

    <template v-if="open && !props.isMobile">
      <div class="absolute bottom-full right-0 z-[80] mb-2 w-72 overflow-hidden rounded-xl border border-gray-200/80 bg-white/95 shadow-[0_14px_40px_rgba(15,23,42,0.16)] backdrop-blur-xl dark:border-gray-700 dark:bg-gray-900/95" role="menu">
        <!-- 原桌面浮层内容原样保留（标题行 + 动作列表） -->
      </div>
    </template>
```

并在 import 区加：

```ts
import MobileActionSheet from "./MobileActionSheet.vue";
```

- [ ] **Step 4: 改造 `ChatBIContinueAnalysis.vue`**

同样把移动端抽屉换成壳、桌面浮层条件改成 `v-if="open && !isMobile"`、去掉外层 `<template v-if="open">`：

```vue
    <!-- 移动端底部抽屉：常驻挂载（靠 :open 切换） -->
    <MobileActionSheet
      :open="open && isMobile"
      title="继续分析"
      subtitle="基于刚才的数据选择下一步"
      @close="closeChooser"
    >
      <div class="space-y-1">
        <button v-for="action in props.actions.slice(0, 6)" :key="action.id" type="button" class="group w-full rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-gray-100 dark:hover:bg-gray-800" @click="selectAction(action)">
          <div class="text-sm font-semibold text-gray-700 group-hover:text-gray-900 dark:text-gray-200 dark:group-hover:text-gray-100">{{ action.label }}</div>
          <div v-if="action.description" class="mt-0.5 text-xs leading-relaxed text-gray-400">{{ action.description }}</div>
        </button>
      </div>
    </MobileActionSheet>

    <template v-if="open && !isMobile">
      <div class="absolute bottom-full right-0 z-[80] mb-2 w-72 overflow-hidden rounded-xl border border-gray-200/80 bg-white/95 shadow-[0_14px_40px_rgba(15,23,42,0.16)] backdrop-blur-xl dark:border-gray-700 dark:bg-gray-900/95" role="menu">
        <!-- 原桌面浮层内容原样保留 -->
      </div>
    </template>
```

import 区加：

```ts
import MobileActionSheet from "@/components/chat/MobileActionSheet.vue";
```

- [ ] **Step 5: 跑契约测试与类型检查**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q`
Expected: 9 passed。

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: exit 0。

- [ ] **Step 6: 跑与这两个组件相关的既有测试**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend -q -k "continue or chatbi or embed"`
Expected: 全绿（关注 `AgentDebug.vue` 仍在用 `MessageContinueAnalysis`，接口未变）。

- [ ] **Step 7: Commit（由用户执行）**

```bash
git add frontend/src/components/chat/MessageContinueAnalysis.vue \
        frontend/src/components/chatbi/ChatBIContinueAnalysis.vue \
        tests/frontend/test_mobile_actions_sheet_contract.py
# 建议 message: refactor(chat): 继续分析与 ChatBI 抽屉复用公共底部壳
```

---

### Task 6: 变异验证 + 全量回归 + CHECKLIST

**Files:**
- Modify: `tests/CHECKLIST.md`（追加一行）

- [ ] **Step 1: 逐条做变异验证（每次改一处 → 跑测试 → 必须变红 → 字节级还原）**

每次都用 `cp` 备份原文件，改完跑 `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_mobile_actions_sheet_contract.py -q`，确认目标用例失败后 `cp` 还原，并用 `git diff --stat` 确认还原后无残留。

| 编号 | 变异 | 期望被谁捕获 |
| --- | --- | --- |
| M1 | `EmbedChat.vue` 里 `v-if="hasConversationDataFile"` 改成 `v-if="true"` | `test_embedchat_mobile_bar_exposes_data_entry_and_sheet_trigger` |
| M2 | 把删掉的移动端用量按钮那段整块贴回操作栏 | `test_embedchat_mobile_bar_drops_inline_usage_and_continue_entries` |
| M3 | `MobileActionSheet.vue` 去掉 `env(safe-area-inset-bottom)` | `test_action_sheet_shell_owns_appearance_close_and_scroll_lock` 与 SSR 探针 |
| M4 | `MobileActionSheet.vue` 的 `watch` 改成 `immediate: true`（模拟"挂载即 open"下的锁滚动失效路径） | SSR 探针（`document is not defined`） |
| M5 | `MobileMessageActionsSheet.vue` 的高亮条件 `props.focus === 'data'` 改成 `false` | `test_actions_sheet_content_has_four_sections_and_focus_highlight` |
| M6 | `EmbedChat.vue` 的 `if (wasMobile !== isMobile.value) closeMobileActions();` 删掉 | `test_embedchat_mobile_sheet_content_and_breakpoint_close` |
| M7 | `MessageContinueAnalysis.vue` 把自绘遮罩贴回去 | `test_existing_drawers_reuse_the_shared_shell` |
| M8 | `continueAnalysisActions.ts` 里删掉 `chatbiActionIcon` 导出 | `test_continue_actions_live_in_one_shared_module` |

- [ ] **Step 2: 全量回归**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend -q`
Expected: 基线 `1708 passed / 1 skipped` + 本次新增 9 条 = **1717 passed / 1 skipped / 0 failed**（若基线不同，以「新增 9 条全绿、无新增失败」为准）。

- [ ] **Step 3: 类型检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: exit 0。

- [ ] **Step 4: 追加 CHECKLIST 行**

在 `tests/CHECKLIST.md` 末尾追加（保持 5 列 / 7 个 `|` 分隔字段，单元格内不要出现裸 `|`）：

```markdown
| 移动端 AI 消息操作栏重排与操作抽屉 (Mobile Message Actions Sheet) | `frontend/src/views/EmbedChat.vue`、`frontend/src/components/chat/MobileActionSheet.vue`、`frontend/src/components/chat/MobileMessageActionsSheet.vue`、`frontend/src/components/chat/continueAnalysisActions.ts`、`frontend/src/components/chat/MessageContinueAnalysis.vue`、`frontend/src/components/chatbi/ChatBIContinueAnalysis.vue`、`tests/frontend/test_mobile_actions_sheet_contract.py`、`tests/frontend/mobile_action_sheet_ssr.cjs`、`tests/CHECKLIST.md` | **用户反馈原话**：「移动端下呢」→「你准备移动端下如何优化」→ 看完三版排布对比后选定「A · 一行放核心 + 数据图标带徽标」。**先做视觉对比再动手**：按 375px 手机宽度并排渲染 A（一行核心 + 数据图标 + 更多）、B（极简一行、全部收进抽屉）、C（拆两行）三版排布并截图，据此确认 A 命中全部四个目标。**现状问题**：① 移动端「数据 / 文件」入口藏在 `hidden sm:block` 之外——只能进「⋯ 更多」浮层且看不到「数据 N」「文件 N」徽标（`EmbedChat.vue:1139`、`MessageActionMenus.vue:187-201`）；② 操作栏 `flex-nowrap + overflow-x-auto`，375px 上时间戳 + 5 图标 + 用量 + 继续分析 + 更多已接近上限；③ 同一行里「继续分析」是底部抽屉、「更多」是贴按钮浮层，两种手感；④ `hidden sm:inline` 让「继续分析」在手机上只剩一个图标。**落地（仅改 <640px，桌面零改动）**：① 新增 `MobileActionSheet.vue` 作为底部抽屉**壳**（Teleport body、遮罩、`rounded-t-2xl`、`pb-[max(1rem,env(safe-area-inset-bottom))]`、`role="dialog"` + `aria-modal`、点遮罩 / Esc / 取消关闭、打开期间锁 `body.style.overflow` 并在关闭与卸载时还原），要求**常驻挂载**（挂载即 open 不会触发 watch，所以壳里不做 `immediate`）；② 新增 `MobileMessageActionsSheet.vue` 作为抽屉**内容**，四组（数据 / 文件 → 继续分析 → 本次调用 → 沉淀），空组不渲染，`focus === 'data'` 时数据组高亮（浅蓝底 + 左侧主色竖条），ChatBI 追问与通用沉淀动作共用渲染但事件分开上抛（`chatbiAction` / `continueAnalysis`）；③ 操作栏新增「▤ 数据」徽标按钮（`sm:hidden` + `v-if="hasConversationDataFile"`，无数据时**不出现**——手机上禁用按钮没有 hover 提示）与移动端「⋯ 更多」按钮（`v-if="hasMobileSheetContent(msg)"`），两个入口打开**同一个抽屉**，差别只是数据组是否高亮；④ 删掉移动端单独的用量图标按钮，桌面用量 / 数据 / 继续分析 / 更多浮层统一包进 `hidden sm:flex`；⑤ 抽屉用 `:open="mobileActionsMessageId === msg.id"` 定位当前消息（消息循环 key 是 `msg.id`），并在 `updateWidth` 里跨 640px 断点时 `closeMobileActions()`；⑥ 「继续分析」四个动作与两类图标映射从组件内联搬到 `continueAnalysisActions.ts`，`MessageContinueAnalysis` / `ChatBIContinueAnalysis` 与抽屉共用一份，两个既有抽屉同步换成公共壳（桌面浮层保留）。**测试**：新增 9 条契约 + 1 个真渲染探针 `mobile_action_sheet_ssr.cjs`（`vue/compiler-sfc` 编译真实源码 + esbuild 剥 TS + `@vue/server-renderer` 渲染，断言 `open=false` 时 teleport 内容为空、`open=true` 时 dialog / aria-modal / 遮罩 / 安全区 / 标题 / 插槽 / 取消齐备）。**变异验证 8/8 全部被捕获且字节级还原**（M1 数据入口条件放开、M2 用量按钮贴回、M3 去掉安全区、M4 壳改 `immediate`、M5 高亮失效、M6 断点不关抽屉、M7 既有抽屉自绘遮罩回潮、M8 图标导出被删）。**回归**：`pytest --confcutdir=tests/frontend tests/frontend` 全量 **1717 passed / 1 skipped / 0 failed**；`vue-tsc --noEmit` **0 报错**。**未做**：未跑 `./dev.sh`、未执行 `git commit`。 | ✅ 已落地：移动端一行内可见带计数的「▤ 数据」入口、常态不再横向滚动，「⋯ 更多」与「继续分析」统一为同一套底部抽屉，「继续分析」四项在手机上带文字与说明。**需用户在控制台执行 `./dev.sh` 重建前端并刷新页面**后验收：在 ≤390px 宽度下 AI 消息操作栏应一行放得下（时间戳 · 复制 · 重新生成 · 赞 · 踩 · ▤ 数据 · ⋯ 更多）；有数据 / 文件时 ▤ 徽标数字应与桌面「数据 / 文件」一致、无数据时 ▤ 不出现；点 ▤ 弹出抽屉且「数据 / 文件」组高亮，点 ⋯ 弹出同一抽屉不高亮；抽屉里「继续分析」四项带说明文字、查看调用详情 / 查看执行链路 / 添加固化报表与桌面行为一致；点遮罩 / 取消 / Esc 均可关闭且关闭后页面滚动恢复正常；桌面端（≥640px）入口、浮层与样式与改动前完全一致。 | 2026-10-12 |
```

- [ ] **Step 5: 校验 CHECKLIST 行格式**

Run: `tail -1 tests/CHECKLIST.md | awk -F'|' '{print NF}'`
Expected: `7`。

- [ ] **Step 6: 汇报**

改动文件、验证结果（契约 9 条 / 探针 / 变异 8 项 / 全量回归 / vue-tsc）、以及需要用户手动执行的 `./dev.sh` 与 7 条验收清单。**不要**执行 `git commit`。

---

## 自审记录（写完计划后对照 spec 复查）

- **Spec 覆盖**：交互规格 → Task 4；抽屉四组与高亮 → Task 3；壳（安全区 / 滚动锁 / Esc / 可访问性）→ Task 2；组件拆分与两个既有抽屉换壳 → Task 1、Task 5；数据流零后端改动 → Task 4 的 props 绑定全部复用既有派生值；边界（空组、全空、断点、暗色、安全区、长内容）→ Task 2/3/4；测试策略 4 条 → Task 2/6；CHECKLIST → Task 6；验收清单 → Task 6 Step 6。
- **占位符扫描**：`continueAnalysisActions.ts` 的四个 `query` 明确要求从既有文件整段搬移，并由 `test_both_continue_consumers_import_the_shared_module` 兜底；其余步骤均为可直接落笔的完整代码。Task 5 的桌面浮层标注为「原样保留」，因为它的完整内容已在代码库中且不被本任务修改。
- **类型一致性**：`MobileActionSheet` 的 props／emit 为 `open/title/subtitle/closeLabel` + `close`；`MobileMessageActionsSheet` 的 props 为 `focus/hasConversationDataFile/reusableCount/artifactCount/hasReusableResultEntry/hasArtifactEntry/conversationReusableCount/conversationArtifactCount/canExport/hasTrace/hasTokenStats/tokenLabel/canSaveReport/chatbiActions/showGenericContinue`，emit 为 `exportData/openReusableResults/openArtifacts/openTrace/openStats/saveReport/continueAnalysis/chatbiAction`——与 Task 4 的模板绑定逐项对齐；`ContinueAction` 在 Task 1 定义、Task 3 引用。
