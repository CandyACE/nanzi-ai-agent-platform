# 自动委派默认 Main Implementation Plan

> **For agentic workers:** 本计划按 TDD 执行；每个任务先写一个会失败的测试，再实现最小改动并运行定向回归。仓库约定禁止自动提交和启动服务，因此不包含自动 `git commit` 或 `./dev.sh` 步骤。

**Goal:** 将无专家请求统一交给固定 Main，由 Main 自动回答或委派子智能体，并同步更新界面文案及 Main 的禁用/删除保护。

**Architecture:** `AgentContextManager` 负责在没有显式专家时按固定 Main ID/slug 解析配置并生成 `automatic_delegation` 决策，`AgentService` 和 `AssistantRunner` 继续消费同一决策。显式专家分支保留 `direct_agent_selection`；管理 API 在服务层拒绝 Main 的禁用和删除，Vue 页面隐藏对应操作。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、Pydantic、pytest、Vue 3、TypeScript、Vite、前端源码契约测试。

---

### Task 1: 默认 Main 决策与解析

**Files:**
- Modify: `app/services/ai/turn_decision.py`
- Modify: `app/services/ai/context_manager.py`
- Test: `tests/ai/test_turn_decision.py`
- Test: `tests/services/ai/test_agent_context_manager.py`

- [x] **Step 1: 写默认 Main 决策失败测试**

在 `tests/ai/test_turn_decision.py` 增加：

```python
def test_default_main_delegation_is_not_explicit_selection():
    config = SimpleNamespace(
        agent_id="sys-agent-chat",
        agent_name="main",
        agent_display_name="主助手(Main)",
        capabilities=["general_chat", "coding"],
    )

    decision = TurnDecision.for_default_main_delegation(config)

    assert decision.route_status == "resolved"
    assert decision.turn_kind == "general"
    assert decision.source == "general"
    assert decision.capability == "answer"
    assert decision.provenance == "automatic_delegation"
    assert decision.fast_path == "default_main"
    assert decision.evidence == ["default_main_agent"]
```

在 `tests/services/ai/test_agent_context_manager.py` 增加：

```python
@pytest.mark.asyncio
async def test_resolve_without_explicit_agent_uses_main_without_router():
    main_config = ChatConfig(
        agent_id="sys-agent-chat",
        agent_name="main",
        model_name="DeepSeek",
        temperature=0.7,
        system_prompt="main prompt",
        tools=[],
        capabilities=["general_chat"],
    )
    session_context = MagicMock()
    session_context.__aenter__.return_value = AsyncMock()

    with patch(
        "app.services.ai.context_manager.AsyncSessionLocal",
        return_value=session_context,
    ), patch(
        "app.services.ai.context_manager.AgentManagerService.get_active_agent_config",
        new_callable=AsyncMock,
        return_value=main_config,
    ) as get_config, patch(
        "app.services.ai.context_manager.router_service.route_query",
        new_callable=AsyncMock,
    ) as route_query:
        config, decision = await AgentContextManager.resolve_agent_config(
            messages=[{"role": "user", "content": "你好"}],
            user_info=None,
        )

    assert config is main_config
    assert decision.provenance == "automatic_delegation"
    assert decision.agent_id == "sys-agent-chat"
    get_config.assert_awaited_once()
    route_query.assert_not_awaited()
```

- [x] **Step 2: 运行失败测试确认缺口**

运行：

```bash
venv/bin/python -m pytest tests/ai/test_turn_decision.py::test_default_main_delegation_is_not_explicit_selection tests/services/ai/test_agent_context_manager.py::test_resolve_without_explicit_agent_uses_main_without_router -q
```

预期：失败，原因是默认 Main 决策工厂和无专家直达解析尚未实现，而不是测试收集错误。

- [x] **Step 3: 实现最小默认 Main 解析**

在 `TurnDecision` 增加 `for_default_main_delegation()`，字段固定为 `resolved/general/answer/automatic_delegation/default_main`。在 `AgentContextManager.resolve_agent_config()` 的无显式参数分支中按以下顺序加载：

```python
for fallback_name in ("main", "assistant", "general-chat"):
    agent_config = await AgentManagerService.get_active_agent_config(
        session, agent_name=fallback_name
    )
    if agent_config:
        route_details = TurnDecision.for_default_main_delegation(agent_config)
        break
```

保留现有合成通用配置兜底；删除该分支对 `router_service.route_query()` 和 `force_data_query` 的调用，但不修改显式 `version_id`、`agent_id`、`agent_name` 分支。`metadata_dataset_ids` 仍由后续 `setup_context()` 写入 `AgentContext`。

- [x] **Step 4: 运行测试确认通过**

运行同一条定向命令，预期两个测试均 PASS；再运行：

```bash
venv/bin/python -m pytest tests/ai/test_turn_decision.py tests/services/ai/test_agent_context_manager.py -q
```

预期：既有显式选择和上下文测试保持 PASS。

### Task 2: 默认决策的 AgentService/Runner 语义

**Files:**
- Modify: `app/services/ai/agent_service.py`
- Test: `tests/services/ai/test_agent_service_skill_hint.py` 或新增 `tests/services/ai/test_agent_service_default_main.py`
- Test: `tests/ai/runners/test_assistant_agent_data_guard.py`

- [x] **Step 1: 写默认 Main 不产生 Router 日志的失败测试**

以现有 `_run_chat_turn_stream` 测试夹具为基础，mock `_start_route_resolution` 返回 `(main_config, automatic_delegation_decision, 0.0, None)`，消费生成器事件并断言：

```python
assert not any(event.get("type") == "router_log" for event in events)
assert any(event.get("type") == "meta" for event in events)
```

同时增加 Runner 决策断言，证明默认决策不被 `_is_direct_agent_selection()` 识别为显式专家：

```python
runner = AssistantAgentRunner(config=main_config, turn_decision=decision, ...)
assert runner._is_direct_agent_selection() is False
```

- [x] **Step 2: 运行失败测试确认日志条件仍过宽**

运行新增定向测试，预期当前 `route_details` 非空时仍发送 `router_log`，因此测试失败在“出现了 Router 日志”断言。

- [x] **Step 3: 仅对真实 Router 决策发送 router_log**

在 `AgentService._run_chat_turn_stream()` 的日志分支增加来源门槛：

```python
if route_details and route_details.provenance == "router":
    yield {"type": "router_log", ...}
```

默认 Main 的决策仍保留在 `turn_decision` 和 trace 中，但不生成 Router UI 事件。`AssistantRunner._resolve_grounding_request_decision()` 继续从 `source=general` 回到 `resolve_request_decision(user_query)`，让 Main 根据当前问题触发现有知识库/ChatBI/显式子智能体委派引导；不新增第二次 LLM Router。

- [x] **Step 4: 运行测试确认通过**

运行新增测试、Main Guard 测试和现有 AgentService 定向测试，预期 PASS；确认显式专家仍使用 `direct_agent_selection` 且没有被改成默认委派。

### Task 3: Main 禁止禁用和删除的后端保护

**Files:**
- Modify: `app/services/ai/agent_manager.py`
- Modify: `app/api/portal/endpoints/agents.py`（仅在需要返回明确错误信息时修改）
- Test: `tests/services/ai/test_agent_manager.py`
- Test: `tests/api/portal/test_agent_management.py`

- [x] **Step 1: 写服务层失败测试**

在 `tests/services/ai/test_agent_manager.py` 增加：

```python
@pytest.mark.asyncio
async def test_update_main_rejects_disabling_even_for_admin(mock_session, mock_user_admin):
    main_agent = AIAgent(
        id="sys-agent-chat",
        name="main",
        display_name="主助手(Main)",
        is_system=True,
        is_enabled=True,
        engine_type="LOCAL",
    )
    mock_session.get.return_value = main_agent

    with pytest.raises(ValueError, match="主助手不可禁用"):
        await AgentManagerService.update_agent(
            mock_session,
            "sys-agent-chat",
            AIAgentBase(
                name="main",
                display_name="主助手(Main)",
                is_enabled=False,
            ),
            mock_user_admin,
        )

    assert main_agent.is_enabled is True
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_main_is_rejected_without_deleting(mock_session, mock_user_admin):
    main_agent = AIAgent(
        id="sys-agent-chat",
        name="main",
        display_name="主助手(Main)",
        is_system=True,
        is_enabled=True,
    )
    mock_session.get.return_value = main_agent

    assert await AgentManagerService.delete_agent(
        mock_session, "sys-agent-chat", user=mock_user_admin
    ) is False
    mock_session.delete.assert_not_called()
    mock_session.commit.assert_not_called()
```

- [x] **Step 2: 运行失败测试确认保护缺口**

运行：

```bash
venv/bin/python -m pytest tests/services/ai/test_agent_manager.py::test_update_main_rejects_disabling_even_for_admin tests/services/ai/test_agent_manager.py::test_delete_main_is_rejected_without_deleting -q
```

预期：禁用测试当前会成功修改对象并提交；删除测试当前会先因 `is_system` 返回 False，需补充稳定 Main 语义断言及明确保护代码。

- [x] **Step 3: 实现稳定 ID/兼容 slug 保护**

在 `agent_manager.py` 增加仅针对数据库模型的内部判断：稳定 ID `sys-agent-chat` 或名称 `main`、`assistant`、`general-chat` 命中固定主专家。

在 `update_agent()` 修改 `agent.is_enabled` 前拒绝 `False`：

```python
if is_main_agent and data.is_enabled is False:
    raise ValueError("主助手不可禁用")
```

在 `delete_agent()` 删除前直接返回 False。保留普通自定义智能体的更新和删除行为；不把 Main 标记为不可编辑，以便继续配置、更新版本和发布。

- [x] **Step 4: 运行服务层与 API 定向测试**

运行：

```bash
venv/bin/python -m pytest tests/services/ai/test_agent_manager.py tests/api/portal/test_agent_management.py -q
```

预期：Main 的禁用/删除均被拒绝，既有普通智能体 CRUD 测试保持 PASS。若 API 测试环境缺少数据库或 Redis，只记录为环境阻塞，不启动服务脚本替代验证。

### Task 4: 设置页与智能体管理页文案和操作保护

**Files:**
- Modify: `frontend/src/components/embed/ChatSettings.vue`
- Modify: `frontend/src/views/AgentManagement.vue`
- Test: `tests/frontend/test_embed_routing_preference_contract.py`
- Test: `tests/frontend/test_agent_type_form_contract.py`

- [x] **Step 1: 写前端契约失败测试**

更新 `test_settings_has_auto_and_default_agent_tabs()` 与 `test_routing_mode_help_text_explains_latency_and_delegation()`，断言 `ChatSettings.vue` 包含：

```python
assert "主专家自动委派" in source
assert "未指定专家时，默认由主专家直接回答，或按任务需要自动委派其他智能体" in source
assert "先识别问题意图，再选择合适的主智能体" not in source
assert "可能增加一次路由判断耗时" not in source
```

在 AgentManagement 契约测试中断言：

```python
assert "isMainAgent" in management
assert "主助手不可禁用" in management
assert "主专家自动委派" in management
```

- [x] **Step 2: 运行失败契约测试**

运行：

```bash
venv/bin/python -m pytest tests/frontend/test_embed_routing_preference_contract.py tests/frontend/test_agent_type_form_contract.py -q
```

预期：旧的“自动路由”文案断言或新的 Main 保护断言失败，证明契约覆盖了本次修改。

- [x] **Step 3: 实现界面文案和 Main 操作保护**

在 `ChatSettings.vue` 将模式标题和说明替换为：

```html
主专家自动委派
未指定专家时，默认由主专家直接回答，或按任务需要自动委派其他智能体，统一流程并减少额外判断耗时。
```

在 `AgentManagement.vue`：

- 增加 `isMainAgent(agent)`，按 `agent.id === "sys-agent-chat"` 或名称别名判断。
- Main 的状态位置显示“主助手 / 固定启用”，不渲染禁用开关。
- 删除按钮增加 `!isMainAgent(agent)` 条件。
- 批量选择和 `batchSetEnabled()` 排除 Main。
- `handleDeleteAgent()` 与 `toggleAgentStatus()` 保留运行时防护提示。
- 将帮助面板、发布确认、字段 placeholder 和外部引擎说明中的旧“自动路由”语义改为“主专家自动委派”。

- [x] **Step 4: 运行前端契约测试和静态类型检查**

运行：

```bash
venv/bin/python -m pytest tests/frontend/test_embed_routing_preference_contract.py tests/frontend/test_agent_type_form_contract.py -q
cd frontend && ./node_modules/.bin/vue-tsc --noEmit
```

预期：契约测试和类型检查 PASS；不启动 Vite 开发服务。

### Task 4A: 普通 EmbedChat 首次加载保持自动委派

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue:4292-4308`
- Test: `tests/frontend/test_embed_routing_preference_contract.py`
- Modify: `docs/superpowers/specs/2026-08-27-automatic-delegation-default-main-design.md`

- [x] **Step 1: 将未配置偏好的契约改为禁止自动选中 Main**

断言未配置路由偏好时不会查找或填充 `main`，而是保留 `config.routingMode="auto"` 和空 `config.expertAgentId`。

- [x] **Step 2: 运行 RED 测试**

运行：

```bash
venv/bin/python -m pytest -q tests/frontend/test_embed_routing_preference_contract.py::test_unconfigured_routing_defaults_to_auto_without_selecting_main
```

预期：旧实现因仍存在 `mainAgent` 自动选中分支而失败。

- [x] **Step 3: 删除未配置时的 Main 自动填充分支**

保留已保存专家偏好、已保存自动委派偏好以及集成锁定专家的原有逻辑；未配置时直接执行已有 `auto` 兜底分支。

- [x] **Step 4: 运行 GREEN 测试**

同一条定向命令应通过，且普通请求继续由后端无有效专家参数解析为 Main 的 `automatic_delegation`。

### Task 5: 全部定向回归与交付检查

**Files:**
- Modify: `docs/superpowers/specs/2026-08-27-automatic-delegation-default-main-design.md`
- Modify: `docs/superpowers/plans/2026-08-27-automatic-delegation-default-main-plan.md`
- Test: `tests/ai/test_turn_decision.py`
- Test: `tests/services/ai/test_agent_context_manager.py`
- Test: `tests/services/ai/test_agent_manager.py`
- Test: `tests/frontend/test_embed_routing_preference_contract.py`
- Test: `tests/frontend/test_agent_type_form_contract.py`

- [x] **Step 1: 运行后端组合回归**

运行：

```bash
venv/bin/python -m pytest tests/ai/test_turn_decision.py tests/services/ai/test_agent_context_manager.py tests/services/ai/test_agent_manager.py tests/ai/runners/test_assistant_agent_data_guard.py -q
```

预期：与本次决策、默认 Main、Main 保护和 Guard 相关的测试全部 PASS。

- [x] **Step 2: 运行前端组合回归**

运行：

```bash
venv/bin/python -m pytest tests/frontend/test_embed_routing_preference_contract.py tests/frontend/test_agent_type_form_contract.py -q
cd frontend && ./node_modules/.bin/vue-tsc --noEmit
```

预期：前端源码契约和 TypeScript 检查全部 PASS。

- [x] **Step 3: 检查变更范围和空白**

运行：

```bash
git status --short
git diff --check
git diff --stat
```

预期：只包含本需求的后端、前端、测试、设计和计划文件；不自动 stage/commit，不执行 `./dev.sh`、部署脚本或生产数据库操作。

- [x] **Step 4: 汇报验收边界**

最终报告明确列出：默认 Main 无 Router LLM 的静态测试证据、显式专家保持不变的测试证据、Main API 禁用/删除保护、前端契约与类型检查结果，以及未执行的真实服务/浏览器/数据库环境验收。
