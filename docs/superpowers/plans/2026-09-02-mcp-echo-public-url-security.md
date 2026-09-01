# Echo MCP 公网地址与 Host 白名单 Implementation Plan

> **For agentic workers:** 本计划在当前任务中由主代理按步骤执行，遵循测试先行。

**Goal:** 使用现有 `APP_PUBLIC_URL` 自动配置 Echo MCP 的 Host/Origin 白名单和对外 `sse_url`，同时保持未配置时的本地回退行为。

**Architecture:** 在 `echo_server.py` 增加纯函数，将绝对 HTTP/HTTPS 公网 URL 转换为 `TransportSecuritySettings`；无有效公网 URL 时返回 `None`，让 MCP SDK 保留 localhost 默认安全策略。Echo 创建接口优先使用 `settings.APP_PUBLIC_URL`，否则使用 `request.base_url`。

**Tech Stack:** Python 3.11, FastAPI, Pydantic Settings, MCP Streamable HTTP, pytest。

---

### Task 1: Add failing configuration and URL precedence tests

**Files:**
- Modify: `tests/services/mcp/test_mcp_echo_server.py`
- Modify: `tests/api/test_mcp_echo_server_api_contract.py`

- [x] Add tests for public URL parsing, invalid URL fallback, and Echo creation URL precedence.
- [x] Run the focused tests and confirm they fail because the helper and preference do not exist.

### Task 2: Implement public URL security configuration

**Files:**
- Modify: `app/services/mcp/echo_server.py`
- Modify: `app/api/portal/endpoints/mcp.py`

- [x] Add a pure helper that parses `APP_PUBLIC_URL`, builds `allowed_hosts` and `allowed_origins`, and rejects non-HTTP(S) or hostless values.
- [x] Pass the explicit `TransportSecuritySettings` to `FastMCP` only when a valid public URL is configured.
- [x] Make Echo creation prefer `APP_PUBLIC_URL`, falling back to `request.base_url`.

### Task 4: Wire Docker configuration and document production troubleshooting

**Files:**
- Modify: `docker/docker-compose.yml`
- Modify: `docker/docker-compose.ai-agent.yml`
- Modify: `docker/README.md`
- Modify: `docker/README_EN.md`
- Modify: `docs/md/mcp_echo_test_server.md`
- Modify: `FAQ.md`
- Modify: `data/docs/FAQ.md`
- Test: `tests/test_docker_mcp_public_url_contract.py`

- [x] Pass `APP_PUBLIC_URL` into the API container in both Compose variants.
- [x] Document the `421 Invalid Host header` cause, checks, and Echo endpoint refresh step.
- [x] Add a contract test covering both Compose files and the production troubleshooting guidance.

### Task 3: Verify the complete focused regression set

**Files:**
- Test only; no additional production files.

- [x] Run Echo service/API tests, MCP auth tests, frontend Echo contract tests, and `git diff --check`.
- [x] Confirm no database migration, frontend change, or service startup is required.
