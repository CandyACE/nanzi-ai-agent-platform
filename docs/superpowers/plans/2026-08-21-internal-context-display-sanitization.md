# 内部上下文标记显示清洗实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 防止后端内部上下文标记泄漏到用户可见回答、复制内容和下一轮 assistant 历史，同时保留正常执行协议内容。

**Architecture:** 在 `frontend/src/utils/streamContentSanitize.ts` 增加统一的内部上下文块清洗器，处理完整标签、未闭合标签和纯文本内部前缀；实时 SSE、历史消息展示、复制和发送历史统一调用它。仅清洗平台已知内部标记，不清洗 `<sql_plan>`、`<sub_query>` 等执行协议标签。

**Tech Stack:** Vue 3 + TypeScript + 现有 Python/pytest 前端契约测试。

---

### Task 1: 定义内部标记清洗行为

**Files:**
- Modify: `frontend/src/utils/streamContentSanitize.ts`
- Create: `tests/frontend/test_internal_context_display_sanitization.py`

- [x] **Step 1: 写失败测试**

测试 `stripInternalContextBlocks` 必须移除 `<backend_tool_run_summary>`、`<backend_injected_attachments>`、`<system_injected_attachments>`、`SYSTEM_BLOCK_START/END`、`[早前对话摘录]`、`[上一轮可复用工具结果]` 和 `[本回复由智能体「…」生成]`，同时保留普通正文与 `<sql_plan>`。

- [x] **Step 2: 运行测试确认失败**

运行：`venv/bin/python -m pytest tests/frontend/test_internal_context_display_sanitization.py --confcutdir=tests/frontend -q`

预期：因清洗函数尚未导出而失败。

### Task 2: 实现共享清洗器

**Files:**
- Modify: `frontend/src/utils/streamContentSanitize.ts`

- [x] **Step 1: 实现最小清洗逻辑**

导出 `stripInternalContextBlocks(content: string): string`，先移除完整内部块；对只有开始标签而没有结束标签的尾部内容直接截断；再移除压缩/工具快照/智能体身份前缀及系统区块注释；最后规范多余空行。

- [x] **Step 2: 运行测试确认通过**

运行：`venv/bin/python -m pytest tests/frontend/test_internal_context_display_sanitization.py --confcutdir=tests/frontend -q`

预期：全部通过。

### Task 3: 接入聊天展示与历史发送路径

**Files:**
- Modify: `frontend/src/utils/streamContentSanitize.ts`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`

- [x] **Step 1: 实时流和历史正文统一清洗**

让 `sanitizeStreamContent` 调用共享清洗器；让 `visibleStreamBody` 对历史/当前 `msg.content` 使用同一清洗结果。

- [x] **Step 2: 防止清洗前文本进入复制和下一轮上下文**

复制按钮使用可见正文；`buildOutboundMessages` 对 assistant content 使用清洗后的正文，避免内部标签跨轮再次进入模型上下文。

- [x] **Step 3: 补齐 AgentDebug 入口**

AgentDebug 的流式正文和复制/展示路径复用同一清洗器，避免两个聊天界面行为不一致。

- [x] **Step 4: 运行回归验证**

运行：

```bash
venv/bin/python -m pytest tests/frontend/test_internal_context_display_sanitization.py tests/frontend/test_chat_model_call_stats_context_contract.py tests/frontend/test_chat_surface_extraction_contract.py --confcutdir=tests/frontend -q
```

再运行：`cd frontend && npx vue-tsc --noEmit`

预期：测试全部通过，类型检查退出码为 0。
