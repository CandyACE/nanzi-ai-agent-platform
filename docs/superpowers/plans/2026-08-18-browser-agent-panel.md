# 浏览器智能体右侧面板 Implementation Plan

> **For agentic workers:** 按项目协作边界执行本计划；每个任务完成后先运行对应验证，不自动 stage 或 commit。

**Goal:** 在 NanZi 中实现服务端远程 Chromium 浏览器会话、右侧 BrowserPanel、用户手动登录后继续执行、用户级登录 Profile 跨对话复用，以及当前 BrowserSession 级 guarded / autopilot 开关。

**Architecture:** 新增 BrowserProfile 与 BrowserSession 两层资源，由 Playwright Worker 管理隔离 Chromium Context；AgentScope 通过第一方 Browser Tools 使用语义化 `target_ref` 操作页面，EmbedChat 通过浏览器专用 SSE 事件打开右侧 BrowserPanel，并通过同源 WebSocket 展示画面和转发用户接管输入。现有 ChatCanvas 继续负责文件/代码预览，不扩展为浏览器容器。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.x Async、Pydantic 2、Playwright、AgentScope、Redis、Vue 3、TypeScript、Vite、pytest、vue-tsc。

**实施记录（2026-08-18）：** 已完成核心 MVP：双数据库迁移（MySQL V122 / PostgreSQL V22，含中文表与字段备注）、服务端 Playwright Worker、Profile/Session API、AgentScope 浏览器工具、guarded/autopilot 权限接入、敏感参数脱敏、同源 WebSocket Viewer、右侧 BrowserPanel 和聚焦回归测试。真实 Chromium、登录态跨对话和前端类型检查需由用户在具备依赖与服务的环境中验收。

---

## Task 1: 建立浏览器会话数据契约和迁移

**Files:**
- Create: `app/models/browser.py`
- Create: `app/schemas/browser.py`
- Create: `db-prod/V122-browser-session.sql`
- Create: `db-prod-pg/V22-browser-session.sql`
- Test: `tests/test_browser_session_migrations.py`
- Test: `tests/services/ai/test_browser_contracts.py`

- [ ] **Step 1: 写迁移契约测试，先验证当前实现缺少浏览器表。**

```python
def test_mysql_browser_migration_declares_profiles_and_sessions():
    sql = (ROOT / "db-prod/V122-browser-session.sql").read_text(encoding="utf-8")
    assert "browser_profiles" in sql
    assert "browser_sessions" in sql
    assert "encrypted_storage_ref" in sql
    assert "approval_mode" in sql


def test_postgresql_browser_migration_declares_same_contract():
    sql = (ROOT / "db-prod-pg/V22-browser-session.sql").read_text(encoding="utf-8")
    assert "browser_profiles" in sql
    assert "browser_sessions" in sql
    assert "user_id" in sql
    assert "profile_id" in sql
```

- [ ] **Step 2: 运行迁移契约测试，确认测试先失败。**

Run: `pytest tests/test_browser_session_migrations.py -q`

Expected: FAIL because the two migration files do not exist.

- [ ] **Step 3: 实现 MySQL 和 PostgreSQL 对齐迁移。**

迁移必须创建：

```sql
browser_profiles
- id varchar(36) primary key
- user_id bigint/int not null
- display_name varchar(120) not null
- encrypted_storage_ref text not null
- status varchar(20) not null default 'active'
- last_used_at datetime/timestamp null
- created_at datetime/timestamp not null
- updated_at datetime/timestamp not null

browser_sessions
- id varchar(36) primary key
- profile_id varchar(36) not null
- user_id bigint/int not null
- attached_conversation_id varchar(64) null
- current_url text null
- page_title varchar(500) null
- approval_mode varchar(20) not null default 'guarded'
- status varchar(20) not null default 'active'
- viewer_token_hash varchar(128) null
- last_seen_at datetime/timestamp null
- created_at datetime/timestamp not null
- updated_at datetime/timestamp not null
```

为 `user_id`、`profile_id`、`status` 和 `attached_conversation_id` 添加查询索引；Profile 与 Session 的 `user_id` 必须同时保存，避免只通过 Profile 反查导致越权。

- [ ] **Step 4: 写 SQLAlchemy 模型和 Pydantic 契约。**

```python
class BrowserApprovalMode(str, Enum):
    GUARDED = "guarded"
    AUTOPILOT = "autopilot"


class BrowserSessionStatus(str, Enum):
    ACTIVE = "active"
    WAITING_USER = "waiting_user"
    DETACHED = "detached"
    CLOSED = "closed"
    CRASHED = "crashed"


class BrowserSessionOpenRequest(BaseModel):
    url: str = Field(default="https://www.baidu.com/", min_length=1, max_length=2048)
    profile_id: str | None = None


class BrowserPolicyUpdateRequest(BaseModel):
    approval_mode: BrowserApprovalMode
```

`BrowserProfileResponse`、`BrowserSessionResponse` 只返回状态、URL、标题和时间，不返回 `encrypted_storage_ref`、Cookie、Viewer token 原文或浏览器存储内容。

- [ ] **Step 5: 运行契约测试和 Python 编译。**

Run: `pytest tests/test_browser_session_migrations.py tests/services/ai/test_browser_contracts.py -q`

Run: `python3 -m compileall -q app/models/browser.py app/schemas/browser.py`

Expected: PASS。

## Task 2: 实现浏览器安全策略和 Playwright Worker

**Files:**
- Create: `app/services/ai/browser/__init__.py`
- Create: `app/services/ai/browser/browser_policy.py`
- Create: `app/services/ai/browser/browser_worker.py`
- Modify: `app/services/ai/tools/system_tools.py`
- Test: `tests/services/ai/test_browser_policy.py`
- Test: `tests/services/ai/test_browser_worker.py`

- [ ] **Step 1: 写 URL、动作风险和敏感参数的失败测试。**

```python
def test_guarded_blocks_submit_and_allows_search_click():
    assert classify_browser_action(role="button", name="百度一下") == "interact"
    assert classify_browser_action(role="button", name="提交订单") == "commit"
    assert decide_browser_action("guarded", "interact").allowed is True
    assert decide_browser_action("guarded", "commit").requires_confirmation is True


def test_navigation_rejects_private_and_metadata_addresses():
    with pytest.raises(BrowserUrlBlocked):
        validate_browser_navigation("http://127.0.0.1:8000/")
    with pytest.raises(BrowserUrlBlocked):
        validate_browser_navigation("http://169.254.169.254/latest/meta-data/")


def test_sensitive_fill_is_redacted_from_audit_payload():
    payload = redact_browser_arguments({"value": "secret", "sensitive": True})
    assert payload["value"] == "<redacted>"
```

- [ ] **Step 2: 运行失败测试。**

Run: `pytest tests/services/ai/test_browser_policy.py -q`

Expected: FAIL because the policy module and functions do not exist.

- [ ] **Step 3: 实现 BrowserPolicy。**

实现以下明确接口：

```python
def validate_browser_navigation(url: str) -> str: ...
def classify_browser_action(*, role: str | None, name: str | None) -> Literal["read", "interact", "commit"]: ...
def decide_browser_action(mode: str, action_class: str) -> BrowserDecision: ...
def redact_browser_arguments(arguments: dict[str, Any]) -> dict[str, Any]: ...
```

复用现有 `validate_url` 的 SSRF 基础逻辑，但在浏览器导航前和最终重定向后都重新解析 DNS/IP；明确拒绝 loopback、link-local、私网、云元数据和平台内部服务地址。`autopilot` 只改变当前 Session 的确认决策，不取消平台级禁止地址策略。

- [ ] **Step 4: 写 Worker 的 Playwright mock 测试。**

```python
async def test_worker_open_snapshot_and_semantic_click(mock_playwright):
    worker = BrowserWorker(playwright_factory=lambda: mock_playwright)
    opened = await worker.open(session_id="bs-1", profile_path="/tmp/profile-1", url="https://www.baidu.com/")
    snapshot = await worker.snapshot("bs-1")
    result = await worker.click("bs-1", target_ref="e18", snapshot=snapshot)
    assert opened.url == "https://www.baidu.com/"
    assert snapshot.elements[0].ref == "e17"
    assert result.action == "click"
    mock_playwright.page.get_by_role.assert_called_once()
```

- [ ] **Step 5: 实现 Worker 的最小接口并运行测试。**

Worker 必须封装 `browser.new_context`、`page.goto`、`page.screenshot`、可访问性元素提取、`get_by_role` / `get_by_text` 语义定位、`page.fill`、`page.keyboard.press`、滚动和关闭；不得向上层暴露 Playwright Page 对象。

Run: `pytest tests/services/ai/test_browser_policy.py tests/services/ai/test_browser_worker.py -q`

Expected: PASS。

## Task 3: 实现 Profile / Session 服务和安全 API

**Files:**
- Create: `app/services/ai/browser/browser_profile_service.py`
- Create: `app/services/ai/browser/browser_session_service.py`
- Create: `app/api/v1/endpoints/browser.py`
- Modify: `app/api/v1/api.py`
- Test: `tests/services/ai/test_browser_profile_service.py`
- Test: `tests/services/ai/test_browser_session_service.py`
- Test: `tests/api/v1/test_browser_sessions.py`

- [ ] **Step 1: 写用户隔离、重用和模式切换的失败测试。**

```python
async def test_open_reuses_user_profile_and_keeps_guarded_default(db_session, user_a):
    first = await service.open_or_resume(user_id=user_a.id, url="https://www.baidu.com/")
    second = await service.open_or_resume(user_id=user_a.id, url="https://www.baidu.com/")
    assert second.profile_id == first.profile_id
    assert second.approval_mode == "guarded"


async def test_user_cannot_read_or_update_another_users_session(db_session, user_a, user_b):
    session = await service.open_or_resume(user_id=user_a.id, url="https://www.baidu.com/")
    with pytest.raises(BrowserAccessDenied):
        await service.get_owned_session(user_id=user_b.id, session_id=session.id)
```

- [ ] **Step 2: 运行服务测试确认缺失实现。**

Run: `pytest tests/services/ai/test_browser_profile_service.py tests/services/ai/test_browser_session_service.py tests/api/v1/test_browser_sessions.py -q`

Expected: FAIL because the services, router and tables are not implemented.

- [ ] **Step 3: 实现 Profile 服务。**

实现以下接口：

```python
class BrowserProfileService:
    async def get_or_create_default(self, *, user_id: int) -> BrowserProfile: ...
    async def list_owned(self, *, user_id: int) -> list[BrowserProfile]: ...
    async def delete_owned(self, *, user_id: int, profile_id: str) -> None: ...
```

Profile 的物理存储引用只能由服务内部生成；API 不接收任意路径，不允许用户指定其他用户的 profile path。删除前先停止该 Profile 的 active Session，再清理加密存储引用对应的数据。

- [ ] **Step 4: 实现 Session 服务。**

实现以下接口：

```python
class BrowserSessionService:
    async def open_or_resume(self, *, user_id: int, conversation_id: str | None, url: str, profile_id: str | None) -> BrowserSession: ...
    async def get_owned_session(self, *, user_id: int, session_id: str) -> BrowserSession: ...
    async def set_approval_mode(self, *, user_id: int, session_id: str, mode: BrowserApprovalMode) -> BrowserSession: ...
    async def mark_waiting_user(self, *, session_id: str, reason: str) -> BrowserSession: ...
    async def detach(self, *, user_id: int, session_id: str) -> BrowserSession: ...
    async def close(self, *, user_id: int, session_id: str, destroy_profile: bool) -> None: ...
```

使用数据库事务和用户/Profile 条件防止两个对话同时抢占同一 Session；模式切换只更新当前 Session，不更新用户默认设置。

- [ ] **Step 5: 暴露受保护 API 并运行测试。**

路由固定为 `/api/v1/chat/browser`，加入 `v1_secured`：

```text
POST   /sessions/open
GET    /sessions/active
GET    /sessions/{session_id}
PUT    /sessions/{session_id}/policy
POST   /sessions/{session_id}/detach
POST   /sessions/{session_id}/continue
POST   /sessions/{session_id}/close
DELETE /profiles/{profile_id}
POST   /sessions/{session_id}/viewer-token
```

每个路由都通过当前用户身份查询 Session；返回值只使用 `BrowserSessionResponse`。Viewer token 只返回一次 hash 不可逆的短时凭据，WebSocket 建连时校验 token、用户和 Session 三者关系。

Run: `pytest tests/services/ai/test_browser_profile_service.py tests/services/ai/test_browser_session_service.py tests/api/v1/test_browser_sessions.py -q`

Expected: PASS。

## Task 4: 接入 AgentScope Browser Tools

**Files:**
- Create: `app/services/ai/tools/browser_tools.py`
- Modify: `app/services/ai/tools/registry.py`
- Modify: `app/services/ai/runtime/agentscope/tools.py`
- Modify: `app/services/ai/agent_service.py`
- Test: `tests/services/ai/test_browser_tools.py`
- Test: `tests/ai/runtime/test_browser_tool_permissions.py`

- [ ] **Step 1: 写工具 schema、目标引用失效和敏感参数回归测试。**

```python
async def test_browser_fill_does_not_return_sensitive_value(browser_tools):
    result = await browser_tools.fill(session_id="bs-1", target_ref="e17", value="secret", sensitive=True)
    assert result["action"] == "fill"
    assert result["value"] == "<redacted>"


async def test_browser_click_rejects_stale_target_ref(browser_tools):
    with pytest.raises(BrowserTargetStale):
        await browser_tools.click(session_id="bs-1", target_ref="e18", snapshot_id="old")
```

- [ ] **Step 2: 实现 Browser Tools 的结构化调用。**

每个工具接收 `session_id`，从 `BrowserSessionService` 校验当前用户并从 Worker 获取页面；成功结果统一包含 `session_id`、`action`、`url`、`title`、`snapshot_id` 和 `screenshot_ref`。`browser_fill` 的敏感值只进入 Worker，不进入结果、Trace 或日志。

- [ ] **Step 3: 在 ToolRegistry 注册工具并标注权限。**

注册：

```python
"browser_session_open": browser_session_open,
"browser_snapshot": browser_snapshot,
"browser_click": browser_click,
"browser_fill": browser_fill,
"browser_press": browser_press,
"browser_scroll": browser_scroll,
"browser_wait": browser_wait,
"browser_back": browser_back,
"browser_forward": browser_forward,
"browser_close": browser_close,
```

`browser_snapshot`、`browser_wait` 和导航读取结果可标记为 read；`browser_click`、`browser_fill`、`browser_press` 等统一由 BrowserPolicy 返回 guarded/autopilot 决策，不依赖模型自行声明风险。

- [ ] **Step 4: 接入 AgentScope 运行时和工具提示。**

在 `app/services/ai/runtime/agentscope/tools.py` 增加浏览器工具的 schema 和权限映射；在 Agent 工具说明中明确：必须先调用 `browser_snapshot`，只能使用最新 snapshot 的 `target_ref`，遇到 `browser_user_required` 必须等待用户继续，不能通过 Shell 或任意 JS 绕过 BrowserPolicy。

- [ ] **Step 5: 运行工具和权限测试。**

Run: `pytest tests/services/ai/test_browser_tools.py tests/ai/runtime/test_browser_tool_permissions.py tests/ai/test_tool_description_validation.py -q`

Expected: PASS。

## Task 5: 接入 SSE 浏览器事件和 Agent 暂停恢复

**Files:**
- Modify: `app/services/ai/runtime/agentscope/event_stream.py`
- Modify: `app/services/ai/runtime/agentscope/confirmations.py`
- Modify: `app/services/ai/runtime/agentscope/pending_store.py`
- Modify: `app/services/ai/agent_service.py`
- Modify: `frontend/src/utils/agentscopeSseHandlers.ts`
- Test: `tests/ai/runtime/test_browser_agentscope_events.py`
- Test: `tests/frontend/test_browser_sse_contract.py`

- [ ] **Step 1: 写浏览器事件映射测试。**

```python
def test_browser_tool_result_emits_panel_state_and_action():
    chunks = list(map_browser_tool_result({
        "session_id": "bs-1",
        "action": "fill",
        "url": "https://www.baidu.com/",
        "title": "百度一下",
        "screenshot_ref": "media://browser/frame-1",
    }))
    assert {item["type"] for item in chunks} == {"browser_state", "browser_action"}
    assert chunks[0]["session_id"] == "bs-1"


def test_browser_user_required_is_interrupt_chunk():
    assert is_interrupt_sse_chunk({"type": "browser_user_required", "session_id": "bs-1"}) is True
```

- [ ] **Step 2: 增加浏览器事件映射。**

在 `event_stream.py` 增加 `browser_panel_open`、`browser_state`、`browser_action`、`browser_user_required` 和 `browser_panel_close` 的标准化 payload。大图只传 `screenshot_ref`，前端再通过受保护媒体接口拉取。

- [ ] **Step 3: 把浏览器 Session 绑定写入 pending snapshot。**

当 Agent 因登录或 guarded 高风险动作暂停时，将以下字段放入可序列化的 `stream_state`：

```python
{
    "browser_session_id": "bs-1",
    "browser_resume_action": "continue",
    "browser_panel_open": True,
}
```

恢复时重新校验当前用户拥有该 Session，再恢复 AgentScope runner；禁止只依赖前端传回的 `session_id`。

- [ ] **Step 4: 在前端 SSE handler 中保留事件顺序。**

`agentscopeSseHandlers.ts` 必须保证：`browser_panel_open` 先于 `browser_state`，`browser_user_required` 会让消息进入等待状态，`permission_result` / `browser_action` 恢复后追加到同一消息时间线，而不是创建孤立消息。

- [ ] **Step 5: 运行后端和前端事件测试。**

Run: `pytest tests/ai/runtime/test_browser_agentscope_events.py tests/frontend/test_browser_sse_contract.py --confcutdir=tests/frontend -q`

Expected: PASS。

## Task 6: 实现 BrowserPanel 与 WebSocket Viewer

**Files:**
- Create: `frontend/src/types/browser.ts`
- Create: `frontend/src/composables/chat/useBrowserSession.ts`
- Create: `frontend/src/components/embed/BrowserPanel.vue`
- Modify: `app/api/v1/endpoints/browser.py`
- Test: `tests/frontend/test_browser_panel_contract.py`

- [ ] **Step 1: 写 BrowserPanel 前端契约测试。**

```python
SOURCE = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")


def test_browser_panel_has_session_status_and_policy_switch():
    assert "BrowserSession" in SOURCE
    assert "guarded" in SOURCE
    assert "autopilot" in SOURCE
    assert "继续" in SOURCE
    assert "退出并清除" in SOURCE


def test_browser_panel_does_not_embed_external_baidu_iframe():
    assert "iframe" not in SOURCE
    assert "WebSocket" in SOURCE or "websocket" in SOURCE
```

- [ ] **Step 2: 定义前端类型和 composable 接口。**

```ts
export type BrowserApprovalMode = 'guarded' | 'autopilot'
export type BrowserSessionStatus = 'active' | 'waiting_user' | 'detached' | 'closed' | 'crashed'

export interface BrowserSessionState {
  id: string
  profile_id: string
  current_url: string | null
  page_title: string | null
  approval_mode: BrowserApprovalMode
  status: BrowserSessionStatus
  screenshot_ref: string | null
}

export interface UseBrowserSession {
  state: Ref<BrowserSessionState | null>
  open: (url?: string, profileId?: string) => Promise<void>
  setApprovalMode: (mode: BrowserApprovalMode) => Promise<void>
  continueWaitingUser: () => Promise<void>
  close: (destroyProfile?: boolean) => Promise<void>
}
```

- [ ] **Step 3: 实现同源 Viewer WebSocket。**

`useBrowserSession.ts` 先请求 viewer token，再连接 `/api/v1/chat/browser/sessions/{id}/viewer`；处理 `frame`、`state`、`error`、`closed` 四类消息。断线时指数退避重连三次，仍失败则显示“浏览器连接已断开”，不自动创建新 Session。

- [ ] **Step 4: 实现 BrowserPanel 布局。**

组件必须包含：地址与状态栏、画面区域、登录等待提示、继续按钮、停止按钮、guarded/autopilot 开关、关闭面板按钮和清除 Profile 按钮。用户输入事件发给 WebSocket；浏览器画面只来自服务端 frame，不直接访问第三方 DOM。

- [ ] **Step 5: 运行前端契约测试。**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_browser_panel_contract.py -q`

Expected: PASS。

## Task 7: 将 BrowserPanel 接入 EmbedChat 布局和消息流

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/utils/agentscopeSseHandlers.ts`
- Modify: `frontend/src/components/embed/SessionResourceScopeBar.vue`（仅在需要展示当前浏览器 Session 状态时）
- Test: `tests/frontend/test_embed_browser_panel_contract.py`

- [ ] **Step 1: 写布局和 SSE 联动测试。**

```python
SOURCE = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")


def test_embed_chat_mounts_browser_panel_and_accounts_for_pinned_width():
    assert "BrowserPanel" in SOURCE
    assert "browserPinnedWidth" in SOURCE
    assert "browserPanelVisible" in SOURCE


def test_embed_chat_keeps_browser_panel_separate_from_chat_canvas():
    assert "<ChatCanvas" in SOURCE
    assert "<BrowserPanel" in SOURCE
```

- [ ] **Step 2: 增加浏览器面板状态和宽度计算。**

在现有 `canvasPinnedWidthReactive`、`totalPinnedDrawerPx` 旁增加：

```ts
const browserPanelVisible = ref(false)
const browserPanelPinned = ref(true)
const browserPinnedWidth = ref(520)

const browserPanelWidthPx = computed(() => {
  if (!browserPanelVisible.value || !browserPanelPinned.value || isMobile.value) return 0
  return browserPinnedWidth.value
})
```

将 `browserPanelWidthPx` 加入 `totalPinnedDrawerPx`，但移动端保持全屏覆盖，不挤压其他抽屉。

- [ ] **Step 3: 处理浏览器 SSE 事件。**

收到 `browser_panel_open` 时打开并挂载 BrowserPanel；收到 `browser_state` 时更新当前 Session；收到 `browser_user_required` 时显示面板内继续提示；收到 `browser_panel_close` 时释放前端 WebSocket。所有浏览器动作仍追加到当前 Agent 消息的时间线。

- [ ] **Step 4: 运行前端契约测试和类型检查。**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_embed_browser_panel_contract.py tests/frontend/test_browser_sse_contract.py -q`

Run: `./frontend/node_modules/.bin/vue-tsc --noEmit`（只做前端类型检查，不启动开发服务。）

Expected: PASS。

## Task 8: 完成端到端回归证据和交付边界

**Files:**
- Modify: `tests/CHECKLIST.md`
- Create: `tests/ai/test_browser_search_flow.py`
- Create: `tests/api/v1/test_browser_security_contract.py`
- Create: `docs/superpowers/specs/2026-08-18-browser-agent-panel-acceptance.md`

- [ ] **Step 1: 写百度搜索编排测试，不依赖真实网络。**

```python
async def test_baidu_search_flow_opens_panel_fills_and_clicks(fake_browser_worker, agent_runner):
    result = await agent_runner.run("打开百度搜索 xxx")
    assert result.browser_events[0]["type"] == "browser_panel_open"
    assert [event["action"] for event in result.browser_events] == ["open", "fill", "click"]
    assert result.final_status == "success"
```

- [ ] **Step 2: 写安全回归测试。**

覆盖用户隔离、Viewer token 过期、私网 URL、密码日志脱敏、guarded 阻断提交、autopilot 放行允许动作、Session 关闭后模式恢复 guarded、断线不创建新 Session。

- [ ] **Step 3: 更新 `tests/CHECKLIST.md`。**

新增“服务端浏览器 Agent 与右侧 BrowserPanel”条目，列出模型、迁移、服务、API、AgentScope、前端契约测试路径，并明确真实登录浏览器验收由用户在启动服务后执行。

- [ ] **Step 4: 运行完整的聚焦验证。**

```bash
pytest \
  tests/test_browser_session_migrations.py \
  tests/services/ai/test_browser_contracts.py \
  tests/services/ai/test_browser_policy.py \
  tests/services/ai/test_browser_worker.py \
  tests/services/ai/test_browser_profile_service.py \
  tests/services/ai/test_browser_session_service.py \
  tests/services/ai/test_browser_tools.py \
  tests/ai/runtime/test_browser_tool_permissions.py \
  tests/ai/runtime/test_browser_agentscope_events.py \
  tests/api/v1/test_browser_sessions.py \
  tests/api/v1/test_browser_security_contract.py \
  -q
pytest --confcutdir=tests/frontend \
  tests/frontend/test_browser_panel_contract.py \
  tests/frontend/test_browser_sse_contract.py \
  tests/frontend/test_embed_browser_panel_contract.py \
  -q
python3 -m compileall -q app
git diff --check
```

Expected: 聚焦后端、前端契约、Python 编译和 diff 检查全部通过；不运行 `./dev.sh`、部署脚本或数据库迁移。

- [ ] **Step 5: 由用户执行真实环境验收。**

用户在控制台启动服务后，使用已登录平台账号验证：打开百度、右侧面板展示、手动登录、Agent 继续搜索、guarded 确认、autopilot 连续执行、关闭后重新打开、跨对话复用 Profile、用户隔离和 WebSocket 断线恢复。Agent 只记录实际完成的测试，不把静态测试描述为真实浏览器验收。

## 计划自检

- 设计文档中的服务端浏览器、用户级 Profile、BrowserPanel、工具协议、SSE 事件、权限开关、安全策略、测试和分阶段交付均有对应任务。
- 计划没有要求直接修改现有网页抓取工具来伪装成浏览器控制能力。
- `ChatCanvas` 与 `BrowserPanel` 保持职责分离；EmbedChat 只负责布局和事件编排。
- 没有使用 `./dev.sh`、部署脚本或数据库执行命令。
- Git stage、commit、push 不属于本计划的自动动作，需用户另行明确授权。
