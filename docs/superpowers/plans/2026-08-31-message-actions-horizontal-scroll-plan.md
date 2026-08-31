# 窄屏消息操作栏横向滚动 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 EmbedChat 窄屏消息操作栏中的按钮保持完整宽度，并在内容溢出时横向滚动。

**Architecture:** 保留现有消息操作栏和组件结构，只收紧 flex 尺寸约束。外层继续使用单行 `flex-nowrap` + `overflow-x-auto`；操作项、MessageActionMenus 根节点和右侧反馈组设置不可收缩/不换行，移除窄屏下会争抢剩余空间的 `ml-auto`。

**Tech Stack:** Vue 3、TypeScript、Tailwind CSS、pytest 源码契约测试、vue-tsc。

---

## 文件映射

- Modify: `frontend/src/views/EmbedChat.vue` — 消息底部操作栏外层、Token 按钮和右侧反馈/扩展操作组的 flex 约束。
- Modify: `frontend/src/components/chat/MessageActionMenus.vue` — 根节点及“更多”按钮的不可收缩、不换行约束。
- Create: `tests/frontend/test_message_actions_horizontal_scroll_contract.py` — 锁定横向滚动与防压缩契约。

### Task 1: 先写窄屏布局契约测试

**Files:**
- Create: `tests/frontend/test_message_actions_horizontal_scroll_contract.py`

- [ ] **Step 1: 写一个失败测试，验证消息操作栏和子操作项不会被压缩**

```python
from pathlib import Path


ROOT = Path(__file__).parents[2]
EMBED = ROOT / "frontend/src/views/EmbedChat.vue"
ACTION_MENU = ROOT / "frontend/src/components/chat/MessageActionMenus.vue"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_embed_message_actions_scroll_without_compressing_items() -> None:
    source = _source(EMBED)
    assert 'class="flex min-w-0 max-w-full flex-nowrap items-center space-x-2 overflow-x-auto' in source
    assert 'class="flex shrink-0 items-center space-x-1"' in source
    assert 'class="hidden sm:flex shrink-0 items-center space-x-1.5' in source
    assert 'space-x-1 ml-auto' not in source


def test_message_action_menu_keeps_root_and_more_action_intrinsic_width() -> None:
    source = _source(ACTION_MENU)
    assert '<div ref="root" class="flex shrink-0 items-center gap-1.5">' in source
    assert 'class="flex min-h-8 shrink-0 items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium' in source
```

- [ ] **Step 2: 运行测试，确认当前源码按预期失败**

Run:

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_message_actions_horizontal_scroll_contract.py -q
```

Expected: FAIL，因为当前右侧组仍是 `ml-auto`，MessageActionMenus 根节点和“更多”按钮也没有完整的不可收缩约束。

### Task 2: 实现最小布局修复

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue` 消息操作栏区域（约 830-1010 行）
- Modify: `frontend/src/components/chat/MessageActionMenus.vue` 模板（约 91-138 行）

- [ ] **Step 1: 给 EmbedChat 的消息操作项补充不可压缩边界**

在现有外层类名中保留 `min-w-0 max-w-full flex-nowrap overflow-x-auto`；将 Token 统计桌面按钮的类名改为包含 `shrink-0`，将右侧反馈/扩展操作组的类名改为：

```html
<div class="flex shrink-0 items-center space-x-1">
```

这样右侧操作组作为滚动内容的一部分保留自身宽度，不再通过 `ml-auto` 把其他按钮压窄。

- [ ] **Step 2: 给 MessageActionMenus 根节点和“更多”按钮补充不可压缩、不换行约束**

将根节点改为：

```html
<div ref="root" class="flex shrink-0 items-center gap-1.5">
```

将“更多”按钮改为包含 `shrink-0 whitespace-nowrap` 的单行 flex 按钮，保留现有事件、菜单定位和条件渲染：

```html
<button type="button" class="flex min-h-8 shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200" :class="{ 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200': openMenu === 'more' }" :aria-expanded="openMenu === 'more'" aria-haspopup="menu" title="更多操作" @click="toggle('more')">⋯ 更多</button>
```

- [ ] **Step 3: 运行契约测试，确认最小修改通过**

Run:

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_message_actions_horizontal_scroll_contract.py -q
```

Expected: PASS。

### Task 3: 回归验证

**Files:**
- Test: `tests/frontend/test_message_actions_horizontal_scroll_contract.py`
- Test: existing frontend contract tests selected by changed components

- [ ] **Step 1: 运行相关消息渲染、可复用结果和输入图标契约测试**

Run:

```bash
pytest --confcutdir=tests/frontend \
  tests/frontend/test_message_actions_horizontal_scroll_contract.py \
  tests/frontend/test_message_renderer_contract.py \
  tests/frontend/test_reusable_result_contract.py \
  tests/frontend/test_chat_input_icon_contract.py -q
```

Expected: PASS；若失败，只修复本次 flex 类名变更引起的契约冲突，不扩大范围。

- [ ] **Step 2: 运行前端类型检查**

Run from `frontend`:

```bash
./node_modules/.bin/vue-tsc --noEmit
```

Expected: PASS。此任务不启动 `./dev.sh`，真实浏览器窄屏视觉验收由用户在控制台启动服务后执行。

- [ ] **Step 3: 检查差异和工作区边界**

Run:

```bash
git diff --check -- frontend/src/views/EmbedChat.vue frontend/src/components/chat/MessageActionMenus.vue tests/frontend/test_message_actions_horizontal_scroll_contract.py
git status --short
```

Expected: 无空白错误；只报告本任务涉及的修改和用户已有的未提交文件，不自动暂存或提交。
