# 嵌入个人中心「返回对话」浮标方向感知收起 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/embed/personal` 的「返回对话」浮标在用户向下滚看内容时收起、向上滚或停手时恢复，解决它作为 `fixed` 浮层必然遮挡正文的问题。

**Architecture:** 监听**个人中心滚动容器**（不是 `window`）的 `scroll` 事件，按位移方向切换一个 `backFabHidden` ref；该 ref 同时驱动 CSS 类（淡出 + 不可点）与 `aria-hidden`。向下滚时排一个 1.2 秒兜底定时器，防止「滚到底才想返回、浮标恰好收起」。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript + Tailwind CSS 3；测试为 pytest 源码静态断言（`tests/frontend` 既有风格）。

**设计依据：** `docs/superpowers/specs/2026-10-16-embed-personal-back-fab-design.md`

---

## ⚠️ 项目规范约束（先读这一段）

1. **不要自行执行 `git commit`。** 本项目 `AGENTS.md` 明确要求：改动完成后只汇报，由用户决定何时提交。因此下文中标为「提交」的步骤**必须先向用户确认**；若用户未明确要求，则跳过该步骤、只汇报。
2. 不要执行 `./dev.sh` 或任何部署脚本。
3. 测试命令统一带 `--confcutdir=tests/frontend`。
4. 类型检查命令为 `NODE_OPTIONS=--max-old-space-size=6144 npx vue-tsc -b --force`，**基线 79 条既有错误**，判断标准是「净新增 0」而非「零错误」。

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `frontend/src/views/EmbedPersonal.vue` | 唯一被改的视图：容器加 `ref`，浮标加收起态，脚本加滚动监听 | Modify |
| `tests/frontend/test_embed_personal_contract.py` | 该页的契约测试（已有 10 项），新增收起行为断言 | Modify |
| `tests/CHECKLIST.md` | 交付记录表 | Modify |

`EmbedPersonal.vue` 当前约 543 行，职责单一（凭据门禁 + 渲染 `PersonalCenter` + 返回浮标），**不需要拆分**。

---

### Task 1: 先写契约测试（预期全部失败）

**Files:**
- Modify: `tests/frontend/test_embed_personal_contract.py`（在文件末尾追加）

- [ ] **Step 1: 在测试文件末尾追加以下 8 条断言**

注意：文件里**已经有** `_view()` 与 `_return_button_tag()` 两个辅助函数（第 60-71 行附近），直接复用，**不要重复定义**。

```python
def test_scroll_listener_is_bound_to_container_not_window():
    """监听必须挂在滚动容器上。

    个人中心的滚动容器是 `<div class="h-full w-full overflow-y-auto">`，
    页面本身不滚动——挂到 window 上会一个事件都收不到。
    """
    view = _view()
    assert 'ref="scrollContainerRef"' in view, "滚动容器缺少 ref，无法挂监听"
    assert "scrollContainerRef.value" in view, "未通过容器 ref 取元素"
    assert "addEventListener(\"scroll\"" in view or "addEventListener('scroll'" in view, (
        "未注册 scroll 监听"
    )
    # 不能出现 window.addEventListener("scroll" ...)
    assert 'window.addEventListener("scroll"' not in view, (
        "监听挂到了 window 上——本页滚动的是容器，收不到事件"
    )


def test_back_fab_hides_on_scroll_down():
    """向下滚（看内容）时收起。"""
    view = _view()
    m = re.search(r"const handleContainerScroll = \(\) => \{(.*?)\n\};", view, re.S)
    assert m, "缺少 handleContainerScroll"
    body = m.group(1)
    assert "backFabHidden.value = true" in body, "向下滚未收起浮标"
    assert "delta > 0" in body, "未按位移方向判断"


def test_back_fab_restores_immediately_on_scroll_up():
    """向上滚（想回上面）时立即恢复。"""
    view = _view()
    m = re.search(r"const handleContainerScroll = \(\) => \{(.*?)\n\};", view, re.S)
    assert m, "缺少 handleContainerScroll"
    body = m.group(1)
    assert "delta < 0" in body, "未处理向上滚"
    assert "backFabHidden.value = false" in body, "向上滚未恢复浮标"


def test_scroll_up_cancels_pending_restore_timer():
    """向上滚必须取消待执行的兜底定时器。

    否则「立即恢复」之后，先前排队的定时器还会再触发一次——无副作用，
    但属于多余的状态跳变。
    """
    view = _view()
    m = re.search(r"const handleContainerScroll = \(\) => \{(.*?)\n\};", view, re.S)
    assert m, "缺少 handleContainerScroll"
    body = m.group(1)
    up_branch = body.split("delta < 0")[1]
    assert "clearRestoreTimer()" in up_branch, "向上滚分支未取消兜底定时器"


def test_back_fab_has_restore_fallback():
    """停止滚动后必须有兜底恢复。

    纯方向感知的洞：滚到底部后才想返回时，最后一段动作是向下滚，浮标恰好收起。
    用户明确要求保留这条兜底。
    """
    view = _view()
    m = re.search(r"const handleContainerScroll = \(\) => \{(.*?)\n\};", view, re.S)
    assert m, "缺少 handleContainerScroll"
    body = m.group(1)
    assert "setTimeout" in body, "缺少兜底恢复定时器"
    assert "BACK_FAB_RESTORE_MS" in body, "定时器未使用具名常量"
    assert re.search(r"const BACK_FAB_RESTORE_MS = \d+", view), "未定义恢复时长常量"


def test_scroll_jitter_threshold_and_top_guard_exist():
    """位移阈值与顶部保护都必须存在。

    阈值：移动端惯性滚动会产生大量微小反向抖动，不设阈值浮标会疯狂闪烁。
    顶部保护：刚进页面（scrollTop = 0）只向下滚一点点时，「在看内容」的语义还不成立。
    """
    view = _view()
    assert re.search(r"const SCROLL_JITTER_PX = \d+", view), "未定义抖动阈值常量"
    assert re.search(r"const SCROLL_TOP_GUARD_PX = \d+", view), "未定义顶部保护常量"
    m = re.search(r"const handleContainerScroll = \(\) => \{(.*?)\n\};", view, re.S)
    assert m, "缺少 handleContainerScroll"
    body = m.group(1)
    assert "SCROLL_JITTER_PX" in body, "未使用抖动阈值"
    assert "SCROLL_TOP_GUARD_PX" in body, "未使用顶部保护"


def test_hidden_state_is_inert_and_accessible():
    """收起态必须同时不可点且对辅助技术隐藏。

    pointer-events-none 只挡指针，挡不住屏幕阅读器——不加 aria-hidden
    会读出一个「看不见但存在」的按钮。
    """
    view = _view()
    tag = _return_button_tag()
    assert "pointer-events-none" in view, "收起态缺少 pointer-events-none"
    assert "aria-hidden" in tag, "收起态缺少 aria-hidden"
    assert "opacity-0" in view, "收起态缺少透明度变化"


def test_scroll_listener_and_timer_are_cleaned_up():
    """卸载时必须移除监听并清掉定时器，否则泄漏。"""
    view = _view()
    unmount = view.split("onUnmounted(")[-1]
    assert "removeEventListener" in unmount or "removeEventListener" in view, (
        "未移除 scroll 监听"
    )
    assert "clearRestoreTimer" in view, "未清理兜底定时器"
```

- [ ] **Step 2: 运行，确认全部失败**

Run:
```bash
.venv/bin/python -m pytest --confcutdir=tests/frontend \
  tests/frontend/test_embed_personal_contract.py -q
```

Expected: **8 failed, 10 passed**（新增的 8 条全部失败——实现还不存在；原有 10 条仍通过）

- [ ] **Step 3: 提交测试（先问用户）**

按本文档开头的项目规范，**先向用户确认**再执行：

```bash
git add tests/frontend/test_embed_personal_contract.py
git commit -m "test(embed): 补 EmbedPersonal 返回浮标方向感知收起的契约测试"
```

---

### Task 2: 容器 ref + 收起态样式

**Files:**
- Modify: `frontend/src/views/EmbedPersonal.vue:23-26`（容器）
- Modify: `frontend/src/views/EmbedPersonal.vue:44-56`（浮标）

- [ ] **Step 1: 给滚动容器加 ref**

把：

```html
  <div
    v-if="gateState === 'granted'"
    class="h-full w-full overflow-y-auto overflow-x-hidden bg-gray-100 custom-scrollbar"
  >
```

改为：

```html
  <div
    ref="scrollContainerRef"
    v-if="gateState === 'granted'"
    class="h-full w-full overflow-y-auto overflow-x-hidden bg-gray-100 custom-scrollbar"
  >
```

> 注意：`ref` 必须写在 `v-if` **之前**的位置无所谓（Vue 属性顺序不影响行为），但要与文件里其他元素的书写顺序风格保持一致。

- [ ] **Step 2: 给浮标加收起态类与 aria-hidden**

在浮标的 `class` 之后、`aria-label` 之前插入两行绑定（`class` 属性本身保持不变）：

```html
      :class="backFabHidden ? 'pointer-events-none translate-y-2 opacity-0' : 'translate-y-0 opacity-100'"
      :aria-hidden="backFabHidden ? 'true' : undefined"
```

同时把 `transition-all` 明确为带时长，避免依赖默认值：

```html
      class="fixed bottom-4 right-4 z-30 inline-flex min-h-11 items-center gap-2 rounded-full bg-white/90 px-4 text-sm font-medium text-gray-600 shadow-sm transition-all duration-200 hover:bg-white hover:text-primary hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 active:scale-95 sm:hidden dark:bg-gray-900/90 dark:text-gray-300 dark:hover:bg-gray-900 dark:hover:text-primary"
```

> `sm:hidden` 必须保留——宽屏 Web 下此页有完整导航可回退，浮标纯属多余。

- [ ] **Step 3: 运行测试，确认样式相关 2 条已通过、其余仍失败**

Run:
```bash
.venv/bin/python -m pytest --confcutdir=tests/frontend \
  tests/frontend/test_embed_personal_contract.py -q
```

Expected: **7 failed, 11 passed**（只有
`test_hidden_state_is_inert_and_accessible` 转为通过——它依赖的
`pointer-events-none` / `aria-hidden` / `opacity-0` 已随样式一起加好；
`test_scroll_listener_is_bound_to_container_not_window` 仍失败，因为
`scrollContainerRef.value` 与 `addEventListener` 在 Task 3 才写）

---

### Task 3: 滚动监听逻辑

**Files:**
- Modify: `frontend/src/views/EmbedPersonal.vue`（script 区，返回浮标逻辑之后）

- [ ] **Step 1: 在 `goBackToChat` 定义之后插入滚动逻辑**

```ts
// --- 返回浮标的方向感知收起 -----------------------------------------------
// 浮标是 fixed 浮层，滚动正文时必然压住内容；向下滚（在看内容）时收起，
// 向上滚（想回上面）或停手 1.2 秒后恢复。
// 注意：本页滚动的是**容器**而不是 window（见模板上的 scrollContainerRef），
// 监听必须挂在容器上，挂到 window 会一个事件都收不到。

/** 位移低于该值视为抖动：移动端惯性滚动会产生大量微小反向抖动。 */
const SCROLL_JITTER_PX = 8;
/** 顶部附近不收起：刚进页面只滚一点点时，「在看内容」的语义还不成立。 */
const SCROLL_TOP_GUARD_PX = 64;
/** 兜底恢复时长：防「滚到底才想返回，浮标恰好是收起的」。 */
const BACK_FAB_RESTORE_MS = 1200;

const scrollContainerRef = ref<HTMLElement | null>(null);
const backFabHidden = ref(false);

/** 在 onMounted 时留存，供 onUnmounted 解绑——那时 ref 可能已被置空。 */
let scrollEl: HTMLElement | null = null;
let lastScrollTop = 0;
let restoreTimer: number | undefined;

const clearRestoreTimer = () => {
  if (restoreTimer !== undefined) {
    window.clearTimeout(restoreTimer);
    restoreTimer = undefined;
  }
};

const handleContainerScroll = () => {
  if (!scrollEl) return;

  const top = scrollEl.scrollTop;
  const delta = top - lastScrollTop;

  if (Math.abs(delta) < SCROLL_JITTER_PX) return;

  if (delta > 0 && top > SCROLL_TOP_GUARD_PX) {
    // 向下滚：收起，并排一个兜底恢复
    backFabHidden.value = true;
    clearRestoreTimer();
    restoreTimer = window.setTimeout(() => {
      backFabHidden.value = false;
      restoreTimer = undefined;
    }, BACK_FAB_RESTORE_MS);
  } else if (delta < 0) {
    // 向上滚：立即恢复，并取消兜底（否则它还会再触发一次多余跳变）
    clearRestoreTimer();
    backFabHidden.value = false;
  }

  lastScrollTop = top;
};
```

- [ ] **Step 2: 在既有的 `onMounted(detectBackToChat)` 之后绑定监听**

```ts
onMounted(() => {
  scrollEl = scrollContainerRef.value;
  // passive: 只读监听，不阻止默认行为，避免拖累滚动性能
  scrollEl?.addEventListener("scroll", handleContainerScroll, { passive: true });
});
```

- [ ] **Step 3: 在既有的 `onUnmounted` 中解绑并清理**

文件第 512-514 行当前是：

```ts
onUnmounted(() => {
  window.removeEventListener("message", handleHostMessage);
});
```

改为：

```ts
onUnmounted(() => {
  window.removeEventListener("message", handleHostMessage);
  scrollEl?.removeEventListener("scroll", handleContainerScroll);
  scrollEl = null;
  clearRestoreTimer();
});
```

- [ ] **Step 4: 运行测试，确认 18 条全部通过**

Run:
```bash
.venv/bin/python -m pytest --confcutdir=tests/frontend \
  tests/frontend/test_embed_personal_contract.py -q
```

Expected: **18 passed**

- [ ] **Step 5: 类型检查，确认净新增 0**

Run:
```bash
cd frontend && NODE_OPTIONS=--max-old-space-size=6144 npx vue-tsc -b --force 2>&1 | grep -cE "error TS"
```

Expected: **79**（与基线一致；若出现 EmbedPersonal.vue 相关的新错误，必须修掉）

- [ ] **Step 6: 提交（先问用户）**

```bash
git add frontend/src/views/EmbedPersonal.vue
git commit -m "feat(embed): EmbedPersonal 返回浮标按滚动方向收起，停手 1.2s 兜底恢复"
```

---

### Task 4: 变异验证与全量回归

**Files:**
- 不改文件（只做验证）

- [ ] **Step 1: 变异 A — 去掉兜底定时器**

用脚本把 `setTimeout` 那段临时删掉，运行测试，**必须** `test_back_fab_has_restore_fallback` 失败：

```bash
cp frontend/src/views/EmbedPersonal.vue .mc_bak
.venv/bin/python - <<'PY'
from pathlib import Path
p = Path("frontend/src/views/EmbedPersonal.vue"); s = p.read_text(encoding="utf-8")
old = """    clearRestoreTimer();
    restoreTimer = window.setTimeout(() => {
      backFabHidden.value = false;
      restoreTimer = undefined;
    }, BACK_FAB_RESTORE_MS);"""
assert old in s, "定位失败"
p.write_text(s.replace(old, "    clearRestoreTimer();", 1), encoding="utf-8")
PY
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_embed_personal_contract.py -q 2>&1 | tail -2
cp .mc_bak frontend/src/views/EmbedPersonal.vue
```

Expected: `FAILED ...::test_back_fab_has_restore_fallback`

- [ ] **Step 2: 变异 B — 监听改挂 window**

```bash
cp frontend/src/views/EmbedPersonal.vue .mc_bak
.venv/bin/python - <<'PY'
from pathlib import Path
p = Path("frontend/src/views/EmbedPersonal.vue"); s = p.read_text(encoding="utf-8")
old = '  scrollEl?.addEventListener("scroll", handleContainerScroll, { passive: true });'
new = '  window.addEventListener("scroll", handleContainerScroll, { passive: true });'
assert old in s, "定位失败"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
PY
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_embed_personal_contract.py -q 2>&1 | tail -2
cp .mc_bak frontend/src/views/EmbedPersonal.vue
```

Expected: `FAILED ...::test_scroll_listener_is_bound_to_container_not_window`

- [ ] **Step 3: 变异 C — 收起态去掉 aria-hidden**

```bash
cp frontend/src/views/EmbedPersonal.vue .mc_bak
.venv/bin/python - <<'PY'
from pathlib import Path
p = Path("frontend/src/views/EmbedPersonal.vue"); s = p.read_text(encoding="utf-8")
old = """      :aria-hidden="backFabHidden ? 'true' : undefined"
"""
assert old in s, "定位失败"
p.write_text(s.replace(old, "", 1), encoding="utf-8")
PY
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_embed_personal_contract.py -q 2>&1 | tail -2
cp .mc_bak frontend/src/views/EmbedPersonal.vue
```

Expected: `FAILED ...::test_hidden_state_is_inert_and_accessible`

- [ ] **Step 4: 变异 D — 去掉顶部保护**

```bash
cp frontend/src/views/EmbedPersonal.vue .mc_bak
.venv/bin/python - <<'PY'
from pathlib import Path
p = Path("frontend/src/views/EmbedPersonal.vue"); s = p.read_text(encoding="utf-8")
old = "if (delta > 0 && top > SCROLL_TOP_GUARD_PX) {"
new = "if (delta > 0) {"
assert old in s, "定位失败"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
PY
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_embed_personal_contract.py -q 2>&1 | tail -2
cp .mc_bak frontend/src/views/EmbedPersonal.vue
```

Expected: `FAILED ...::test_scroll_jitter_threshold_and_top_guard_exist`
（该常量仍在文件里定义，但已不再被 `handleContainerScroll` 使用，断言据此失败）

- [ ] **Step 5: 变异 E — 去掉抖动阈值**

```bash
cp frontend/src/views/EmbedPersonal.vue .mc_bak
.venv/bin/python - <<'PY'
from pathlib import Path
p = Path("frontend/src/views/EmbedPersonal.vue"); s = p.read_text(encoding="utf-8")
old = "  if (Math.abs(delta) < SCROLL_JITTER_PX) return;"
assert old in s, "定位失败"
p.write_text(s.replace(old, "", 1), encoding="utf-8")
PY
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_embed_personal_contract.py -q 2>&1 | tail -2
cp .mc_bak frontend/src/views/EmbedPersonal.vue
```

Expected: `FAILED ...::test_scroll_jitter_threshold_and_top_guard_exist`

- [ ] **Step 6: 每次变异后校验文件完整恢复**

```bash
shasum -a 256 frontend/src/views/EmbedPersonal.vue
```

与变异前记录的值比对，必须一致。全部变异做完后删除 `.mc_bak`。

- [ ] **Step 7: 跑全量前端契约套件**

Run:
```bash
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/ -q
```

Expected: **2096 passed, 1 skipped**（基线 2088 + 新增 8）

- [ ] **Step 8: 更新 `tests/CHECKLIST.md` 并提交（先问用户）**

按既有表格格式新增一行，记录：用户诉求原文、方案对比与选择、兜底的理由、
四条约束（容器监听 / 方向感知 / 兜底 / 双重不可用态）、变异验证项、套件数字。

```bash
git add tests/CHECKLIST.md
git commit -m "docs(checklist): 记录 EmbedPersonal 返回浮标方向感知收起"
```

---

## 已知缺口（实现完成后如实汇报）

- **未做真机验证**：`scroll` 事件在微信小程序 web-view 的沙箱内是否正常派发、
  `passive: true` 是否被支持，均无法用静态断言覆盖。需用户在实际 web-view 中
  滚动页面确认浮标确实会收起与恢复。
- **未验证的交互细节**：容器是否还有别的滚动来源（例如内部某个区域自身滚动）
  会影响「顶部保护」的判定。当前实现按 `scrollEl.scrollTop` 判断，若
  `PersonalCenter` 内部另有滚动容器，则本逻辑对它无效。

---

## 追加任务（同日）：触摸拖动，位置不持久化

**起因：** 用户看到实机效果后补充（原文）：「还是需要能支持拖动，但是不需要持久化记忆，
因为有时候会挡住我后面的按钮，我要手动拖开」。设计文档已同步追加「后续修订」一节。

**Files:**
- Modify: `frontend/src/views/EmbedPersonal.vue`
- Modify: `tests/frontend/test_embed_personal_contract.py`

### Task 5: 拖动（已按 TDD 完成）

- [x] **Step 1: 先写 6 条断言**，运行得 `5 failed / 19 passed`
      （`test_drag_position_is_not_persisted` 是反向断言，实现前天然通过，属预期）
- [x] **Step 2: 模板** —— 加 `ref="backFabRef"`、`:style` 绑 `fabPos`、
      `:class` 里用 `fabPos ? '' : 'bottom-4 right-4'` 保留默认位置、
      绑定 `touchstart.passive` / `touchmove` / `touchend` / `touchcancel`；
      同时把 `transition-all` 改为 `transition-opacity`（位置不走动画，拖动才跟手）
- [x] **Step 3: 脚本** —— 三个常量（`FAB_DRAG_THRESHOLD_PX=8`、
      `FAB_VIEWPORT_MARGIN_PX=8`、`FAB_CLICK_SUPPRESS_MS=300`）、
      `fabPos`/`backFabRef` 两个 ref、`clampToViewport`、
      `handleFabTouchStart/Move/End`，以及给 `goBackToChat` 加抑制窗口判断
- [x] **Step 4: 运行得 `24 passed`**
- [x] **Step 5: 类型门禁 `79` 条 = 基线，`EmbedPersonal.vue` 零命中**
- [x] **Step 6: 变异验证 8 项全部精确命中**（含专门证明反向断言有效的变异 B）
- [x] **Step 7: 全量套件 `2102 passed / 1 skipped / 0 failed`**
- [x] **Step 8: 更新 `tests/CHECKLIST.md`**（未执行 `git commit`，按项目规范由用户决定）

### 过程中修正的一处过弱断言

`test_dragged_position_switches_to_absolute_coordinates` 首版只断言「标签里含 `fabPos`」，
而 `:class` 里也有 `fabPos`，导致删掉 `:style` 后仍然全绿（变异 F 首轮**没有**失败）。
已改为断言 `:style` 与 `left`/`top`，重跑变异 F 才精确失败。
