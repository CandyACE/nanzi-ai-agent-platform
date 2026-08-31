# 生成文件下载地址加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 只允许本轮真实文件工具登记并返回的下载地址进入最终 assistant 消息，并将旧 manifest 发布路径统一到 `ai_artifacts`。

**Architecture:** 在 `AgentContext` 中保存当前执行链共享的真实下载地址白名单，产物登记成功后写入白名单；`AgentService` 在最终正文持久化和结束事件前过滤伪造的生成文件 URL，并用 retraction 修正已流式展示的正文。旧 `publish()` 改为将外部临时文件复制到当前用户工作区后复用 `register_artifact()`，下载端点继续只保留 DB 校验和旧 manifest 回退兼容。

**Tech Stack:** Python 3.11、FastAPI、Pydantic 2、SQLAlchemy AsyncSession、pytest、SSE 字典事件。

---

### Task 1: 盘点并定义可测试的下载地址白名单接口

**Files:**
- Modify: `app/core/context.py`
- Modify: `app/services/ai/tools/generated_file_service.py`
- Test: `tests/ai/tools/test_generated_file_service.py`

- [ ] **Step 1: Write failing tests**

增加测试，验证 `record_download_url()` 只记录非空且去重，`filter_untrusted_download_urls()` 保留本轮登记的生成文件 URL，并替换未登记的生成文件 URL；普通外链不受影响。

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python3 -m pytest -q tests/ai/tools/test_generated_file_service.py -k 'download_url_allowlist or filter_untrusted'`

Expected: FAIL because the context field and helper functions do not exist.

- [ ] **Step 3: Implement minimal registry and filter**

在 `AgentContext` 增加 `published_download_urls: List[str]`；在生成文件服务中增加当前上下文登记函数和只匹配 `/api/v1/chat/generated-files/{32位ID}?token=...` 的过滤函数。未知生成文件 URL 替换为“下载地址未通过文件工具确认”，非生成文件 URL 原样保留。

- [ ] **Step 4: Run focused tests and verify pass**

Run: `python3 -m pytest -q tests/ai/tools/test_generated_file_service.py -k 'download_url_allowlist or filter_untrusted'`

Expected: PASS。

### Task 2: 让登记成功的产物进入执行上下文，并覆盖委派链

**Files:**
- Modify: `app/services/ai/tools/generated_file_service.py`
- Modify: `app/services/ai/context_manager.py`
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Modify: `app/services/ai/tools/generated_file_tool.py`
- Test: `tests/ai/tools/test_generated_file_tool.py`

- [ ] **Step 1: Write failing tests**

增加测试验证 `publish_generated_file` 成功返回的 URL 会出现在当前 `AgentContext.published_download_urls` 中；登记失败时不写入白名单。

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python3 -m pytest -q tests/ai/tools/test_generated_file_tool.py -k 'allowlist or failure'`

Expected: FAIL because successful registration currently只返回 payload，不记录上下文。

- [ ] **Step 3: Implement minimal propagation**

在 `register_artifact()` 和统一发布函数成功构造 `PublishedArtifact` 后记录 URL；上下文重建时从旧上下文继承列表；普通子代理和批量子代理共享/回流同一列表，确保子代理生成的真实 URL 可被主回复白名单识别。

- [ ] **Step 4: Run focused tests and verify pass**

Run: `python3 -m pytest -q tests/ai/tools/test_generated_file_tool.py -k 'allowlist or failure'`

Expected: PASS。

### Task 3: 在最终正文出口过滤伪造链接

**Files:**
- Modify: `app/services/ai/agent_service.py`
- Modify: `app/services/ai/runtime/agentscope/stream_reconcile.py` or the generated-file service helper location chosen in Task 1
- Test: `tests/ai/test_agent_service_download_url_guard.py`

- [ ] **Step 1: Write failing tests**

覆盖三种行为：真实登记 URL 保留；未登记的标准生成文件 URL 被替换；普通 URL 保留。另测 `chat_completion_stream` 的最终正文和持久化正文使用过滤后的内容。

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python3 -m pytest -q tests/ai/test_agent_service_download_url_guard.py`

Expected: FAIL because主链路当前直接使用 `full_response_content`，没有下载地址过滤。

- [ ] **Step 3: Implement minimal final guard**

在主执行链完成后读取当前 `AgentContext` 白名单，过滤 `full_response_content`；如果过滤结果与已发送正文不同，发送一个 `retraction` 事件，使前端最终正文与持久化正文一致；`run_status` 和 assistant history 只使用过滤后的正文。不要过滤工具日志中的真实结果文本。

- [ ] **Step 4: Run focused tests and verify pass**

Run: `python3 -m pytest -q tests/ai/test_agent_service_download_url_guard.py tests/ai/test_prompt_assembler.py -k 'download or publish or allowlist'`

Expected: PASS。

### Task 4: 将旧 `publish()` 统一到 `ai_artifacts`

**Files:**
- Modify: `app/services/ai/tools/generated_file_service.py`
- Modify: `app/services/ai/tools/browser_tools.py`
- Modify: `app/services/chatbi_brief_service.py`
- Modify: `app/api/portal/endpoints/chatbi_briefs.py`
- Modify: `tests/ai/tools/test_generated_file_service.py`
- Modify: `tests/services/test_chatbi_brief_service.py` only if async API requires coverage

- [ ] **Step 1: Write failing tests**

增加测试验证旧发布入口将外部临时文件复制到当前用户工作区、创建 `AiArtifact`、返回 DB 下载地址，并且不再创建 `manifest.json`；验证缺少用户身份时拒绝发布。

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python3 -m pytest -q tests/ai/tools/test_generated_file_service.py -k 'publish_unifies or publish_requires_owner'`

Expected: FAIL because当前 `publish()` 是同步 manifest 发布，且不需要 owner context。

- [ ] **Step 3: Implement minimal unified publisher**

把 `publish()` 改为异步发布：接收 owner、会话、trace 和文件类型；将外部文件复制到当前用户工作区的受控目录后调用 `register_artifact()`。更新浏览器下载/PDF 和 ChatBI 简报调用方使用 `await`，保留下载端点的 manifest 回退以兼容既有历史链接。

- [ ] **Step 4: Run focused tests and verify pass**

Run: `python3 -m pytest -q tests/ai/tools/test_generated_file_service.py tests/ai/tools/test_browser_tool_configuration.py tests/services/test_chatbi_brief_service.py`

Expected: PASS。

### Task 5: 补充失败、假链接和下载回归测试

**Files:**
- Modify: `tests/api/v1/test_generated_file_download.py`
- Modify: `tests/ai/tools/test_generated_file_service.py`
- Create: `tests/ai/test_agent_service_download_url_guard.py`
- Modify: `tests/ai/test_prompt_assembler.py` only for any changed contract wording

- [ ] **Step 1: Add regression cases**

覆盖错误 token、过期 token、文件已删除、假 artifact URL、工具登记失败后不得出现在白名单，以及真实 URL 仍能下载。

- [ ] **Step 2: Run the complete focused download slice**

Run: `python3 -m pytest -q tests/ai/tools/test_generated_file_service.py tests/ai/tools/test_generated_file_tool.py tests/api/v1/test_generated_file_download.py tests/ai/test_agent_service_download_url_guard.py`

Expected: PASS；若发现当前 30 天代码与旧 7 天断言冲突，按当前仓库实际策略更新对应测试断言并单独报告，不扩大到无关 TTL 改动。

### Task 6: Review and static verification

**Files:**
- Review all modified files above

- [ ] **Step 1: Run formatting/syntax and diff checks**

Run: `python3 -m compileall -q app tests/ai tests/api/v1` and `git diff --check`。

- [ ] **Step 2: Review security boundaries**

确认过滤只影响生成文件 URL，不吞掉普通外链；确认文件路径仍经过工作区约束；确认 token 只保存哈希；确认最终持久化正文与 SSE 修正正文一致。

- [ ] **Step 3: Report validation boundary**

明确说明未启动服务、未运行浏览器/Redis/真实数据库验收；检查 `git status --short`，不自动 stage 或 commit。
