from types import SimpleNamespace

import pytest

from app.services.ai.request_decision import RequestCapability, RequestDecision, RequestSource
from app.services.ai.turn_decision import (
    TurnDecision,
)


pytestmark = pytest.mark.no_infrastructure


def test_router_components_round_trip_through_canonical_json():
    decision = TurnDecision.from_router_components(
        agent_id="data-agent",
        agent_name="data-agent",
        secondary_agents=["knowledge-agent"],
        confidence=0.91,
        reasoning="内部业务数据查询",
        intent_info=SimpleNamespace(
            intent="DATA_QUERY",
            confidence=0.88,
            reasoning="查询业务指标",
            domain="chatbi_business_data",
            operation="aggregate",
            fact_kind="business_metric",
            freshness_requirement="realtime",
            time_scope="本月",
            reference_mode="new_query",
            needs_fresh_data=True,
        ),
        request_decision=RequestDecision(
            source=RequestSource.INTERNAL_STRUCTURED_DATA,
            capability=RequestCapability.DATA_QUERY,
            confidence=0.91,
            reasoning="confirmed data source",
            should_delegate=True,
            delegate_capability="data_query",
            allows_data_route=True,
            semantic_domain="chatbi_business_data",
            semantic_operation="aggregate",
            fact_kind="business_metric",
            freshness_requirement="realtime",
            time_scope="本月",
            reference_mode="new_query",
            needs_fresh_data=True,
            chatbi_mode="direct",
            chatbi_evidence_level="explicit",
            chatbi_reason="authorized dataset",
            matched_dataset_ids=(12,),
        ),
        turn_labels=["new_business_request"],
        relation_to_previous="new_topic",
        user_action_type="ask_business_data_or_task",
    )
    restored = TurnDecision.model_validate(decision.model_dump(mode="json"))

    assert restored.agent_id == "data-agent"
    assert restored.capability == "data_query"
    assert restored.reference_mode == "new_query"
    assert restored.matched_dataset_ids == [12]


def test_turn_decision_projects_back_to_request_contract():
    decision = TurnDecision(
        source="internal_structured_data",
        capability="data_query",
        allows_data_route=True,
        should_delegate=True,
        delegate_capability="data_query",
        semantic_intent="DATA_QUERY",
        matched_dataset_ids=[7],
    )

    projected = decision.to_request_decision()

    assert projected.source is RequestSource.INTERNAL_STRUCTURED_DATA
    assert projected.capability is RequestCapability.DATA_QUERY
    assert projected.allows_data_route is True
    assert projected.matched_dataset_ids == (7,)


def test_direct_agent_selection_derives_capability_without_routing_llm():
    config = SimpleNamespace(
        agent_id="knowledge-agent",
        agent_name="Knowledge Agent",
        agent_display_name="知识助手",
        capabilities=["knowledge_base"],
    )

    decision = TurnDecision.for_direct_agent_selection(config)

    assert decision.agent_id == "knowledge-agent"
    assert decision.capability == "knowledge_search"
    assert decision.source == "internal_docs"
    assert decision.provenance == "direct_agent_selection"


def test_direct_agent_selection_is_a_first_class_single_track_decision():
    config = SimpleNamespace(
        agent_id="data-agent",
        agent_name="Data Agent",
        agent_display_name="数据助手",
        capabilities=["data_query"],
    )

    decision = TurnDecision.for_direct_agent_selection(config)

    assert decision.turn_kind == "data_query"
    assert decision.route_status == "resolved"
    assert decision.allows_data_route is True
    assert decision.provenance == "direct_agent_selection"


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


def test_unknown_or_failed_route_status_is_not_a_resolved_decision():
    unknown = TurnDecision()
    failed = TurnDecision(route_status="failed", capability="data_query")

    assert unknown.route_status == "unknown"
    assert unknown.turn_kind == "general"
    assert failed.route_status == "failed"
    assert failed.allows_data_route is False


def test_trace_payload_keeps_timings_and_omits_raw_reasoning():
    decision = TurnDecision(
        source="general",
        capability="answer",
        reasoning="internal router explanation",
        provenance="direct_agent_selection",
        fast_path="direct_agent_selection",
        stage_timings_ms={"route_resolution": 1.5},
    )

    trace = decision.trace_payload(
        stage_timings_ms={"intent_resolution": 0.0},
        executor="GENERAL",
    )

    assert trace["stage_timings_ms"] == {
        "route_resolution": 1.5,
        "intent_resolution": 0.0,
    }
    assert trace["fast_path"] == "direct_agent_selection"
    assert "reasoning" not in trace
