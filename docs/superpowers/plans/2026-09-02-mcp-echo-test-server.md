# MCP Echo 测试服务 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加一个平台级 Echo MCP 测试服务，让所有智能体都可以调用 `echo` 工具验证 MCP 协议、固定 Authorization Bearer Token、NanZi 用户身份断言和请求链路。

**Architecture:** Echo MCP 作为 NanZi 内置的 Streamable HTTP MCP 服务挂载在平台 API 进程中，由管理员通过 MCP 管理页一键创建一个全局 MCP 配置和已发布的 `echo` 工具。Echo 工具读取请求 Header，验证当前 MCP 配置的固定 `Authorization: Bearer` Token，并使用当前 MCP 的 JWKS 对 `X-Nanzi-User-Assertion` 验签；工具只返回验证后的安全诊断字段，不返回任何原始凭证。创建后的全局 MCP 按现有 MCP 版本绑定机制对所有智能体可挂载。

**Tech Stack:** Python 3.11、FastAPI、MCP FastMCP Streamable HTTP、PyJWT、cryptography、SQLAlchemy Async、Vue 3 + TypeScript、pytest。

---

### Task 1: Echo MCP 验证器与工具服务

**Files:**
- Create: `app/services/mcp/echo_server.py`
- Test: `tests/services/mcp/test_mcp_echo_server.py`

- [x] **Step 1: Write the failing tests**

覆盖以下真实行为：固定 Authorization Bearer Token 校验；缺少用户断言时返回未收到状态；有效 EdDSA JWS 返回 `verified_user_context`、`verified_agent_context` 和 `request_context`；无效签名返回认证错误；诊断结果不包含原始 Authorization 或 JWS。

```python
def test_echo_diagnostics_returns_verified_identity_without_raw_credentials():
    result = build_echo_diagnostics(
        headers=valid_headers,
        server=server,
        private_key=private_key,
    )

    assert result["message"] == "已收到"
    assert result["diagnostics"]["authorization_valid"] is True
    assert result["diagnostics"]["user_assertion_valid"] is True
    assert result["diagnostics"]["verified_user_context"]["user_id"] == "123"
    assert "authorization" not in json.dumps(result)
    assert assertion not in json.dumps(result)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/services/mcp/test_mcp_echo_server.py -q`

Expected: FAIL because `app.services.mcp.echo_server` and `build_echo_diagnostics` do not exist.

- [x] **Step 3: Implement the minimal verifier and FastMCP service**

实现以下边界：

```python
def build_echo_diagnostics(headers, server, private_key):
    # 只比较 Authorization: Bearer 的 Token 值，不返回原值。
    # User Assertion 存在时校验 EdDSA、kid、iss、aud、时间窗口、sub 和 user_context.user_id。
    # 成功后仅返回标准用户字段、agent 字段、request_id 和认证布尔状态。

echo_mcp = FastMCP(
    "NanZi Echo 测试 MCP",
    instructions="用于验证 NanZi MCP 协议和用户身份透传，不执行任何业务操作。",
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)

@echo_mcp.tool()
def echo(ctx: Context) -> dict:
    return build_echo_diagnostics(
        headers=ctx.request_context.request.headers,
        server=load_echo_server(),
        private_key=load_mcp_private_key(load_echo_server()),
    )
```

服务端使用稳定的内置 Echo Server ID 读取 `sys_mcp_servers` 配置；缺少固定 Token、密钥或数据库配置时返回明确的 MCP 错误，不降级为信任请求。诊断结果禁止包含完整 Token、JWS、私钥和 `jti`。

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/services/mcp/test_mcp_echo_server.py -q`

Expected: PASS。

### Task 2: 平台挂载和一键创建全局 Echo MCP

**Files:**
- Modify: `app/main.py`
- Modify: `app/api/portal/endpoints/mcp.py`
- Test: `tests/api/test_mcp_echo_server.py`
- Test: `tests/test_mcp_lifecycle_migrations_contract.py`

- [x] **Step 1: Write failing API tests**

验证管理员创建接口只创建一个稳定的全局 Echo MCP、自动生成固定 Authorization Bearer Token 和 Ed25519 密钥、预置已发布的 `echo` 工具；重复调用返回同一服务；非管理员不能创建；创建接口不回显任何密钥或 Token。

- [x] **Step 2: Run API tests to verify failure**

Run: `.venv/bin/python -m pytest tests/api/test_mcp_echo_server.py -q`

Expected: FAIL because the create endpoint and mounted route do not exist.

- [x] **Step 3: Add the mounted service and idempotent create endpoint**

在 `app/main.py` 挂载 `echo_mcp.streamable_http_app()`；在 MCP Portal 增加管理员接口，例如 `POST /api/portal/mcp/servers/echo-test`。接口使用稳定 UUID、`scope="global"`、`credential_mode="fixed_token_signed_user"`、`user_assertion_enabled=True`，使用当前请求的外部 Base URL 生成 Echo MCP 地址，并插入或复用已发布的 `echo` 工具。固定 Token 和签名私钥只加密保存。

- [x] **Step 4: Run API tests to verify pass**

Run: `.venv/bin/python -m pytest tests/api/test_mcp_echo_server.py tests/services/mcp/test_mcp_echo_server.py -q`

Expected: PASS。

### Task 3: MCP 管理页入口和调用说明

**Files:**
- Modify: `frontend/src/components/system/McpServerRegistry.vue`
- Modify: `frontend/src/views/McpManagement.vue` only if the registry entry requires page-level wiring
- Create: `tests/frontend/test_mcp_echo_server_contract.py`

- [x] **Step 1: Write the failing frontend contract tests**

断言平台 MCP 管理页存在“创建 Echo 测试 MCP”入口、调用创建接口、创建成功后刷新并选中服务；页面说明 Echo MCP 可被平台智能体挂载，且不展示原始 Token/JWS。

- [x] **Step 2: Run the frontend contract test to verify failure**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_mcp_echo_server_contract.py -q`

Expected: FAIL because the button and API call do not exist。

- [x] **Step 3: Add the management entry**

在平台 MCP（`scope="global"`）列表头部新增按钮“创建 Echo 测试 MCP”，仅管理员显示。成功后刷新服务列表并选中 Echo MCP；重复创建显示“已存在并已就绪”。Echo 服务卡片标注“平台测试 MCP / 所有智能体可挂载”，工具 `echo` 默认显示“已发布”。

- [x] **Step 4: Run frontend checks**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_mcp_echo_server_contract.py -q`

Expected: PASS。

Run: `cd frontend && ./node_modules/.bin/vue-tsc --noEmit`

Expected: PASS。

### Task 4: 文档和回归验证

**Files:**
- Create: `docs/md/mcp_echo_test_server.md`
- Modify: `FAQ.md`
- Modify: `data/docs/FAQ.md`
- Modify: `README.md`
- Modify: `tests/CHECKLIST.md`

- [x] **Step 1: Document usage and response contract**

说明 Echo MCP 的用途、创建入口、所有智能体挂载方式、对话调用示例、返回 JSON、认证失败场景和安全边界；明确它验证的是实际 NanZi 出站 MCP 请求，不返回原始 Header。

- [x] **Step 2: Run documentation and targeted regression checks**

Run: `.venv/bin/python -m pytest tests/services/mcp/test_mcp_echo_server.py tests/api/test_mcp_echo_server.py tests/services/mcp/test_mcp_auth_policy.py tests/frontend/test_mcp_echo_server_contract.py --confcutdir=tests/frontend -q`

Expected: PASS。

Run: `git diff --check`

Expected: no output。

### Task 5: Review and commit

- [x] **Step 1: Inspect the complete diff**

确认新增服务未把 Token/JWS 写入日志或返回值，未改变未开启 UserContext 的现有 MCP 调用路径，Echo MCP 仅有无副作用的 `echo` 工具，API 创建接口具备管理员校验和幂等行为。

- [ ] **Step 2: Commit**

```bash
git add app/main.py app/api/portal/endpoints/mcp.py app/services/mcp/echo_server.py frontend/src/components/system/McpServerRegistry.vue tests docs/md/mcp_echo_test_server.md README.md FAQ.md data/docs/FAQ.md
git commit -m "feat: 增加 MCP Echo 联调测试服务"
```
