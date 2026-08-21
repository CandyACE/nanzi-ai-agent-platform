# 上下文使用浮标 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将聊天输入框内的上下文使用进度条改为输入框右上角的低干扰浮标，并在展开详情中同时显示 token 数值、百分比占比和当前 sandbox 策略。

**Architecture:** 保留现有 `useContextUsage`、API 和上下文阈值计算，只调整 `ChatInput.vue` 的展示层。浮标显示当前估算值和窗口上限，点击默认向上展开轻量详情面板；组件根据视口剩余空间在向上和向下之间翻转；现有 context-usage 接口在同一认证上下文中读取 `sandbox_policy` 并返回，避免前端调用需要系统配置权限的管理接口；无有效窗口数据时不渲染任何占位 UI。

**Tech Stack:** Vue 3 + TypeScript + Tailwind CSS 3 + pytest 前端契约测试。

---

### Task 1: 定义浮标展示契约

**Files:**
- Modify: `tests/frontend/test_chat_context_usage_contract.py`
- Modify: `frontend/src/components/embed/ChatInput.vue`

- [x] **Step 1: 写失败测试**

在现有契约测试中要求 `ChatInput.vue`：

```python
assert 'data-testid="context-usage-indicator"' in chat_input
assert 'context-usage-details' in chat_input
assert 'data-testid="context-usage-bar"' not in chat_input[chat_input.index('<!-- Input Box -->'):]
```

测试同时保留 composable、API 路径和两个聊天页面的已有断言，确保本次只改变布局，不删除数据刷新链路。

- [x] **Step 2: 运行测试确认失败**

运行：

```bash
venv/bin/python -m pytest tests/frontend/test_chat_context_usage_contract.py --confcutdir=tests/frontend -q
```

预期：因当前模板仍包含输入框内的 `上下文使用` 文案且没有浮标 test id，测试失败。

### Task 2: 实现右上角浅浮标与详情面板

**Files:**
- Modify: `frontend/src/components/embed/ChatInput.vue`

- [x] **Step 1: 添加最小交互状态**

在 `script setup` 中增加 `showContextUsageDetails = ref(false)`，并用现有 `contextUsagePercent`、`contextUsageTone` 和 token 格式化函数计算浮标文案与颜色。`contextUsageTone` 为三种状态补充具体的 `badge` class：正常使用 `border-emerald-200/70 bg-emerald-50/70 text-emerald-600 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-400`，接近上限使用对应的 amber class，超限使用对应的 red class。浮标只在 `contextUsage?.physical_window` 有效时显示。

- [x] **Step 2: 替换输入框内进度条**

删除当前输入框内部的大型三行上下文进度区域，在 `<!-- Input Box -->` 容器内靠右上角加入一个原生 `button`：

```vue
<button
  v-if="contextUsage && contextUsage.physical_window"
  type="button"
  data-testid="context-usage-indicator"
  class="absolute right-2 top-2 z-20 inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] font-medium leading-none transition-colors"
  :class="contextUsageTone.badge"
  :aria-expanded="showContextUsageDetails"
  aria-controls="context-usage-details"
  :aria-label="`上下文使用 ${formatContextTokens(contextUsage.estimated_current_tokens)} / ${formatContextTokens(contextUsage.physical_window)}`"
  @click="showContextUsageDetails = !showContextUsageDetails"
>
  <span aria-hidden="true" class="h-1.5 w-1.5 rounded-full bg-current" />
  <span>{{ formatContextTokens(contextUsage.estimated_current_tokens) }}</span>
  <span class="font-mono tabular-nums opacity-70">/ {{ formatContextTokens(contextUsage.physical_window) }}</span>
</button>
```

按钮使用低对比度背景和边框；正常、接近请求输入上限、超限分别沿用绿色、黄色、红色语义；浮标出现时文本框使用 `pr-24` 预留约 96px 空间，避免窄屏长占位文本被覆盖，不影响底部模型选择器。

- [x] **Step 3: 添加点击详情面板**

在浮标上方右对齐渲染 `data-testid="context-usage-details"` 的绝对定位面板，仅在 `showContextUsageDetails` 为真时显示；若上方空间不足，则通过 `contextUsageDetailsPlacement` 自动翻转到浮标下方。内容显示当前值、窗口上限和 `contextUsagePercentLabel`（例如 `75%`），并保留历史截断线、请求输入上限与进度条。面板使用 `role="dialog"`、明确标题和 `aria-live="polite"`，不改变任何上下文数据：

```vue
<div
  v-if="showContextUsageDetails"
  id="context-usage-details"
  data-testid="context-usage-details"
  role="dialog"
  aria-label="上下文使用详情"
  aria-live="polite"
                  class="absolute right-0 z-40 w-60 max-w-[calc(100vw-2rem)] rounded-xl border border-gray-200 bg-white/95 p-3 text-[10px] shadow-xl dark:border-gray-700 dark:bg-gray-800/95"
                  :class="contextUsageDetailsPlacement === 'above'
                    ? 'bottom-[calc(100%+0.5rem)]'
                    : 'top-[calc(100%+0.5rem)]'"
>
  <div class="flex items-center justify-between gap-2 text-gray-500 dark:text-gray-400">
    <span>上下文使用</span>
    <span class="flex items-center gap-1.5 font-mono tabular-nums" :class="contextUsageTone.text">
      <span>
        {{ formatContextTokens(contextUsage.estimated_current_tokens) }} /
        {{ formatContextTokens(contextUsage.physical_window) }}
      </span>
      <span class="opacity-75">· {{ contextUsagePercentLabel }}</span>
    </span>
  </div>
  <div class="mt-2 h-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
    <div class="h-full rounded-full transition-all duration-300" :class="contextUsageTone.track" :style="{ width: `${contextUsagePercent}%` }" />
  </div>
  <div class="mt-2 flex items-center justify-between gap-2 text-gray-400 dark:text-gray-500">
    <span>历史截断线 {{ formatContextTokens(contextUsage.history_budget) }}</span>
    <span>请求输入上限 {{ formatContextTokens(contextUsage.request_input_budget) }}</span>
  </div>
</div>
```

- [x] **Step 4: 处理关闭与生命周期**

复用组件已有的 `onMounted` / `onUnmounted` 生命周期，在组件卸载时将详情状态复位；点击浮标以外的现有菜单关闭逻辑不得被改动。若当前文件已有统一的 document 点击监听，沿用该监听关闭详情，避免新增重复全局监听。详情打开后在窗口 resize/scroll 时重新计算上下空间，避免面板被视口裁切。

### Task 3: 回归验证

**Files:**
- Test: `tests/frontend/test_chat_context_usage_contract.py`
- Test: `frontend/src/components/embed/ChatInput.vue`

- [x] **Step 1: 运行聚焦契约测试**

运行：

```bash
venv/bin/python -m pytest tests/frontend/test_chat_context_usage_contract.py --confcutdir=tests/frontend -q
```

预期：通过，且仍确认 `EmbedChat.vue` 与 `AgentDebug.vue` 都传入 `contextUsage`。

- [x] **Step 2: 运行前端类型检查**

运行：

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：退出码为 0。

- [x] **Step 3: 检查差异与边界**

运行：

```bash
git diff --check -- frontend/src/components/embed/ChatInput.vue tests/frontend/test_chat_context_usage_contract.py
```

已完成静态检查；手动页面检查仍需用户启动前端后确认：有效上下文显示浮标；无 `physical_window` 时完全隐藏；正常/接近上限/超限颜色正确；点击浮标默认向上展开、空间不足时向下翻转；点击浮标可展开和收起详情；窄屏不覆盖输入占位和底部操作区。

### Task 4: 返回并展示当前 sandbox 策略

**Files:**
- Modify: `app/api/v1/endpoints/chat.py`
- Modify: `frontend/src/composables/useContextUsage.ts`
- Modify: `frontend/src/components/embed/ChatInput.vue`
- Test: `tests/api/v1/test_chat_context_usage.py`
- Test: `tests/frontend/test_chat_context_usage_contract.py`

- [x] **Step 1: 写失败测试**

后端契约要求上下文接口从 `ConfigService.get("sandbox_policy", "local")` 读取并在响应中返回 `sandbox_policy`；前端契约要求 `ContextUsage` 接口和详情面板包含 `sandbox_policy`、`sandboxPolicyLabel` 与「Sandbox 策略」文案。

- [x] **Step 2: 运行测试确认失败**

运行：

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/api/v1/test_chat_context_usage.py -q
venv/bin/python -m pytest tests/frontend/test_chat_context_usage_contract.py --confcutdir=tests/frontend -q
```

预期：因接口尚未返回策略字段且前端尚未渲染策略行而失败。

- [x] **Step 3: 实现后端字段**

在现有 context-usage endpoint 中读取系统配置；读取异常时记录 warning 并返回 `null`，不能让上下文使用接口整体失败：

```python
try:
    sandbox_policy = (await ConfigService.get("sandbox_policy", "local") or "local").strip().lower()
except Exception as exc:
    logger.warning("读取 sandbox_policy 失败: %s", exc)
    sandbox_policy = None
return StandardResponse(data={**usage, "sandbox_policy": sandbox_policy})
```

- [x] **Step 4: 实现前端展示**

给 `ContextUsage` 增加可选 `sandbox_policy` 字段，在 `ChatInput.vue` 中将 `local`、`docker`、`e2b`、`ssh` 映射为带友好说明的标签，并在详情面板底部显示「Sandbox 策略：当前策略标签」。配置字段为空时隐藏该行，不显示猜测值。

- [x] **Step 5: 运行回归验证**

已运行后端 context-usage 测试、前端契约测试、`npx vue-tsc --noEmit` 和 `git diff --check`；手动确认策略值显示与系统配置一致、读取失败时上下文面板仍可正常展开，仍需用户启动前端后完成。
