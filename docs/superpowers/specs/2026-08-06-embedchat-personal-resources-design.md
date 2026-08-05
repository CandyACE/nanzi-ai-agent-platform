# EmbedChat 初始页「我的资源」设计

## 背景

部分宿主系统直接嵌入 EmbedChat，用户无法进入「我的工作台」。工作台上的个人资源统计卡（记忆 / Token / 数据门户 / 技能 / MCP / 任务）对这类用户不可见。需要在 EmbedChat 空会话初始页展示同款入口，并在 Embed 内完成查看与管理，避免依赖 Dashboard 路由。

## 目标

1. 在 EmbedChat 空会话欢迎页展示与工作台一致的 6 张「我的资源」统计卡。
2. 保留现有能力入口 3 卡与推荐提示词。
3. 点击统计卡后，在 Embed 内打开「我的资源」居中弹层（形态对齐右上角「对话设置」），切换到对应 Tab。
4. Tab 内容复用个人中心同一套面板，避免两套业务 UI；完整操作能力（非只读概览）。
5. 统计数据复用 `GET /api/portal/workbench/home` 的 `personal_resources`，不新增聚合 API。

## 非目标

- 不把工作台其它区块（待处理、最近会话、最近产出、常用助手等）搬进 Embed 初始页。
- 不在 Embed 内 iframe 整页 `/dashboard/personal`。
- 不改变工作台页面自身的信息架构与路由（仅抽离可共享组件）。
- 不新增后端聚合接口；各 Tab 继续使用个人中心既有 API。

## 决策摘要

| 项 | 选择 |
|----|------|
| 初始页内容 | 统计 6 卡 + 保留能力 3 卡 |
| 统计卡布局 | 问候语下方整排 6 卡（宽屏 6 列；`sm` 3×2；更窄 2×3） |
| 点击行为 | Embed 内打开「我的资源」弹层 |
| 弹层形态 | 统一弹层 + Tab（类 `ChatSettings`） |
| Tab 深度 | 完整操作；复用个人中心面板 |
| 复用策略 | 组合现有面板 + 抽出记忆面板 + 解开数据/任务的 dashboard 硬跳转 |

## 信息架构

### 空会话初始页（自上而下）

1. 问候语（现有）
2. 「我的资源」统计条（新增）
3. 能力入口 3 卡（现有）
4. 推荐提示词（现有）

有消息后初始页消失，统计条随之隐藏（仅空会话展示）。弹层可在有会话时仍由其它入口打开（本轮仅要求初始卡可打开；不强制新增顶栏入口）。

### 「我的资源」弹层

- 标题：我的资源
- Tab 顺序与统计卡一致：`memory` / `tokens` / `data` / `skills` / `mcp` / `tasks`
- 打开时 `activeTab` 设为被点击卡片的 `tab`
- 宽度约 `max-w-5xl`，高度约 `80vh`，内容区内部滚动
- `activeTab` 为弹层本地状态，**不**写入 `/embed/...` 的 `route.query`

## 组件设计

### 1. 统计卡外壳（共享）

调整 `WorkbenchPersonalResources`（或抽出等价 presentational 组件）：

- Props：`items`（来自 workbench home）、可选 `loading` / `error`
- 事件：`select(tab: PersonalResourceTab)`，**不再**在组件内写死 `router.push('/dashboard/personal')`
- 工作台父组件继续 `router.push({ path: '/dashboard/personal', query: { tab } })`
- Embed 父组件改为打开 `PersonalResourcesModal`

视觉：沿用现有 `rounded-2xl`、label / value / unit、hover 蓝调；Embed 需兼容 dark mode（与 WelcomeDashboard 一致）。

### 2. `PersonalResourcesModal`（Embed 新建）

- 交互参考 `ChatSettings`：`v-model:visible`、遮罩、居中卡片、关闭按钮
- Tab 栏 + 内容区；重 Tab 使用 `defineAsyncComponent` 懒加载
- z-index 与 `ChatSettings` 同级；子面板内 `fixed` 抽屉必须高于本弹层，或改为弹层内定位，避免遮挡

### 3. Tab 面板复用

| Tab | 组件 | 改动 |
|-----|------|------|
| memory | 新建 `PersonalMemoryPanel` | 从 `PersonalCenter.vue` 抽出；PersonalCenter 与弹层共用 |
| tokens | `PersonalTokenUsage` | 基本不动；注意弹层内图表容器高度 |
| data | `DataPortalHome` + `embedded` | 禁用对当前路由的 `router.replace` 同步；`/dashboard/chat` 硬跳改为 emit / 回调，由 EmbedChat 接到现有数据门户抽屉或会话动作 |
| skills | `SkillsManagement` + `personal-only` | 基本不动；注意嵌套 overlay z-index |
| mcp | `McpManagement` + `personal-only` | 基本不动 |
| tasks | `TaskCenter` + `personal-only` | 去掉 `/dashboard/personal`、`/dashboard/chat` 硬跳；支持 `initialView` / `initialTaskId` props，避免依赖 `route.query` |

**禁止**直接挂载完整 `PersonalCenter.vue`（带 Dashboard 壳与 query 同步）。

### 5. Dashboard 导航在 Embed 中的映射

`DataPortalHome` / `TaskCenter` 在弹层内不得 `router.push('/dashboard/...')`。统一改为 emit，由 `EmbedChat` 处理：

| 原行为 | Embed 处理 |
|--------|------------|
| 打开报表 / 数据门户 / 带 `dataset_portal` 的会话 | **先关闭** `PersonalResourcesModal`，再调用现有 `openPortalDrawer` / `OPEN_DATA_PORTAL_FULL` / 会话跳转 handler（与能力卡「自然语言查数」同源） |
| 打开对话（`conversation_id` / 追问） | **先关闭**弹层，再切到对应会话或写入输入框发送（复用现有 resume / quick-question 路径） |
| 打开通知设置（`/dashboard/personal?tab=notifications`） | 弹层 Tab **不含** notifications。Embed 内：**隐藏**该入口，或点击后 toast「请在完整平台个人中心打开通知设置」——本轮不实现 Embed 通知设置页 |
| 其它仅个人中心内的 tab 跳转 | 若目标 Tab 在「我的资源」六者之内 → 弹层内切 Tab；否则同上 toast / 隐藏 |

叠层约定：一旦需要打开 Embed 已有的全屏/侧栏抽屉（数据门户、工作空间、记忆浏览器等），必须先关「我的资源」弹层，避免与 `ChatSettings` 同级 z-index 互相遮挡。

### 4. WelcomeDashboard 接入

在问候语与能力卡之间插入统计条：

- 数据：EmbedChat（或 composable）在鉴权成功后调用 `useWorkbenchHome` / `GET /api/portal/workbench/home`，传入 Embed 鉴权头
- 事件：`open-personal-resources(tab)` → EmbedChat 设置 `showPersonalResources = true` 与 `personalResourcesTab`

## 数据流

```text
Auth OK
  → GET /api/portal/workbench/home
  → personal_resources → 统计卡 items

点击卡片(tab)
  → PersonalResourcesModal.visible = true
  → activeTab = tab
  → 懒加载对应面板
  → 面板使用个人中心既有 API（axios / embed 同源凭证）
```

失败态：

- home 接口失败或尚未返回：仍渲染 6 张卡壳，label / unit / tab 使用与后端 `PERSONAL_RESOURCE_DEFS` 对齐的**前端静态定义**（与工作台 defs 同源常量或共享一份），value 显示 `--`；仍可点击打开弹层
- 单 Tab 加载失败：仅该 Tab 错误态
- Embed 无权限：沿用现有全屏无权限，不单独画半残统计条

## 响应式

| 断点 | 统计卡网格 |
|------|------------|
| `xl` / 默认宽屏 | `grid-cols-6` |
| `sm`–`lg` | `grid-cols-3`（两行） |
| 更窄 | `grid-cols-2`（三行） |

弹层在窄屏接近全宽，Tab 横向可滚动。

## 测试要点

- WelcomeDashboard：空会话渲染 6 卡；有消息后不渲染
- 点击某卡打开弹层且 `activeTab` 正确
- PersonalCenter 记忆 Tab 抽出后行为回归（列表 / 子视图仍可用）
- DataPortalHome / TaskCenter 在 `embedded` / 弹层模式下不再跳转 `/dashboard/*`
- 工作台统计卡点击仍进入 `/dashboard/personal?tab=…`
- Embed 鉴权头下 `workbench/home` 可成功拉取（契约或集成测按现有前端测试习惯）
- dark mode 下统计卡与弹层可读

## 实现分期建议

1. **共享外壳 + Welcome 展示**：统计卡可点，弹层壳 + Tab 切换；Tab 内容可先占位或只接 tokens/mcp（最快可见）
2. **抽出 PersonalMemoryPanel**，PersonalCenter 改用共享组件
3. **挂载 skills / tokens / mcp**（改动最小）
4. **改造 data / tasks 导航注入**，完成完整操作闭环
5. **z-index / 懒加载 / 契约测试**收尾

分期不影响本设计目标；计划阶段可按依赖拆 PR。
