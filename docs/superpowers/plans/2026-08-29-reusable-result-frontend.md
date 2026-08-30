# 可复用结果前端入口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI 回复和 AI 产物抽屉中展示可复用结果，并支持用户安全选择最近结果用于下一轮分析。

**Architecture:** 后端通过安全摘要接口读取当前会话的 Redis reusable-result current/stack，通过 SSE 告知本轮 saved/reused/fallback 状态；前端不直接访问 Redis。EmbedChat.vue 管理消息状态和一次性选择，MyArtifactsDrawer.vue 负责文件产物与可复用结果的分栏展示，下一次请求携带可选 reusable_result_id，服务端完成归属、过期、类型和刷新意图校验。

**Tech Stack:** FastAPI、Pydantic 2、异步 Redis、pytest、Vue 3、TypeScript、Vite、现有 SSE 解析和 Tailwind CSS。

---

## 文件结构与职责

| 文件 | 职责 |
| --- | --- |
| app/services/ai/reusable_result.py | 统一结果有效性、用户可见摘要和手动选择解析规则 |
| app/api/v1/endpoints/chat.py | 结果列表 API、聊天请求字段和用户会话鉴权 |
| app/services/ai/agent_service.py | 把手动结果 ID 传入 resolver，并产生复用决策 |
| app/services/ai/session_tool_artifact.py | 普通工具/子代理保存后生成状态事件所需摘要 |
| app/services/ai/runners/chatbi/followup_data.py | ChatBI 保存后生成状态事件所需摘要 |
| app/services/ai/runners/assistant_agent_runner.py | 普通助手轮末发送 saved 状态事件 |
| app/services/ai/runners/chatbi/react_stream.py | ChatBI 轮末发送 saved 状态事件 |
| frontend/src/api/artifact.ts | 前端结果列表类型和请求方法 |
| frontend/src/components/embed/ReusableResultList.vue | 可复用结果列表、加载、选择和失效展示 |
| frontend/src/components/chat/ReusableResultStatus.vue | 回复底部 saved/reused/fallback 轻量状态入口 |
| frontend/src/components/embed/MyArtifactsDrawer.vue | 文件产物/可复用结果两个标签的容器 |
| frontend/src/views/EmbedChat.vue | SSE 状态归并、抽屉定位、一次性选择和聊天请求字段 |
| tests/ai/test_reusable_result.py | 摘要序列化、选择解析和安全字段测试 |
| tests/api/v1/test_reusable_result_api.py | 结果列表 API 鉴权、过滤和空/过期数据测试 |
| tests/ai/test_reusable_result_routing.py | 手动结果 ID 与 current/stack/fallback 路由测试 |
| tests/frontend/test_reusable_result_contract.py | 前端组件、请求字段和 SSE 合同测试 |

本计划把后端契约和前端展示作为一个有依赖关系的子项目：后端先提供可验证的安全契约，前端再接入；不拆成两个彼此独立、无法单独验收的计划。

## Task 1: 增加用户可见结果摘要和安全列表接口

**Files:**
- Modify: app/services/ai/reusable_result.py
- Modify: app/api/v1/endpoints/chat.py
- Modify: tests/ai/test_reusable_result.py
- Create: tests/api/v1/test_reusable_result_api.py

- [ ] **Step 1: 先写摘要和 API 的失败测试**

在 tests/ai/test_reusable_result.py 增加：

~~~python
def test_build_reusable_result_client_summary_redacts_internal_fields():
    payload = {
        "result_id": "rr_1",
        "result_type": "data",
        "origin_name": "查数助手",
        "status": "success",
        "text_excerpt": "销售额结果",
        "structured": {"row_count": 20, "columns": ["区域", "销售额"]},
        "tool_args": {"dataset_name": "sales", "access_token": "secret-value"},
    }

    result = build_reusable_result_client_summary(payload, is_current=True)

    assert result["result_id"] == "rr_1"
    assert result["is_current"] is True
    assert result["structured_preview"]["row_count"] == 20
    assert "tool_args" not in result
    assert "access_token" not in json.dumps(result)


def test_build_reusable_result_client_summary_rejects_non_reusable_payload():
    assert build_reusable_result_client_summary({"status": "failed"}, is_current=False) is None
    assert build_reusable_result_client_summary({"result_id": "rr_empty"}, is_current=False) is None
~~~

在 tests/api/v1/test_reusable_result_api.py 覆盖 current/stack 去重、当前用户鉴权、空结果不返回：

~~~python
async def test_list_reusable_results_returns_current_and_deduplicated_stack(client, monkeypatch):
    monkeypatch.setattr(memory_service, "get_reusable_result", AsyncMock(
        return_value={"result_id": "rr_2", "status": "success", "text_excerpt": "new"},
    ))
    monkeypatch.setattr(memory_service, "get_reusable_result_stack", AsyncMock(
        return_value=[
            {"result_id": "rr_1", "status": "success", "text_excerpt": "old"},
            {"result_id": "rr_2", "status": "success", "text_excerpt": "new"},
        ],
    ))

    response = await client.get(
        "/api/v1/chat/reusable-results?conversation_id=conv-1",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert [item["result_id"] for item in items] == ["rr_2", "rr_1"]
    assert items[0]["is_current"] is True


async def test_list_reusable_results_requires_stable_user_identity(client):
    response = await client.get("/api/v1/chat/reusable-results?conversation_id=conv-1")
    assert response.status_code == 401
~~~

- [ ] **Step 2: 运行失败测试，确认缺少摘要函数和 endpoint**

运行：

~~~bash
./.venv/bin/python -m pytest tests/ai/test_reusable_result.py -k client_summary -q
./.venv/bin/python -m pytest tests/api/v1/test_reusable_result_api.py -q
~~~

预期：失败，原因是摘要函数和 GET /api/v1/chat/reusable-results 尚未存在。

- [ ] **Step 3: 实现安全摘要函数**

在 app/services/ai/reusable_result.py 增加：

~~~python
def build_reusable_result_client_summary(
    payload: Mapping[str, Any] | None,
    *,
    is_current: bool = False,
) -> dict[str, Any] | None:
    if not is_reusable_result_candidate(payload):
        return None
    data = dict(payload or {})
    return {
        "result_id": str(data.get("result_id") or ""),
        "result_type": str(data.get("result_type") or "generic"),
        "origin_type": str(data.get("origin_type") or "tool"),
        "origin_name": str(data.get("origin_name") or data.get("tool_name") or "未知来源"),
        "source_type": str(data.get("source_type") or "unknown"),
        "status": str(data.get("status") or "success"),
        "text_excerpt": truncate_client_excerpt(data.get("text_excerpt")),
        "structured_preview": build_structured_preview(data.get("structured")),
        "created_at": data.get("created_at") or data.get("saved_at"),
        "expires_at": data.get("expires_at"),
        "is_current": bool(is_current),
    }
~~~

实现摘要依赖的两个纯函数也放在 reusable_result.py 中，避免 endpoint 自己拼接或泄漏字段：

~~~python
def truncate_client_excerpt(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 16] + "... [已截断]"


def build_structured_preview(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    preview: dict[str, Any] = {}
    for key in ("row_count", "total_row_count", "item_count", "columns"):
        item = value.get(key)
        if key == "columns" and isinstance(item, list):
            preview[key] = [str(column)[:80] for column in item[:30]]
        elif isinstance(item, (str, int, float, bool)):
            preview[key] = item
    return preview or None


def build_reusable_result_status_event(
    *,
    status: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    summary = build_reusable_result_client_summary(payload, is_current=status == "saved") or {}
    return {
        "type": "reusable_result_status",
        "status": status,
        **{
            key: summary[key]
            for key in ("result_id", "result_type", "origin_name", "created_at", "expires_at")
            if summary.get(key) is not None
        },
    }
~~~

摘要只保留行数、列名、条目数等有限字段，并限制字符串和 JSON 大小；不得复制 tool_args、凭证、Redis key 或完整 payload。

- [ ] **Step 4: 实现会话级列表 endpoint**

在 app/api/v1/endpoints/chat.py 复用 _require_chat_user_id，新增 response model 和 endpoint。核心逻辑必须是：

~~~python
current = await memory_service.get_reusable_result(user_id, conversation_id)
stack = await memory_service.get_reusable_result_stack(user_id, conversation_id)

items = []
seen = set()
for payload, is_current in [(current, True), *[(item, False) for item in reversed(stack)]]:
    summary = build_reusable_result_client_summary(payload, is_current=is_current)
    result_id = summary.get("result_id") if summary else ""
    if summary and result_id and result_id not in seen:
        seen.add(result_id)
        items.append(ReusableResultListItem(**summary))

return StandardResponse(
    data=ListResponse(items=items[:10], total=len(items[:10]), page=1, page_size=10)
)
~~~

endpoint 使用当前登录用户和 conversation_id 读取 Redis；Redis 异常沿用 fail-safe 约定，记录 warning 后返回空列表，不能阻断聊天页面或文件产物列表。

- [ ] **Step 5: 运行测试确认通过**

~~~bash
./.venv/bin/python -m pytest tests/ai/test_reusable_result.py tests/api/v1/test_reusable_result_api.py -q
~~~

预期：新增摘要和列表接口测试全部通过。

## Task 2: 接入用户手动选择的结果 ID

**Files:**
- Modify: app/api/v1/endpoints/chat.py
- Modify: app/services/ai/reusable_result.py
- Modify: app/services/ai/agent_service.py
- Modify: tests/ai/test_reusable_result_routing.py
- Modify: tests/api/v1/test_reusable_result_api.py

- [ ] **Step 1: 先写 preferred result routing 失败测试**

增加：

~~~python
def test_resolve_reusable_result_prefers_valid_selected_stack_item():
    selected = {"result_id": "rr_old", "status": "success", "text_excerpt": "old result"}
    current = {"result_id": "rr_new", "status": "success", "text_excerpt": "new result"}

    decision = resolve_reusable_result(
        "请继续分析",
        current=current,
        stack=[selected, current],
        preferred_result_id="rr_old",
    )

    assert decision.mode == "reuse"
    assert decision.result["result_id"] == "rr_old"


def test_resolve_reusable_result_ignores_invalid_selected_id():
    decision = resolve_reusable_result(
        "查询本周订单",
        current=None,
        stack=[],
        preferred_result_id="rr_missing",
    )
    assert decision.mode == "none"
~~~

API 测试还要断言 ChatCompletionRequest 接受可选 reusable_result_id，并拒绝超过 128 个字符的 ID。

- [ ] **Step 2: 运行失败测试**

~~~bash
./.venv/bin/python -m pytest tests/ai/test_reusable_result_routing.py -k preferred -q
~~~

预期：失败，因为 resolver 尚未接受 preferred_result_id。

- [ ] **Step 3: 扩展 resolver 和 AgentService 参数链**

将 resolver 签名扩展为：

~~~python
def resolve_reusable_result(
    user_query: str,
    *,
    current: Mapping[str, Any] | None,
    stack: Sequence[Mapping[str, Any]] | None,
    preferred_result_id: str | None = None,
) -> ReusableResultDecision:
~~~

当 preferred_result_id 非空时，只在 current/stack 中找到同 ID 且通过 is_reusable_result_candidate 的真实 Redis 结果才使用；不存在或无效时回到正常自动解析，不信任客户端传来的 payload。

在 ChatCompletionRequest 增加：

~~~python
reusable_result_id: Optional[str] = Field(
    default=None,
    max_length=128,
    description="用户明确选择用于下一轮分析的会话结果 ID",
)
~~~

沿 create_chat_completion → AgentService.chat_completion_stream/chat_completion → _run_chat_turn_stream → _resolve_reusable_result_decision 传递该 ID。

- [ ] **Step 4: 保留刷新意图和结果类型的服务端否决权**

确保 resolver 在“最新、实时、刷新、重新查询”意图下清除 preferred_result_id，并继续执行现有 query/type 判断。手动选择不能让刷新请求变成旧结果复用。

- [ ] **Step 5: 运行路由回归测试**

~~~bash
./.venv/bin/python -m pytest tests/ai/test_reusable_result_routing.py tests/ai/test_turn_decision.py -q
~~~

预期：preferred、current/stack/fallback、刷新绕过和原有 TurnDecision 测试全部通过。

## Task 3: 发出 saved/reused/fallback SSE 状态事件

**Files:**
- Modify: app/services/ai/session_tool_artifact.py
- Modify: app/services/ai/runners/chatbi/followup_data.py
- Modify: app/services/ai/runners/assistant_agent_runner.py
- Modify: app/services/ai/runners/chatbi/react_stream.py
- Modify: app/services/ai/agent_service.py
- Modify: tests/ai/runners/test_assistant_agent_reusable_result.py
- Modify: tests/ai/test_chatbi_result_stack.py

- [ ] **Step 1: 先写状态事件失败测试**

普通助手和 ChatBI 成功保存后必须产生安全事件：

~~~python
assert {
    "type": "reusable_result_status",
    "status": "saved",
    "result_id": "rr_1",
    "result_type": "data",
}.items() <= event.items()
assert "tool_args" not in event
assert "structured" not in event
~~~

失败、空结果、取消不能产生 status == saved。

- [ ] **Step 2: 运行失败测试**

~~~bash
./.venv/bin/python -m pytest tests/ai/runners/test_assistant_agent_reusable_result.py tests/ai/test_chatbi_result_stack.py -k status -q
~~~

预期：失败，因为当前 runner 只保存 Redis，不发送状态事件。

- [ ] **Step 3: 让保存函数返回安全状态摘要**

把 persist_turn_artifact_candidate 和 save_last_data_result_for_followups 的返回值从 None 扩展为 Optional[Dict[str, Any]]：

~~~python
return build_reusable_result_client_summary(payload, is_current=True)
~~~

保存失败、空结果、取消或没有 conversation_id 时返回 None；返回值只作为当前 SSE 事件输入，不改变 Redis payload。

- [ ] **Step 4: 在 runner 保存后发送 saved 事件**

普通助手和 ChatBI 保存调用改为：

~~~python
saved_meta = await persist_turn_artifact_candidate(...)
if saved_meta:
    yield build_reusable_result_status_event(status="saved", payload=saved_meta)
~~~

两条执行链使用同一个事件构造函数，确保字段一致。

- [ ] **Step 5: 在 AgentService 解析后发送 reused/fallback 事件**

在 resolver 之后把状态放入 shared_state，并在本轮执行开始前发送：

~~~python
if reusable_result_decision.mode == "reuse":
    yield build_reusable_result_status_event(status="reused", payload=reusable_result_decision.result)
elif reusable_result_decision.mode == "fallback":
    yield build_reusable_result_status_event(status="fallback")
~~~

事件只带 result_id/result_type/origin_name/created_at/expires_at 等安全字段；fallback 不携带旧结果正文。Resolver 异常时不伪造 saved/reused 状态。

- [ ] **Step 6: 运行事件回归测试**

~~~bash
./.venv/bin/python -m pytest tests/ai/runners/test_assistant_agent_reusable_result.py tests/ai/test_chatbi_result_stack.py tests/ai/test_reusable_result.py -q
~~~

## Task 4: 增加前端 API 类型和可复用结果列表组件

**Files:**
- Modify: frontend/src/api/artifact.ts
- Create: frontend/src/components/embed/ReusableResultList.vue
- Create: tests/frontend/test_reusable_result_contract.py

- [ ] **Step 1: 先写前端合同失败测试**

~~~python
def test_reusable_result_api_and_component_contract():
    api = Path("frontend/src/api/artifact.ts").read_text()
    component = Path("frontend/src/components/embed/ReusableResultList.vue").read_text()
    assert "ReusableResultListItem" in api
    assert "reusableResults" in api
    assert "/api/v1/chat/reusable-results" in api
    assert "用于下一轮分析" in component
    assert "结果已失效" in component
~~~

- [ ] **Step 2: 实现 API 类型和方法**

在 artifact.ts 增加：

~~~typescript
export interface ReusableResultListItem {
  result_id: string
  result_type: string
  origin_type: string
  origin_name: string
  source_type: string
  status: string
  text_excerpt: string
  structured_preview?: Record<string, unknown> | null
  created_at?: string | null
  expires_at?: string | null
  is_current: boolean
}

export interface ReusableResultListResponse {
  items: ReusableResultListItem[]
  total: number
  page: number
  page_size: number
}

reusableResults: (conversationId: string) =>
  axios.get<StandardResponse<ReusableResultListResponse>>(
    '/api/v1/chat/reusable-results',
    { params: { conversation_id: conversationId } },
  ),
~~~

- [ ] **Step 3: 实现 ReusableResultList.vue**

组件 props/emits 固定为：

~~~typescript
const props = defineProps<{
  conversationId: string
  selectedResultId?: string
}>()
const emit = defineEmits<{
  (event: 'select', item: ReusableResultListItem): void
}>()
~~~

组件负责加载、空态、错误重试、过期态、current 标识、摘要截断、结果类型/来源/时间格式化和“用于下一轮分析”事件；不负责发送聊天请求，不直接访问 Redis，不显示内部字段。

- [ ] **Step 4: 运行前端合同测试**

~~~bash
./.venv/bin/python -m pytest tests/frontend/test_reusable_result_contract.py -q
~~~

## Task 5: 改造 AI 产物抽屉并接入回复状态

**Files:**
- Modify: frontend/src/components/embed/MyArtifactsDrawer.vue
- Create: frontend/src/components/chat/ReusableResultStatus.vue
- Modify: frontend/src/views/EmbedChat.vue
- Modify: tests/frontend/test_reusable_result_contract.py
- Modify: tests/frontend/test_general_message_continue_analysis_contract.py

- [ ] **Step 1: 先补充 UI 合同测试**

~~~python
drawer = Path("frontend/src/components/embed/MyArtifactsDrawer.vue").read_text()
view = Path("frontend/src/views/EmbedChat.vue").read_text()
status = Path("frontend/src/components/chat/ReusableResultStatus.vue").read_text()
assert "文件产物" in drawer
assert "可复用结果" in drawer
assert "已保存，可复用" in status
assert "已复用上一结果" in status
assert "selectedReusableResultId" in view
assert "reusable_result_id" in view
~~~

- [ ] **Step 2: 在抽屉中增加文件/结果标签**

MyArtifactsDrawer.vue 保留现有文件列表、分页、类型过滤和下载方法，只增加：

~~~typescript
type ArtifactTab = 'files' | 'reusable'
const activeTab = ref<ArtifactTab>('files')
~~~

模板将现有文件区域放到 activeTab === 'files' 下，将 ReusableResultList 放到 activeTab === 'reusable' 下。抽屉接收 initialTab、conversationId、selectedResultId，打开时刷新对应内容；文件 API 行为不变。

- [ ] **Step 3: 增加回复底部状态组件**

ReusableResultStatus.vue 只接受安全状态和结果 ID：

~~~typescript
type ReusableResultStatus = 'saved' | 'reused' | 'fallback'
const emit = defineEmits<{
  (event: 'open', resultId?: string): void
}>()
~~~

saved 点击打开抽屉并定位，reused 可以打开结果详情，fallback 只做低强调提示或不显示；组件不能自动发送查询。

- [ ] **Step 4: 在 EmbedChat 中归并 SSE 事件并管理一次性选择**

扩展 Message：

~~~typescript
reusableResultStatus?: {
  status: 'saved' | 'reused' | 'fallback'
  result_id?: string
  result_type?: string
  origin_name?: string
  created_at?: string | null
  expires_at?: string | null
}
~~~

处理 data.type === 'reusable_result_status' 时，只把允许字段写入当前 agentMsg。增加 selectedReusableResultId、showMyArtifactsTab、focusedReusableResultId 三个状态。openReusableResult(resultId) 负责打开抽屉、切到 reusable tab 和定位；selectReusableResult(item) 只设置 selectedReusableResultId，不调用 sendMessage。

- [ ] **Step 5: 将选择 ID 只注入下一次请求**

扩展 ChatSendSnapshot 和 body：

~~~typescript
interface ChatSendSnapshot {
  content: string
  files: ChatFile[]
  clientRequestId: string
  groundingAction?: Record<string, unknown>
  reusableResultId?: string
}

const captureSendSnapshot = (overrides: ChatSendOverrides = {}): ChatSendSnapshot => ({
  // 保留现有字段
  reusableResultId: selectedReusableResultId.value || undefined,
})
~~~

sendMessageInternal 组装 body 时仅当 snapshot 有值才加入 body.reusable_result_id；请求开始后立即清除 selectedReusableResultId，确保只消费一次。显式刷新/最新动作创建 snapshot 时置空，并清除输入区选择提示。

- [ ] **Step 6: 运行前端合同和快捷按钮测试**

~~~bash
./.venv/bin/python -m pytest tests/frontend/test_reusable_result_contract.py tests/frontend/test_general_message_continue_analysis_contract.py -q
~~~

## Task 6: 完善失效处理并做全量回归

**Files:**
- Modify: frontend/src/components/embed/ReusableResultList.vue
- Modify: frontend/src/components/embed/MyArtifactsDrawer.vue
- Modify: frontend/src/views/EmbedChat.vue
- Modify: app/services/ai/reusable_result.py
- Modify: tests/ai/test_reusable_result_routing.py
- Modify: tests/frontend/test_reusable_result_contract.py

- [ ] **Step 1: 添加后端过期/归属和前端空态测试**

后端覆盖选择 ID 不在当前用户/会话 stack、结果过期、空 payload、刷新意图；前端覆盖列表为空、接口错误、过期项禁用“用于下一轮分析”、关闭后重新打开能刷新。

- [ ] **Step 2: 固化边界行为**

确保选择旧结果不会改写 current；选择只进入下一条请求且发送后清空；MessageArtifactsDrawer 仍只加载文件；文件 tab 原有下载分页不变；未知/缺失 SSE 字段不显示“已保存”；摘要按纯文本渲染，不使用 HTML 注入。

- [ ] **Step 3: 运行后端聚焦回归**

~~~bash
./.venv/bin/python -m pytest \
  tests/ai/test_reusable_result.py \
  tests/ai/test_reusable_result_routing.py \
  tests/ai/test_session_tool_artifact.py \
  tests/ai/test_chatbi_result_stack.py \
  tests/ai/runners/test_assistant_agent_reusable_result.py \
  tests/ai/runners/test_data_agent_runner.py \
  tests/ai/test_prompt_assembler.py \
  tests/ai/test_sub_agent_delegation.py \
  tests/api/v1/test_chat_artifacts.py -q
~~~

预期：旧 last_data_result、legacy session artifact、快捷按钮、文件产物和 Redis fail-safe 回归通过。

- [ ] **Step 4: 运行前端类型和合同检查**

~~~bash
frontend/./node_modules/.bin/vue-tsc --noEmit
./.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend -q
~~~

若环境缺少前端依赖，应记录为环境阻塞，不修改业务代码绕过检查。

## Task 7: 更新清单并准备真实验收

**Files:**
- Modify: tests/CHECKLIST.md
- Modify: docs/superpowers/specs/2026-08-29-reusable-result-frontend-design.md（仅在实现导致契约澄清时同步）

- [ ] **Step 1: 更新测试清单**

增加“可复用结果前端入口”条目，列出后端 endpoint、SSE event、MyArtifactsDrawer.vue、ReusableResultList.vue、ReusableResultStatus.vue 和对应测试文件，并注明静态/契约测试覆盖范围。

- [ ] **Step 2: 做变更范围和格式检查**

~~~bash
git diff --check
git status --short
git diff --stat
~~~

确认不修改 router_service.py、数据库迁移或无关页面；不自动 stage 或 commit。

- [ ] **Step 3: 用户启动服务后做真实验收**

由用户在控制台自行启动服务，依次验证：

1. 执行普通工具或 ChatBI 查询，回复底部显示“已保存，可复用”。
2. 打开“AI 产物”，切换“可复用结果”，看到 current 和最近结果。
3. 点击旧结果“用于下一轮分析”，输入区出现一次性选择提示。
4. 发送“继续分析”，确认复用所选结果，不重复执行原查询。
5. 再发普通新查询，确认旧选择没有继续携带。
6. 点击“最新/刷新/重新查询”，确认绕过缓存。
7. 结果过期或清理后重试，确认回退原有查询。
8. 验证文件产物 tab、消息级文件产物按钮和现有快捷按钮不变。

## 完成标准

- 用户能在回复底部看到本轮保存/复用状态。
- AI 产物抽屉能区分文件产物和可复用结果。
- current 和最近结果可安全读取，最近结果可手动选择一次。
- 手动选择不会覆盖 current，不会跨会话或跨用户读取。
- 失败、空结果、过期、刷新意图和 Redis 故障均安全降级。
- 后端聚焦测试、前端合同测试和 TypeScript 检查通过；真实 Redis/浏览器验收由用户完成。
