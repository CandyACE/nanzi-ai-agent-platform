import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.agent import ChatConfig
from app.services.ai.dispatcher import AgentDispatcher
from app.services.ai.executors.data_executor import DataQueryExecutor
from app.services.ai.executors.assistant_executor import AssistantExecutor
from app.services.ai.executors.knowledge_executor import KnowledgeExecutor
from app.services.ai.intent_service import IntentType
from app.services.ai.turn_classifier import TurnClassification, TurnType


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
    shared_turn = (
        TurnClassification(
            turn_type=TurnType.GENERAL,
            reasoning="外部粗分类不应决定 ChatBI 内部执行器",
            intent=IntentType.GENERAL,
        ),
        None,
        0.0,
    )

    executor = await AgentDispatcher.dispatch(
        config,
        user_query="分析一下",
        messages=[{"role": "user", "content": "分析一下"}],
        trace_id="trace-dispatch-boundary",
        trace_buffer=[],
        shared_turn=shared_turn,
        route_hints={
            "semantic_domain": "chatbi_business_data",
            "reference_mode": "new_query",
            "needs_fresh_data": True,
        },
    )

    assert isinstance(executor, DataQueryExecutor)
    assert not hasattr(executor, "turn_classification")
    assert executor.route_hints["reference_mode"] == "new_query"


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_dispatcher_does_not_run_generic_turn_classifier_for_data_agent_without_shared_turn():
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

    with patch(
        "app.services.ai.dispatcher.resolve_turn_for_session",
        AsyncMock(side_effect=AssertionError("DataQueryExecutor owns ChatBI turn classification")),
    ):
        executor = await AgentDispatcher.dispatch(
            config,
            user_query="那本月呢",
            messages=[{"role": "user", "content": "那本月呢"}],
            trace_id="trace-dispatch-no-generic-turn",
            trace_buffer=[],
        )

    assert isinstance(executor, DataQueryExecutor)


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
    shared_turn = (
        TurnClassification(
            turn_type=TurnType.KNOWLEDGE,
            reasoning="SOP 问答",
            requires_knowledge_search=True,
            intent=IntentType.KNOWLEDGE_BASE,
        ),
        None,
        0.0,
    )

    executor = await AgentDispatcher.dispatch(
        config,
        user_query="高温告警处理流程是什么",
        messages=[{"role": "user", "content": "高温告警处理流程是什么"}],
        trace_id="trace-dispatch-knowledge",
        trace_buffer=[],
        shared_turn=shared_turn,
    )

    assert isinstance(executor, DataQueryExecutor)


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
    shared_turn = (
        TurnClassification(
            turn_type=TurnType.KNOWLEDGE,
            reasoning="用户显式选择了知识库上下文",
            requires_knowledge_search=True,
            knowledge_preemption_allowed=True,
            intent=IntentType.KNOWLEDGE_BASE,
        ),
        None,
        0.0,
    )

    executor = await AgentDispatcher.dispatch(
        config,
        user_query="按这个知识库回答",
        messages=[{"role": "user", "content": "按这个知识库回答"}],
        trace_id="trace-dispatch-explicit-knowledge",
        trace_buffer=[],
        shared_turn=shared_turn,
    )

    assert isinstance(executor, KnowledgeExecutor)
    assert executor.turn_classification.turn_type == TurnType.KNOWLEDGE


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
    shared_turn = (
        TurnClassification(
            turn_type=TurnType.KNOWLEDGE,
            reasoning="外部意图模型误判",
            requires_knowledge_search=True,
            intent=IntentType.KNOWLEDGE_BASE,
        ),
        None,
        0.0,
    )

    executor = await AgentDispatcher.dispatch(
        config,
        user_query="测试一个外部模型的性能",
        messages=[{"role": "user", "content": "测试一个外部模型的性能"}],
        trace_id="trace-dispatch-unbound-knowledge",
        trace_buffer=[],
        shared_turn=shared_turn,
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
    shared_turn = (
        TurnClassification(
            turn_type=TurnType.KNOWLEDGE,
            reasoning="明确的文档问题",
            requires_knowledge_search=True,
            intent=IntentType.KNOWLEDGE_BASE,
        ),
        None,
        0.0,
    )

    executor = await AgentDispatcher.dispatch(
        config,
        user_query="操作流程是什么",
        messages=[{"role": "user", "content": "操作流程是什么"}],
        trace_id="trace-dispatch-bound-knowledge",
        trace_buffer=[],
        shared_turn=shared_turn,
    )

    assert isinstance(executor, KnowledgeExecutor)
