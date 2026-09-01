# MCP Echo 认证诊断返回 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让内置 Echo MCP 返回认证处理流程和脱敏凭证样例，帮助确认 MCP 请求链路，同时不泄露完整认证信息。

**Architecture:** 在 Echo 服务内部增加通用的脱敏函数和处理步骤收集器。`build_echo_diagnostics` 在读取请求头、校验 Authorization、读取并验签 UserContext 的各阶段追加步骤；成功和失败都只返回脱敏后的值，继续复用现有的验签和解析逻辑。

**Tech Stack:** Python 3.11、FastMCP、PyJWT、pytest。

---

### Task 1: 锁定 Echo 诊断返回契约

**Files:**
- Modify: `tests/services/mcp/test_mcp_echo_server.py`

- [x] **Step 1: Write the failing tests**

为成功请求增加断言：返回 `authorization_masked`、`user_assertion_masked` 和按顺序排列的 `processing_log`，且两种原始凭证不出现在返回 JSON 中。为 Authorization 失败和 UserContext 验签失败增加断言：错误仍然抛出，错误信息和处理步骤不包含完整凭证。

- [x] **Step 2: Run the focused tests to verify failure**

运行：

```bash
.venv/bin/python -m pytest tests/services/mcp/test_mcp_echo_server.py -q
```

预期：新增断言失败，原因是当前诊断结果没有脱敏字段和处理步骤。

### Task 2: 实现脱敏展示和处理流程

**Files:**
- Modify: `app/services/mcp/echo_server.py`

- [x] **Step 1: Add a bounded masking helper**

实现只保留首尾字符、中间替换为 `***` 的函数；空值返回 `None`，短值也必须保证不返回完整原文。

- [x] **Step 2: Add processing steps to the existing diagnostic path**

在 `build_echo_diagnostics` 中记录读取请求头、Authorization 校验、UserContext 读取、UserContext 验签和上下文解析步骤；成功时返回脱敏 Authorization、脱敏 UserContext 断言和步骤列表；失败路径不把 token 拼接进步骤文本或异常信息。

### Task 3: 回归验证

**Files:**
- Test: `tests/services/mcp/test_mcp_echo_server.py`
- Test: `tests/api/test_mcp_echo_server_api_contract.py`

- [x] **Step 1: Run focused Echo tests**

```bash
.venv/bin/python -m pytest tests/services/mcp/test_mcp_echo_server.py tests/api/test_mcp_echo_server_api_contract.py -q
```

预期：全部通过。

- [x] **Step 2: Run MCP authentication regression tests**

```bash
.venv/bin/python -m pytest tests/services/mcp/test_mcp_auth_policy.py tests/services/mcp/test_user_context_assertion.py tests/api/test_mcp_user_context_auth.py -q
```

预期：全部通过，证明出站签发和入站验签逻辑未被改变。

- [x] **Step 3: Check the diff**

```bash
git diff --check
```

预期：无空白错误。
