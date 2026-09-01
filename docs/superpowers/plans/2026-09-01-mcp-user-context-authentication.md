# MCP User Context Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 NanZi MCP 调用增加可选的固定 MCP Token + EdDSA 签名 UserContext，使自有 MCP 能验证用户和智能体身份，并兼容不解析该扩展的第三方 MCP。

**Architecture:** 复用已认证的 `AgentContext`，在开启能力的 MCP 出站调用边界生成最小 UserContext JWS，通过 `X-Nanzi-User-Assertion` 发送；固定 MCP Token、签名私钥、Key ID、Issuer 和 Audience 均按 MCP 实例独立保存。未开启 UserContext 的 MCP 完全沿用旧调用链。完整用户断言不进入 Prompt、工具参数、前端事件或日志；MCP 工具测试台只返回脱敏认证状态。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy Async、Pydantic 2、PyJWT + cryptography Ed25519、Vue 3 + TypeScript、pytest。

---

## 文件范围

- Create: `app/services/mcp/user_context_assertion.py` — UserContext、扩展字段过滤、EdDSA 签名/验签。
- Create: `app/services/mcp/mcp_auth_policy.py` — MCP 认证模式和 Header 组装。
- Modify: `app/models/mcp.py` — MCP 级用户断言配置和加密私钥字段。
- Modify: `app/api/portal/endpoints/mcp.py` — API schema、保存校验、Token 脱敏。
- Modify: `app/services/ai/tools/mcp_client.py` — 调用边界注入认证 Header。
- Modify: `app/services/ai/tools/mcp_factory.py` — 传递当前用户和智能体上下文。
- Modify: `frontend/src/components/system/McpServerRegistry.vue` — 管理页面配置项。
- Create: `db-prod-pg/V37-add_mcp_user_context_auth.sql` — PostgreSQL 迁移。
- Create: `db-prod/V110-add_mcp_user_context_auth.sql` — MySQL 迁移，沿用平台主库版本序列。
- Create: `tests/services/mcp/test_user_context_assertion.py`。
- Create: `tests/services/mcp/test_mcp_auth_policy.py`。
- Create: `tests/api/test_mcp_user_context_auth.py`。
- Create: `tests/frontend/test_mcp_user_context_management_contract.py`。
- Modify: `tests/ai/tools/test_mcp_client_grounding.py`。
- Create: `docs/md/mcp_user_context_integration_guide.md` — 自有 MCP 业务方接入说明。

## Task 1：UserContext 签名契约

**Files:** `app/services/mcp/user_context_assertion.py`, `tests/services/mcp/test_user_context_assertion.py`

- [ ] **Step 1: 写失败测试。** 锁定 Payload 必含 `iss`、`aud`、`sub`、`user_context`、`custom_attributes`、`agent_id`、`agent_version_id`、`request_id`、`jti`、`iat`、`exp`；当前不含 `tenant_id`、`scope`。
- [ ] **Step 2: 写失败测试。** 覆盖修改 Payload 验签失败、过期失败、错误 audience 失败、保留字段覆盖失败、敏感扩展字段删除、扩展字段超过 8 KiB 拒绝。
- [ ] **Step 3: 实现 PyJWT EdDSA 签名。** 使用 `jwt.encode(..., algorithm="EdDSA", headers={"kid": key_id, "typ": "JWT"})`，私钥不从请求体读取。
- [ ] **Step 4: 实现字段规则。** `extra_data` 只能进入 `custom_attributes`；只允许服务端用户资料；过滤 `api_key`、`password`、`token`、`cookie`、`private_key` 和保留字段；拒绝非 object 和超限 JSON。
- [ ] **Step 5: 运行。** `pytest tests/services/mcp/test_user_context_assertion.py -q`，预期全部通过。

## Task 2：MCP 配置和数据库

**Files:** `app/models/mcp.py`, `app/api/portal/endpoints/mcp.py`, `db-prod-pg/V37-add_mcp_user_context_auth.sql`, `db-prod/V110-add_mcp_user_context_auth.sql`, `tests/api/test_mcp_user_context_auth.py`

- [ ] **Step 1: 写失败 API 测试。** 覆盖认证模式校验、Audience 可由系统生成、Token 不回显、旧 static 模式保持兼容。
- [ ] **Step 2: 增加字段。** 增加 MCP 级 `credential_mode`、`fixed_token_encrypted`、`user_assertion_enabled`、`user_assertion_header`、`user_assertion_audience`、`user_assertion_key_id`、`user_assertion_issuer` 和 `user_assertion_private_key_encrypted`。
- [ ] **Step 3: 实现保存和返回。** 仅允许 `static` 和 `fixed_token_signed_user`；固定 Token 和签名私钥均按 MCP 加密保存，不在 response 返回；编辑时空 Token 表示保持原值；UserContext 使用默认安全字段，不配置白名单。
- [ ] **Step 4: 编写迁移。** 只新增字段，不直接改数据库；默认值保持旧 MCP 为 `static` 且不发送 UserContext。
- [ ] **Step 5: 运行。** `pytest tests/api/test_mcp_user_context_auth.py -q && git diff --check`。

## Task 3：MCP 出站调用注入

**Files:** `app/services/mcp/mcp_auth_policy.py`, `app/services/ai/tools/mcp_client.py`, `app/services/ai/tools/mcp_factory.py`, `tests/services/mcp/test_mcp_auth_policy.py`, `tests/ai/tools/test_mcp_client_grounding.py`

- [ ] **Step 1: 写失败测试。** static 模式仅发送现有固定 Header；签名模式增加 `X-Nanzi-User-Assertion` 和 `X-Request-ID`；关闭开关时不发送断言；日志不出现 Token/JWS。
- [ ] **Step 2: 实现 `McpAuthPolicyService.build_headers()`。** 输入已认证用户、实际智能体、MCP Server 和 request ID，按配置生成短期断言并组合 Header。
- [ ] **Step 3: 扩展 `McpClientService.call_remote_tool()`。** 增加 `user_info`、`agent_info`、`request_id` 可选参数；保持旧调用方不传参数时行为不变。
- [ ] **Step 4: 修改 `McpToolFactory`。** 从后端 AgentContext 取得用户和智能体信息；严禁从工具 arguments 或前端上下文取得身份。
- [ ] **Step 5: 处理 session。** 断言不存入可复用 session；签名调用使用 `server_id + user_id + call_id` 的临时会话，避免复用旧断言和 `jti`，并增加跨调用隔离测试。
- [ ] **Step 6: 运行。** `pytest tests/services/mcp/test_mcp_auth_policy.py tests/ai/tools/test_mcp_client_grounding.py -q`。

## Task 4：MCP 管理页面

**Files:** `frontend/src/components/system/McpServerRegistry.vue`, `frontend/src/views/McpManagement.vue`（仅需要更新说明时），`tests/frontend/test_mcp_user_context_management_contract.py`

- [ ] **Step 1: 写前端契约测试。** 页面保留原有身份认证 Header，新增 UserContext 开关、只读 Audience、只读 Issuer、JWKS 地址和默认字段说明；不展示固定 Token、私钥或完整 JWS。
- [ ] **Step 2: 扩展页面信息。** 只保留 `user_assertion_enabled` 用户操作；Audience 按 MCP ID 自动生成，Issuer 固定为 `nanzi-platform`，Key ID 和私钥由系统生成；保存后展示可复制的只读配置。
- [ ] **Step 3: 添加说明。** 明确沿用原有固定 Token/Authorization 认证；签名 UserContext 仅由开关控制；第三方 MCP 可关闭用户断言；JWS 防篡改但不加密；提供 Python/Java 模拟代码和完整字段表。
- [ ] **Step 4: 运行。** `pytest --confcutdir=tests/frontend tests/frontend/test_mcp_user_context_management_contract.py -q`；`cd frontend && ./node_modules/.bin/vue-tsc --noEmit`。

## Task 5：JWKS 和运行配置

**Files:** `app/main.py` 新增按 MCP 实例区分的公开 `/.well-known/nanzi/mcp/{server_id}/jwks.json`；`tests/api/test_mcp_jwks_contract.py`；`docs/md/mcp_user_context_integration_guide.md`。

- [ ] **Step 1: 写失败测试。** JWKS 只返回公钥、`kid`、算法和用途，不返回私钥；未知 `kid` 无法验签。
- [ ] **Step 2: 实现公钥发布。** NanZi 从当前 MCP 的加密配置读取私钥；JWKS 只返回当前 MCP 的公钥；Key ID 由系统生成，业务方根据 JWT Header 的 `kid` 选择公钥。
- [ ] **Step 3: 写密钥轮换说明。** 先发布新公钥，再切换签发 `kid`，等待旧断言过期后删除旧公钥。
- [ ] **Step 4: 运行。** `pytest tests/api/test_mcp_jwks_contract.py -q`。

## Task 6：业务 MCP 接入文档和回归

**Files:** `docs/md/mcp_user_context_integration_guide.md`, `tests/services/mcp/test_mcp_integration_contract.py`

- [ ] **Step 1: 编写业务方中间件。** 统一验证固定 Token、JWS 签名、`iss`、`aud`、`exp`、`jti`，解析 `user_context`、`custom_attributes`、`agent_id` 和 `agent_version_id` 为 `McpPrincipal`。
- [ ] **Step 2: 编写工具示例。** 工具从 `ctx.principal.user_id` 获取用户，不从 arguments 获取 `user_id`；再执行业务资源级权限校验。
- [ ] **Step 3: 编写兼容说明。** 不解析 `X-Nanzi-User-Assertion` 的第三方 MCP 继续使用固定 Token，但没有用户级身份能力；可按配置不发送断言。
- [ ] **Step 4: 运行全目标回归。** `pytest tests/services/mcp tests/api/test_mcp_user_context_auth.py tests/ai/tools/test_mcp_client_grounding.py -q`；`git diff --check`；前端执行 `./node_modules/.bin/vue-tsc --noEmit`。

### 工具测试台展示

- 开启 UserContext 的 MCP 在工具测试台中使用当前登录用户生成真实断言并发出请求。
- 测试结果只返回 `user_assertion_sent`、Header 名称、脱敏值、Audience、Issuer 和 Key ID；完整 JWS 不返回浏览器。

## 实施边界

静态测试只证明签名、字段过滤、API 脱敏、Header 兼容和前端契约；不证明真实业务 MCP 的公钥部署、固定 Token 配置、TLS、网络访问和业务数据权限。不得启动 `./dev.sh`，不得执行部署或生产数据库操作；真实 MCP 联调由用户在控制台启动服务后执行。
