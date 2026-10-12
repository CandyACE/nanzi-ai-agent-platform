# 移动端 AI 消息操作栏与操作抽屉

**日期：** 2026-10-12
**需求（用户原话）：** 「移动端下呢」→「你准备移动端下如何优化」→ 看完三版排布对比后选定「A · 一行放核心 + 数据图标带徽标」

---

## 1. 现状与问题

移动端（`windowWidth < 640`，`EmbedChat.vue:6969-6972`，与 Tailwind `sm` 断点一致）与桌面共用同一套 AI 消息操作栏模板，靠 `sm:` 前缀与 `isMobile` 分流。

**证据链（改动前的真实行为）：**

| 环节 | 代码 | 行为 |
| --- | --- | --- |
| 操作栏容器 | `EmbedChat.vue:1018-1020` | `flex-nowrap items-center space-x-2 overflow-x-auto sm:overflow-x-visible` —— 窄屏只能横向滚动 |
| 数据 / 文件入口 | `EmbedChat.vue:1139`（`hidden sm:block`）+ `MessageActionMenus.vue:187-201` | 移动端没有独立入口，必须先点「⋯ 更多」，徽标计数也只能在浮层里看到 |
| 用量 | `EmbedChat.vue:1155-1166`（`flex sm:hidden` 图标）/ `:1167-1179`（`hidden sm:flex` 文字） | 移动端是图标按钮，占一个行内位置 |
| 继续分析 | `EmbedChat.vue:1190-1194` + `MessageContinueAnalysis.vue:10-26, 29-48` | 移动端只有图标（`hidden sm:inline` 藏了文字），点开是全屏遮罩 + 底部抽屉（`z-[260]`） |
| ChatBI 继续分析 | `EmbedChat.vue:1182-1189` + `ChatBIContinueAnalysis.vue:13, 29` | 同上，另一份独立实现的同款抽屉 |
| 「⋯ 更多」 | `EmbedChat.vue:1195-1216` + `MessageActionMenus.vue:187-208` | 移动端仍是 `Teleport to body` 的小浮层（宽 `min(192, 视口-16)`） |

**由此产生的四个问题：**

1. **数据 / 文件入口藏得深**：手机上要先点「更多」，且看不到「数据 N」「文件 N」计数，无从判断本会话到底有没有产出；
2. **窄屏横向滚动**：行内元素（时间戳 + 5 个图标 + 用量 + 继续分析 + 更多）在 375px 上已接近上限，文案变长或窄机型会滑出可视区；
3. **交互形态不统一**：同一行里「继续分析」是底部抽屉、「更多」是贴按钮浮层，手机上两种手感；
4. **继续分析没有文字**：`hidden sm:inline` 让它在移动端只剩一个 ✨ 图标，识别成本高。

## 2. 目标与非目标

**目标：**

1. 移动端一行内**可见**「数据 / 文件」入口，并带计数徽标；
2. 移动端一行**常态不横向滚动**（保留滚动仅作极端兜底）；
3. 「更多」改为底部抽屉，与「继续分析」形态统一；
4. 「继续分析」在移动端带上文字说明（不再只有图标）；
5. 桌面端（≥640px）**行为与样式零改动**；后端零改动。

**明确不做：**

- 不改桌面端任何入口、样式、浮层交互；
- 不新增后端接口或字段：抽屉所有内容都取 `EmbedChat` 现有派生值；
- 不改消息内容区（执行时间线、思考头、洞察面板等）；
- 不做抽屉拖拽手势（不实现 drag-to-dismiss，只保留拖拽条外观）；
- 不动消息正文里的其它操作（复制、赞踩、重新生成的行为与条件不变）。

## 3. 设计决策（2026-10-12 与用户逐项确认）

| 编号 | 决策点 | 结论 |
| --- | --- | --- |
| D1 | 操作栏排布 | **方案 A**：一行核心（复制 / 重新生成 / 赞 / 踩）+「▤ 数据」徽标图标 +「⋯ 更多」；用量与继续分析移入抽屉 |
| D2 | 抽屉拆分 | **一个抽屉、四个分组**；`▤` 与 `⋯` 打开同一个抽屉，差别只是「数据 / 文件」组是否高亮 |
| D3 | 数据按钮空态 | 本会话没有数据 / 文件时 **`▤` 不出现**（手机上禁用按钮没有 hover 提示可解释原因） |
| D4 | 改动范围 | **只改移动端**（`<640px`），桌面端不动 |
| D5 | 实现方式 | **抽公共底部抽屉壳** `MobileActionSheet.vue`，供 4 处抽屉复用（含现有两个） |

## 4. 交互设计

### 4.1 移动端操作栏（`<640px`）

从左到右，唯一一行：

| 位置 | 元素 | 显示条件 | 说明 |
| --- | --- | --- | --- |
| 1 | 时间戳 | 有 `msg.timestamp` | 不变 |
| 2 | 复制（⧉） | 始终 | 不变 |
| 3 | 重新生成（↻） | `msg === lastAgentMessage && !isProcessing` | 不变 |
| 4 | 赞（👍） | `!hideEmbedLikeDislike` | 不变 |
| 5 | 踩（👎） | `!hideEmbedLikeDislike` | 不变 |
| 6 | **▤ 数据** | `hasConversationDataFile`（会话级有数据 / 文件） | **新增**：图标 + 计数徽标，点击打开抽屉并高亮数据组 |
| 7 | ⋯ 更多 | `hasMobileSheetContent`：抽屉内至少一组非空（见 4.2.4） | 移动端**改为打开抽屉**（桌面仍走 `MessageActionMenus` 浮层） |

- 行内间距沿用现有 `space-x-2`，按钮维持 `h-7 w-7`；`▤` 与「⋯ 更多」为带文字 / 徽标的小胶囊，与桌面「数据 / 文件」按钮同色系（`text-gray-500`，徽标 `bg-primary`）。
- 容器**保留** `overflow-x-auto sm:overflow-x-visible` 作为兜底（超窄屏或文案膨胀时不至于被裁切），但常态应无滚动条。
- **移除**：移动端的用量图标按钮（`EmbedChat.vue:1155-1166`）、继续分析图标（`:1190-1194`）、ChatBI 继续分析（`:1182-1189`）——三者的能力都进入抽屉。

### 4.2 操作抽屉（一个抽屉，四组）

#### 4.2.1 内容与顺序

| 组 | 标题右侧 | 项 | 每项右侧 |
| --- | --- | --- | --- |
| 数据 / 文件 | `数据 {reusableCount} · 文件 {artifactCount}` | ▤ 查看可复用结果、▣ 查看文件产物、↓ 导出数据（Excel） | `{conversationReusableCount} 条`、`{conversationArtifactCount} 个`、— |
| 继续分析 | — | 通用智能体：4 个沉淀动作（见 5.3）；ChatBI 场景：`msg.chatbiInsight.actions` | — |
| 本次调用 | — | ▤ 查看调用详情、↗ 查看执行链路 | `{用量文本}`、— |
| 沉淀 | — | ☆ 添加固化报表 | — |

组的显示条件与桌面端完全一致（沿用 `MessageActionMenus` 现有判定），空组不渲染标题。

#### 4.2.2 打开与高亮

- **▤ 数据** → `openSheet('data')`：打开抽屉，把「数据 / 文件」组渲染为高亮态（浅色底 + 左侧 2px 主色竖条）；**高亮保持到抽屉关闭**（不做定时淡出，行为可测）。
- **⋯ 更多** → `openSheet(null)`：打开抽屉，无高亮，从顶部开始（数据组本来就在最上面）。
- 数据项只在数据组出现一次，不与其它组重复。

#### 4.2.3 关闭与可访问性

- 关闭方式：点遮罩、点底部「取消」、按 `Esc`。
- 抽屉 `role="dialog"`、`aria-modal="true"`、`aria-label="更多操作"`；打开时焦点移入抽屉，关闭后归还给触发按钮（`▤` 或 `⋯`）。
- 打开期间锁定背景滚动（记录并还原 `body.style.overflow`）。

#### 4.2.4 空态与层级

- 四组全空（无数据、无继续分析动作、无 token、无 `trace_id`、无固化报表权限）时，**`⋯ 更多` 按钮不显示**（对齐桌面现有 `hasMore` 语义）。
- 内容超出时抽屉内滚，上限 `70vh`；`z-index` 与现有两个抽屉一致取 `z-[260]`。
- 底部内边距 `pb-[max(1rem,env(safe-area-inset-bottom))]`，覆盖 iPhone 横条。
- 圆角仅上缘（`rounded-t-2xl`），顶部有 36×4 的拖拽条（纯装饰）。

## 5. 组件设计

### 5.1 `frontend/src/components/chat/MobileActionSheet.vue`（新增）

**职责**：只管「底部抽屉长什么样、怎么开关」，不含任何业务内容。

- Props：`open: boolean`、`title?: string`、`subtitle?: string`、`closeLabel?: string`（默认「取消」）。
- Emits：`close`。
- Slots：默认（内容区，内部 `overflow-y-auto max-h-[70vh]`）。
- 内部实现：`Teleport to body` → 全屏遮罩（`fixed inset-0 z-[260] bg-black/35 backdrop-blur-[1px]`，`@click.self` 关闭）→ 贴底容器（`rounded-t-2xl` + 拖拽条 + 标题行 + 内容 + 取消）。
- `watch(open)`：打开时锁 `body` 滚动并聚焦抽屉，关闭时还原滚动；`Esc` 监听在打开期间挂载。
- 依赖：仅 Vue。**不依赖** `isMobile`——由父级用 `sm:hidden` 之类的条件决定何时渲染。

### 5.2 `frontend/src/components/chat/MobileMessageActionsSheet.vue`（新增）

**职责**：消息操作抽屉的**内容**，四组 + 高亮逻辑 + 徽标计数。

- Props：`focus: 'data' | null`，以及各可见性与计数（与 `MessageActionMenus` 现有 props 对齐）：`hasConversationDataFile`、`reusableCount`、`artifactCount`、`conversationReusableCount`、`conversationArtifactCount`、`hasReusableResultEntry`、`hasArtifactEntry`、`canExport`、`hasTrace`、`hasTokenStats`、`tokenLabel`、`canSaveReport`、`chatbiActions`。
- Emits：`exportData`、`openReusableResults`、`openArtifacts`、`openTrace`、`openStats`、`saveReport`、`continueAnalysis(query)`。
- 内部：`computed` 出四个分组的渲染条件；`focus === 'data'` 时数据组加高亮 class。继续分析组：`chatbiActions` 非空时渲染 ChatBI 动作，否则渲染通用 4 个沉淀动作。

### 5.3 `frontend/src/components/chat/continueAnalysisActions.ts`（新增）

把 `MessageContinueAnalysis.vue:90-115` 的 `ContinueAction` 数组与 `actionIcon()` 映射抽成共享常量（`CONTINUE_ANALYSIS_ACTIONS`、`continueActionIcon()`），供该组件与抽屉共用。**理由**：这 4 段 prompt 文案很长，复制一份必然会漂移。

### 5.4 既有组件改造

| 文件 | 改动 |
| --- | --- |
| `MessageContinueAnalysis.vue` | 动作定义改为从 `continueAnalysisActions.ts` 引入；移动端抽屉改用 `MobileActionSheet` 承载（桌面浮层分支保持不变） |
| `ChatBIContinueAnalysis.vue` | 同上（移动端抽屉换壳，桌面浮层不动） |
| `EmbedChat.vue` | 见 5.5 |

### 5.5 `EmbedChat.vue` 改动清单

新增状态：`showMobileActions = ref(false)`、`mobileActionsFocus = ref<'data' | null>(null)`。

新增 computed：`hasMobileSheetContent` —— 数据组 / 继续分析组 / 本次调用组 / 沉淀组任一非空。它必须由 `EmbedChat` 自己算：移动端不再渲染 `MessageActionMenus`，无法复用其内部 `hasMore`。

| 改动 | 位置 | 说明 |
| --- | --- | --- |
| 新增 `▤ 数据` 按钮 | 操作栏内（`sm:hidden`） | 条件 `hasConversationDataFile`；点击 `openMobileActions('data')` |
| 新增移动端 `⋯ 更多` 按钮 | 操作栏内（`sm:hidden`） | 点击 `openMobileActions(null)`；由 `hasMobileSheetContent` 决定是否渲染 |
| 移除移动端用量图标按钮 | `:1155-1166` | 能力进抽屉「本次调用」 |
| 让继续分析仅桌面渲染 | `:1182-1194` | 移动端不再渲染（外层 `hidden sm:flex`），其能力改由抽屉「继续分析」组承载 |
| 让 `MessageActionMenus` 仅桌面渲染 | `:1195-1216` | 外层用 `hidden sm:flex` 包裹（CSS 层隔离而非 `v-if`，避免断点切换时 DOM 抖动）；移动端入口换成上面的 `⋯` 按钮 |
| 挂载抽屉 | 操作栏同级 | `<MobileActionSheet :open="showMobileActions" ...>` + `<MobileMessageActionsSheet :focus="mobileActionsFocus" ...>`，事件直接接现有 handler（`exportData` / `openReusableResults` / `openMessageArtifacts` / `openEmbedTrace` / `openModelCallStats` / `handleSaveReportFromMessage` / `handleQuickQuestion`） |
| 断点切换兜底 | `windowWidth` watcher | 跨过 640px 时 `showMobileActions.value = false` |

## 6. 数据流（零后端改动）

| 抽屉元素 | 来源 | 条件 |
| --- | --- | --- |
| `▤` 是否出现 / 数据组是否渲染 | `hasConversationDataFile` | 会话级标记 |
| 数据组标题徽标 | `currentMessageReusableCount(msg)`、`artifactCount(msg.trace_id)` | 与桌面徽标同源 |
| 查看可复用结果右侧数字 | `conversationReusableResultCount` | — |
| 查看文件产物右侧数字 | `conversationArtifactCount` | — |
| 导出数据（Excel） | `Boolean(msg.trace_id)` | 复用 `exportData(msg.trace_id, 'xlsx')` |
| 查看执行链路 | `Boolean(msg.trace_id)` | 复用 `openEmbedTrace` |
| 查看调用详情 + 用量文本 | `msg.prompt_tokens/completion_tokens/total_tokens`、`getMessageTokenAmount` | 复用 `openModelCallStats` |
| 添加固化报表 | `canSaveGoldenReportFromMessage(msg) && checkRole(msg,'agent') && !msg.isThinking` | 复用 `handleSaveReportFromMessage` |
| 继续分析（通用） | `isGeneralAgentMessage(msg) && !chatbiActions.length && !msg.isThinking && visibleStreamBody(msg)` | 选中后 `handleQuickQuestion(query, 'send', visibleStreamBody(msg))` |
| 继续分析（ChatBI） | `msg.chatbiInsight?.actions?.length` | 复用 `handleChatBIContinueSelect` |

## 7. 边界与错误处理

| 场景 | 处理 |
| --- | --- |
| 会话没有数据 / 文件 | `▤` 不渲染（D3）；若同时没有其它项，`⋯` 也不渲染 |
| 抽屉内某组为空 | 该组标题与内容都不渲染 |
| 内容超长（多组同时有内容） | 抽屉内容区 `overflow-y-auto` + `max-h-[70vh]` |
| resize 跨过 640px | 关闭抽屉，清空 `focus`，避免残影与状态悬空 |
| 深色模式 | 沿用现有 `dark:` token 类（`bg-white dark:bg-gray-900`、`border-gray-100 dark:border-gray-800` 等） |
| iPhone 底部安全区 | `pb-[max(1rem,env(safe-area-inset-bottom))]` |
| 打开时背景滚动 | 壳内锁定并在关闭时还原原值 |

## 8. 测试策略

1. **契约测试** `tests/frontend/test_mobile_actions_sheet_contract.py`（新增）：
   - `MobileActionSheet`：存在 `Teleport`、`role="dialog"`、`aria-modal`、`@click.self` 关闭、`z-[260]`、安全区类、打开时锁 `body` 滚动；
   - `MobileMessageActionsSheet`：四组锚点齐备、`focus === 'data'` 的高亮分支存在、空组条件存在；
   - `EmbedChat`：`▤` 按钮带 `sm:hidden` 且条件含 `hasConversationDataFile`；移动端用量图标按钮已移除；继续分析与 `MessageActionMenus` 在移动端不再渲染；`⋯` 移动端打开抽屉；存在跨断点关闭抽屉的 watcher；
   - `continueAnalysisActions.ts` 被两个消费方引用（防止文案再次复制）。
2. **行为测试** `tests/frontend/mobile_action_sheet_ssr.cjs`（新增）：真编译并 SSR `MobileActionSheet`，断言 `open=false` 时不渲染遮罩与内容、`open=true` 时渲染遮罩 + 标题 + 内容槽，且遮罩与「取消」都带关闭绑定（沿用现有 `timeline_tool_args_collapse.cjs` 的编译/渲染手法）。
3. **变异验证**：至少覆盖「`▤` 条件去掉」「用量按钮没删」「继续分析仍渲染在移动端」「壳不锁滚动」「高亮分支去掉」「跨断点不关抽屉」六项，要求全部被捕获且文件字节级还原。
4. **回归**：`pytest --confcutdir=tests/frontend tests/frontend` 全量 + `vue-tsc --noEmit`（前端类型检查）。
5. **CHECKLIST**：在 `tests/CHECKLIST.md` 追加一行（问题 / 根因 / 做法 / 测试 / 验收）。

## 9. 影响面

| 类型 | 文件 |
| --- | --- |
| 新增 | `frontend/src/components/chat/MobileActionSheet.vue`、`frontend/src/components/chat/MobileMessageActionsSheet.vue`、`frontend/src/components/chat/continueAnalysisActions.ts`、`tests/frontend/test_mobile_actions_sheet_contract.py`、`tests/frontend/mobile_action_sheet_ssr.cjs` |
| 修改 | `frontend/src/views/EmbedChat.vue`、`frontend/src/components/chat/MessageContinueAnalysis.vue`、`frontend/src/components/chatbi/ChatBIContinueAnalysis.vue`、`tests/CHECKLIST.md` |
| 不动 | 桌面端全部行为；后端；消息内容区组件 |

**风险与缓解：**

- *误伤桌面端*：所有改动都在 `sm:hidden` / `hidden sm:flex` 分支内，并用契约测试钉住桌面侧既有元素仍然存在；
- *两个既有抽屉换壳后回归*：换壳只替换「遮罩 + 贴底容器」的外层结构，props / emits / 桌面分支不动，行为测试覆盖壳的开关；
- *滚动锁副作用*：壳在 `onUnmounted` 与关闭时都还原 `body.style.overflow`，避免异常路径把页面锁死。

## 10. 手动验收清单（用户在 `./dev.sh` 后执行）

1. iPhone 宽度（≤390px）：AI 消息操作栏一行放得下、不出现横向滚动条；`▤` 图标出现在赞踩之后；
2. 有数据 / 文件的消息：`▤` 徽标数字与桌面「数据 / 文件」按钮一致；无数据时 `▤` 不出现；
3. 点 `▤`：底部抽屉弹出，「数据 / 文件」组高亮，三项可点（复用结果 / 文件产物 / 导出 Excel）；
4. 点 `⋯ 更多`：同一抽屉、无高亮、从顶部开始；继续分析四项在移动端带文字与说明；
5. 「查看调用详情」能看到用量弹窗、「查看执行链路」能打开链路抽屉、「添加固化报表」行为与桌面一致；
6. 点遮罩 / 取消 / Esc 都能关闭，关闭后页面滚动恢复正常；
7. 桌面端（≥640px）逐项对照：入口、浮层、样式与改动前完全一致。

## 11. 迭代记录

- 2026-10-12：初稿，基于三版排布对比（A/B/C）与 4 项决策（D1–D5）定稿。
