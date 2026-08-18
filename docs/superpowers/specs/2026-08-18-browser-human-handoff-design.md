# 浏览器人工接管与刷新控制设计

## 目标

让用户在右侧服务端浏览器中开始点击、拖拽、输入或滚轮操作后，当前浏览器会话明确进入“人工接管”状态：AI 不再继续调用浏览器点击/填充，截图刷新不会打断一次正在进行的人工操作，验证码由人工完成，并且用户可以显式交还给 AI。

本次不改造多标签页、不引入实时视频流，也不尝试让 AI 破解验证码。

## 现状与边界

当前调用链为：

`BrowserPanel.vue` → Viewer WebSocket → `browser_runtime.manual_input()` → `BrowserWorker.manual_input()` → Playwright。

AI 调用链为：

`browser_click/browser_fill` → `BrowserRuntime.click/fill()` → `BrowserWorker.click/fill()`。

`BrowserRuntime` 已按 session 使用 `asyncio.Lock` 串行化调用，但目前没有控制权状态，所以串行并不等于“人工接管后 AI 停止”。

## 设计

### 1. 会话控制权

在 `BrowserRuntime` 内维护进程内、按 session 隔离的人工控制状态：

- `owner`: `ai` 或 `human`
- `reason`: `click`、`drag`、`input`、`scroll` 或 `captcha`
- `updated_at`

首次人工事件 `mouse_click`、`mouse_down`、`key`、`text`、`scroll` 或 `mouse_up` 前，Runtime 在同一 session lock 内将 owner 设置为 `human`。

当 owner 为 `human` 时，`BrowserRuntime.click()` 和 `BrowserRuntime.fill()` 在控制权事件上等待，不执行 Playwright 动作；用户点击“交还 AI”后等待中的 AI 工具调用继续执行。这样不会把一次人工接管误报成工具失败，也不会让模型在错误后继续尝试操作。

Viewer 发送 `release_control` 后，Runtime 清除人工控制状态并广播 `control_state(owner=ai)`。Viewer 断开时释放本次人工控制，避免关闭面板后会话永久锁死。Runtime shutdown 同时清理控制状态。

### 2. 刷新时序

前端刷新分为两种状态：

- `autoRefreshPaused`: 用户点击“暂停刷新”后的持久暂停。
- `interactionInProgress`: 鼠标按下/拖拽/人工输入发送期间的短暂暂停。

只有真实操作开始时才设置 `interactionInProgress`，不会因为鼠标悬停或普通移动触发。操作结束后：

1. 清除 `interactionInProgress`；
2. 请求一次最新快照；
3. 在人工控制权仍归用户时不恢复轮询，直到用户点击“交还 AI”。

验证码状态下保持用户主动暂停，不自动恢复轮询；完成验证后仍由用户点击“交还 AI”或手动刷新确认页面状态。

### 3. WebSocket 事件契约

服务端新增以下 JSON 消息：

```json
{"type":"control_state","owner":"human","reason":"drag","captcha":false}
{"type":"control_state","owner":"ai","reason":null,"captcha":false}
{"type":"captcha","detected":true,"reason":"页面要求人工完成安全验证"}
```

现有 `focus`、`snapshot` 和 `error` 消息保持兼容。

Viewer 接收 `release_control`；人工事件成功后先发送控制权状态，再按现有逻辑发送快照。`mouse_move` 不单独触发快照，也不重复发送控制权状态。

### 4. 输入增强

- 普通文本、中文文本和粘贴内容统一通过 `text` 事件发送，Worker 优先使用 Playwright 的文本插入能力，避免中文输入法依赖逐字键盘事件。
- `key` 事件继续保留，用于 Enter、Tab、Escape、方向键和验证码键盘操作。
- 前端人工输入弹框在远程文本输入焦点确认后自动聚焦；发送后保持弹框打开，支持连续输入。
- 输入框识别覆盖 `input`、`textarea`、`contenteditable`、`role=textbox`；跨 iframe 只在 Playwright 能确认当前 frame 焦点时报告为可输入，不向前端暴露跨域页面内容。

### 5. 验证码人工处理

Worker 在快照阶段使用低风险、可解释的页面信号识别常见人工验证状态：验证码/安全验证文本、滑块容器和挑战 iframe。识别只用于提示和暂停刷新，不用于自动计算滑块距离或绕过验证。

命中后：

- 服务端发送 `captcha` 消息；
- Runtime 将控制权设为 `human`；
- 前端显示“检测到安全验证，请人工完成”，并暂停自动刷新；
- 用户仍可点击、拖拽、输入和按键；
- 用户完成验证后点击“恢复自动刷新”或“交还 AI”，继续后续流程。

检测失败不阻断人工操作，也不把普通“验证”业务文案直接判定为验证码。

## 错误处理

- AI 在人工接管期间调用 `browser_click`/`browser_fill` 会等待控制权释放，不执行 Playwright 动作。
- 人工操作失败只返回 Viewer `error`，不自动释放人工控制权，避免验证码操作中途被 AI 抢回。
- WebSocket 重连时服务端重新发送当前控制状态；断开连接时释放控制权。
- 所有状态按 session 隔离，不新增数据库字段或迁移；当前 BrowserRuntime 要求会话粘滞到同一应用 Worker，符合现有架构约束。

## 测试范围

- Runtime：人工接管后阻断 AI click/fill、交还 AI 后恢复、shutdown 清理、不同 session 隔离。
- Worker：中文文本插入、键盘事件和验证码检测的正负样本。
- Viewer endpoint：控制权消息、释放事件、断开释放和验证码消息。
- Frontend contract：控制权状态、交还按钮、操作期刷新暂停、输入增强提示和验证码提示。
- 现有浏览器相关测试、Vue 类型检查和 `git diff --check` 全部通过。
