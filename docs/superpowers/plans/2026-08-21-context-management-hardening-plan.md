# Context Management Hardening Implementation Plan

> For agentic workers: execute each task in order and keep the focused regression suite green.

**Goal:** 修复上下文管理 review 中剩余的摘要分支、动态模型窗口、注册表异常和异步摘要一致性问题。

**Architecture:** 路由前只构造安全的兜底上下文；最终 agent 与模型确定后重新构造实际发送上下文。历史截断通过统一状态重置清除旧摘要，后台摘要通过消息 seq 与 branch revision 条件写入避免乱序或旧分支覆盖。

**Tech Stack:** Python 3.11, FastAPI, asyncio, Redis, pytest, SQLAlchemy async.

---

### Task 1: 历史截断状态重置

**Files:**
- Modify: app/services/ai/memory_service.py
- Modify: app/api/v1/endpoints/chat.py
- Modify: app/services/ai/agent_service.py
- Test: tests/services/ai/test_memory_service.py
- Test: tests/services/ai/test_seq_cursor_regression.py

- [x] 写失败测试：截断后清理 debounce key、digest key 和结构化摘要，保留 seq counter。
- [x] 运行聚焦测试并确认失败。
- [x] 实现统一的会话上下文状态重置，并从 API 截断、自动客户端前缀截断和清空路径调用。
- [x] 运行测试确认通过。

### Task 2: 路由后重建目标模型上下文

**Files:**
- Modify: app/services/ai/agent_service.py
- Test: tests/services/ai/test_seq_cursor_regression.py

- [x] 写失败测试：自动路由选择 B agent 后，最终窗口预算使用 B 模型而不是 chat-bi。
- [x] 写失败测试：路由前只允许确定性上下文压缩，最终模型确定后才允许异步语义摘要。
- [x] 将路由前预算限制为配置兜底值，并在最终 agent/model 信息可用后重建发送上下文。
- [x] 运行路由与上下文回归测试确认通过。

### Task 3: 模型注册表异常兜底

**Files:**
- Modify: app/services/ai/agent_service.py
- Test: tests/services/ai/test_seq_cursor_regression.py

- [x] 写失败测试：最终 runtime model info 抛出 ModelRegistryError 时仍返回正常模型请求路径。
- [x] 增加安全 RuntimeModelInfo 兜底，并让最终上下文预算回退 agent_context_max_tokens。
- [x] 运行异常路径测试确认通过。

### Task 4: 异步摘要条件写入

**Files:**
- Modify: app/services/ai/memory_service.py
- Modify: app/services/ai/agent_service.py
- Modify: docs/md/ai_context_management_guide.md
- Test: tests/ai/test_context_compaction.py

- [x] 写失败测试：较旧 source seq 的后台摘要不能覆盖较新历史摘要。
- [x] 写失败测试：摘要 task 被任务集合持有，主链路只调度不等待。
- [x] 实现 task 引用集合和 Redis seq/branch revision 条件写入。
- [x] 更新行为矩阵和异步摘要说明。
- [x] 运行聚焦测试确认通过。

### Task 5: 全量相关验证

**Files:**
- Test: tests/services/ai/test_seq_cursor_regression.py
- Test: tests/ai/test_context_compaction.py
- Test: tests/services/ai/test_memory_service.py

- [x] 运行所有聚焦测试。
- [x] 运行当前相关 P1 优化测试并记录独立失败（知识库工具调用测试仍有既有失败）。
- [x] 执行 compileall、git diff --check，并检查改动未覆盖无关工作。
