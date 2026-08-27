import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.agent import ChatConfig
from app.services.ai.dispatcher import AgentDispatcher
from app.services.ai.executors.data_executor import DataQueryExecutor
from app.services.ai.executors.assistant_executor import AssistantExecutor
from app.services.ai.executors.knowledge_executor import KnowledgeExecutor
from app.services.ai.turn_decision import TurnDecision


def _resolved_data_decision() -> TurnDecision:
    return TurnDecision(
        route_status="resolved",
        turn_kind="data_query",
        source="internal_structured_data",
        capability="data_query",
        semantic_domain="chatbi_business_data",
        reference_mode="new_query",
        needs_fresh_data=True,
        allows_data_route=True,
        provenance="router",
    )


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_requires_a_resolved_single_track_decision():
    config = ChatConfig(
        agent_id="sys-agent-chatbi",
        agent_name="chat-bi",
        model_name="test-model",
        temperature=0.0,
        system_prompt="ChatBI",
        tools=["get_dataset_schema", "execute_sql_query"],
        capabilities=["data_query"],
        engine_type="LOCAL",
    )

    with pytest.raises(ValueError, match="resolved TurnDecision"):
        await AgentDispatcher.dispatch(
            config,
            user_query="分析一下",
            messages=[{"role": "user", "content": "分析一下"}],
            trace_id="trace-dispatch-unknown-decision",
            trace_buffer=[],
            turn_decision=TurnDecision(route_status="unknown"),
        )


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_uses_turn_kind_as_the_only_outer_executor_route():
    config = ChatConfig(
        agent_id="sys-agent-chatbi",
        agent_name="chat-bi",
        model_name="test-model",
        temperature=0.0,
        system_prompt="ChatBI",
        tools=["get_dataset_schema", "execute_sql_query"],
        capabilities=["data_query"],
        engine_type="LOCAL",
    )

    executor = await AgentDispatcher.dispatch(
        config,
        user_query="分析一下",
        messages=[{"role": "user", "content": "分析一下"}],
        trace_id="trace-dispatch-single-track",
        trace_buffer=[],
        turn_decision=_resolved_data_decision(),
    )

    assert isinstance(executor, DataQueryExecutor)
    assert executor.turn_decision == _resolved_data_decision()
    assert executor.current_user_query == "分析一下"
    assert not hasattr(executor, "turn_classification")


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_routes_data_capable_agent_to_data_executor_for_non_knowledge_turn():
    """非知识库轮次时，带 data_query 能力的 agent 仍进入 DataQueryExecutor。"""
    config = ChatConfig(
        agent_id="sys-agent-chatbi",
        agent_name="chat-bi",
        agent_version=None,
        model_name="test-model",
        temperature=0.0,
        system_prompt="ChatBI",
        tools=["get_dataset_schema", "execute_sql_query"],
        capabilities=["data_query"],
        engine_type="LOCAL",
    )
    executor = await AgentDispatcher.dispatch(
        config,
        user_query="分析一下",
        messages=[{"role": "user", "content": "分析一下"}],
        trace_id="trace-dispatch-boundary",
        trace_buffer=[],
        turn_decision=_resolved_data_decision(),
    )

    assert isinstance(executor, DataQueryExecutor)
    assert not hasattr(executor, "turn_classification")
    assert executor.turn_decision.reference_mode == "new_query"
    assert executor.turn_decision.capability == "data_query"


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_keeps_chatbi_classification_inside_data_executor():
    config = ChatConfig(
        agent_id="sys-agent-chatbi",
        agent_name="chat-bi",
        agent_version=None,
        model_name="test-model",
        temperature=0.0,
        system_prompt="ChatBI",
        tools=["get_dataset_schema", "execute_sql_query"],
        capabilities=["data_query"],
        engine_type="LOCAL",
    )

    executor = await AgentDispatcher.dispatch(
        config,
        user_query="那本月呢",
        messages=[{"role": "user", "content": "那本月呢"}],
        trace_id="trace-dispatch-no-generic-turn",
        trace_buffer=[],
        turn_decision=_resolved_data_decision(),
    )

    assert isinstance(executor, DataQueryExecutor)


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_reuses_turn_decision_for_general_agent_without_reclassifying():
    config = ChatConfig(
        agent_id="general-agent",
        agent_name="general-chat",
        model_name="test-model",
        temperature=0.0,
        system_prompt="General",
        tools=[],
        capabilities=["general_chat"],
        engine_type="LOCAL",
    )

    executor = await AgentDispatcher.dispatch(
        config,
        user_query="你好",
        messages=[{"role": "user", "content": "你好"}],
        trace_id="trace-dispatch-reuse-turn-decision",
        trace_buffer=[],
        turn_decision=TurnDecision(
            route_status="resolved",
            source="general",
            capability="answer",
            semantic_intent="GENERAL",
            semantic_confidence=0.96,
            provenance="router",
        ),
    )

    assert isinstance(executor, AssistantExecutor)
    assert executor.turn_decision.turn_kind == "general"
    assert executor.turn_decision.semantic_intent == "GENERAL"
    assert executor.current_user_query == "你好"


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_direct_general_decision_defaults_unknown_semantics_to_general_intent():
    config = ChatConfig(
        agent_id="general-agent",
        agent_name="general-chat",
        model_name="test-model",
        temperature=0.0,
        system_prompt="General",
        tools=[],
        capabilities=["general_chat"],
        engine_type="LOCAL",
    )

    executor = await AgentDispatcher.dispatch(
        config,
        user_query="继续",
        messages=[{"role": "user", "content": "继续"}],
        trace_id="trace-dispatch-direct-general",
        trace_buffer=[],
        turn_decision=TurnDecision(
            route_status="resolved",
            source="general",
            capability="answer",
            provenance="direct_agent_selection",
        ),
    )

    assert isinstance(executor, AssistantExecutor)
    assert executor.turn_decision.provenance == "direct_agent_selection"


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_keeps_data_agent_for_ordinary_knowledge_turn():
    """普通知识库粗分类不应抢占 ChatBI，ChatBI 内部流程继续拥有最终控制权。"""
    config = ChatConfig(
        agent_id="sys-agent-chatbi",
        agent_name="chat-bi",
        agent_version=None,
        model_name="test-model",
        temperature=0.0,
        system_prompt="ChatBI",
        tools=["get_dataset_schema", "execute_sql_query"],
        capabilities=["data_query"],
        engine_type="LOCAL",
    )
    executor = await AgentDispatcher.dispatch(
        config,
        user_query="高温告警处理流程是什么",
        messages=[{"role": "user", "content": "高温告警处理流程是什么"}],
        trace_id="trace-dispatch-knowledge",
        trace_buffer=[],
        turn_decision=TurnDecision(
            route_status="resolved",
            turn_kind="knowledge",
            source="internal_docs",
            capability="knowledge_search",
            requires_knowledge_search=True,
        ),
    )

    assert isinstance(executor, AssistantExecutor)


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_allows_explicit_knowledge_context_to_preempt_data_agent():
    """显式知识库上下文仍可让知识库执行器优先处理。"""
    config = ChatConfig(
        agent_id="sys-agent-chatbi",
        agent_name="chat-bi",
        agent_version=None,
        model_name="test-model",
        temperature=0.0,
        system_prompt="ChatBI",
        tools=["get_dataset_schema", "execute_sql_query"],
        capabilities=["data_query"],
        engine_type="LOCAL",
    )
    executor = await AgentDispatcher.dispatch(
        config,
        user_query="按这个知识库回答",
        messages=[{"role": "user", "content": "按这个知识库回答"}],
        trace_id="trace-dispatch-explicit-knowledge",
        trace_buffer=[],
        turn_decision=TurnDecision(
            route_status="resolved",
            turn_kind="knowledge",
            source="internal_docs",
            capability="knowledge_search",
            requires_knowledge_search=True,
            user_action_type="ask_knowledge",
        ),
    )

    assert isinstance(executor, KnowledgeExecutor)
    assert executor.turn_decision.turn_kind == "knowledge"
    assert executor.current_user_query == "按这个知识库回答"


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_allows_explicit_knowledge_context_without_agent_dataset_binding():
    """知识库智能体未配置默认数据集时，用户显式选择仍可进入知识库执行器。"""
    config = ChatConfig(
        agent_id="knowledge-agent",
        agent_name="知识库助手",
        model_name="test-model",
        temperature=0.0,
        system_prompt="Knowledge",
        tools=["search_knowledge_base"],
        capabilities=["knowledge_base"],
        engine_type="LOCAL",
        engine_config={},
    )
    executor = await AgentDispatcher.dispatch(
        config,
        user_query="按这个知识库回答",
        messages=[{"role": "user", "content": "按这个知识库回答"}],
        trace_id="trace-dispatch-explicit-unbound-knowledge",
        trace_buffer=[],
        turn_decision=TurnDecision(
            route_status="resolved",
            turn_kind="knowledge",
            source="internal_docs",
            capability="knowledge_search",
            requires_knowledge_search=True,
            user_action_type="ask_knowledge",
        ),
    )

    assert isinstance(executor, KnowledgeExecutor)
    assert executor.current_user_query == "按这个知识库回答"


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_does_not_route_unbound_general_agent_to_knowledge_executor():
    """意图误判为知识库时，未绑定知识库能力的普通智能体仍走通用执行器。"""
    config = ChatConfig(
        agent_id="general-agent",
        agent_name="主助手",
        agent_version=None,
        model_name="test-model",
        temperature=0.0,
        system_prompt="General",
        tools=[],
        capabilities=["general_chat"],
        engine_config={"dataset_ids": ["user-permitted-dataset"]},
        engine_type="LOCAL",
    )
    executor = await AgentDispatcher.dispatch(
        config,
        user_query="测试一个外部模型的性能",
        messages=[{"role": "user", "content": "测试一个外部模型的性能"}],
        trace_id="trace-dispatch-unbound-knowledge",
        trace_buffer=[],
        turn_decision=TurnDecision(
            route_status="resolved",
            turn_kind="knowledge",
            source="internal_docs",
            capability="knowledge_search",
            requires_knowledge_search=True,
        ),
    )

    assert isinstance(executor, AssistantExecutor)


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_routes_only_fully_bound_knowledge_agent_to_knowledge_executor():
    """知识库执行器需要能力、检索工具和数据集三项绑定同时存在。"""
    config = ChatConfig(
        agent_id="kb-agent",
        agent_name="知识库助手",
        agent_version=None,
        model_name="test-model",
        temperature=0.0,
        system_prompt="Knowledge",
        tools=["search_knowledge_base"],
        capabilities=["knowledge_base"],
        engine_config={"dataset_ids": ["kb-1"]},
        engine_type="LOCAL",
    )
    executor = await AgentDispatcher.dispatch(
        config,
        user_query="操作流程是什么",
        messages=[{"role": "user", "content": "操作流程是什么"}],
        trace_id="trace-dispatch-bound-knowledge",
        trace_buffer=[],
        turn_decision=TurnDecision(
            route_status="resolved",
            turn_kind="knowledge",
            source="internal_docs",
            capability="knowledge_search",
            requires_knowledge_search=True,
        ),
    )

    assert isinstance(executor, KnowledgeExecutor)
    assert executor.current_user_query == "操作流程是什么"
