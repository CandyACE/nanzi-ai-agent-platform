# 文件工具思考卡片元信息 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让思考卡片显示文件工具实际操作的逻辑路径及可用的文件操作元信息。

**Architecture:** 在后端工具完成日志中构造安全的结构化 `file_metadata`，路径统一保持 `/workspace/...` 逻辑命名空间；前端时间线根据该字段生成操作标题和摘要，并兼容旧日志。

**Tech Stack:** Python 3.11、FastAPI/AgentScope 运行时、Vue 3、TypeScript、pytest 前端契约测试。

---

### Task 1: 后端文件工具元数据

**Files:**
- Modify: `app/services/ai/runners/assistant_agent_runner.py`
- Test: `tests/ai/` 中现有 assistant runner/tool observation 测试或新增对应测试

- [ ] 写测试：验证 Read/Write/Edit/Glob/Grep 的日志包含逻辑路径、操作类型和工具特有字段。
- [ ] 运行测试确认在实现前失败。
- [ ] 增加纯函数构造 `file_metadata`，只读取逻辑工具参数和安全输出，不暴露宿主机路径。
- [ ] 将元数据挂到现有 `log` 事件，保持原 `details`、状态和耗时字段不变。
- [ ] 验证工具元数据计算失败时不影响工具结果。

### Task 2: 前端思考卡片展示

**Files:**
- Modify: `frontend/src/components/chat/ChatExecutionTimeline.vue`
- Modify: `frontend/src/utils/processTimeline.ts`（如需扩展日志类型）
- Test: `tests/frontend/test_execution_stage_card_contract.py`

- [ ] 写契约测试：验证有 `file_metadata` 时展示操作类型、逻辑路径和摘要字段，旧日志仍可展示。
- [ ] 运行前端契约测试确认失败。
- [ ] 在卡片标题中展示“读取/写入/编辑/搜索 + 路径”。
- [ ] 在详情中展示大小、行数、范围、命中数、变更统计等可选字段。
- [ ] 验证 `/app/data` 等宿主机路径不会进入展示字段。

### Task 3: 定向回归验证

- [ ] 运行后端相关 pytest。
- [ ] 运行 `pytest --confcutdir=tests/frontend tests/frontend/test_execution_stage_card_contract.py -q`。
- [ ] 运行 `frontend/node_modules/.bin/vue-tsc --noEmit`。
- [ ] 运行 `git diff --check`，确认只包含本功能相关修改。
