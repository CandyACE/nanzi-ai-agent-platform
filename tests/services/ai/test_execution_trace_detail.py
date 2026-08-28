"""执行卡片前置生命周期明细的行为契约。"""

from types import SimpleNamespace

import pytest

from app.services.ai.agent_service import (
    _build_capability_catalog_log,
    _build_context_history_log,
    _build_model_config_log,
    _build_prompt_assembly_log,
    _build_request_validation_log,
    _build_preparation_parent_log,
)
from app.services.ai.config import RuntimeModelInfo
from app.services.ai.runtime.agentscope.process_timeline_snapshot import apply_stream_chunk


pytestmark = pytest.mark.no_infrastructure


def test_request_validation_log_contains_identity_checks_and_never_credentials():
    event = _build_request_validation_log(
        user_info={
            "user_id": 7,
            "real_name": "张三",
            "role_name": "分析员",
        },
        conversation_id="conversation-1",
        request_observability={
            "authenticated": True,
            "parameters_validated": True,
            "idempotency_status": "已通过",
            "resource_scope": {
                "datasets": 2,
                "knowledge_bases": 1,
                "skills": 3,
                "mcp_tools": 4,
            },
            "turn_resource_scope": {
                "datasets": 1,
                "knowledge_bases": 2,
            },
            "authorized_resource_scope": {
                "datasets": 7,
                "knowledge_bases": 6,
            },
        },
    )

    assert event["title"] == "请求校验"
    assert "当前会话用户：张三（ID：7，角色：分析员）" in event["details"]
    assert "鉴权：已通过" in event["details"]
    assert "参数校验：已通过" in event["details"]
    assert "会话挂载：已加载，数据集 2 个、知识库 1 个" in event["details"]
    assert "本轮请求：数据集 1 个、知识库 2 个" in event["details"]
    assert "当前用户有权限：数据集 7 个、知识库 6 个" in event["details"]
    assert "幂等校验：已通过" in event["details"]
    assert "api_key" not in event["details"]


def test_context_history_log_reports_loaded_window_trim_and_compaction():
    event = _build_context_history_log(
        conversation_id="conversation-1",
        source_history_count=20,
        selected_history_count=8,
        trimmed_history_count=12,
        history_token_budget=4096,
        max_context_messages=60,
        compaction_applied=True,
    )

    assert event["title"] == "会话上下文"
    assert "读取历史 20 条" in event["details"]
    assert "上下文窗口保留 8 条" in event["details"]
    assert "裁剪 12 条" in event["details"]
    assert "上下文压缩：已触发" in event["details"]


def test_model_capability_and_prompt_logs_are_safe_summaries():
    model = RuntimeModelInfo(
        configured_model="团队默认模型",
        effective_model_id="deepseek-chat",
        source="agent_config",
        context_size=32768,
        max_output_tokens=4096,
        resolution_status="registry_resolved",
    )
    model_event = _build_model_config_log(model)
    capability_event = _build_capability_catalog_log(
        knowledge_dataset_count=2,
        configured_dataset_count=1,
        skill_count=3,
        delegable_agent_count=5,
        roster_loaded=True,
        runtime_tool_count=8,
        metadata_dataset_count=4,
        session_dataset_count=2,
        session_knowledge_base_count=1,
        authorized_dataset_count=7,
        authorized_knowledge_base_count=6,
    )
    prompt_event = _build_prompt_assembly_log(
        SimpleNamespace(
            stable_prefix="stable",
            dynamic_suffix="dynamic",
            full_text="assembled prompt",
            section_names=("platform_global", "skills"),
        ),
        runtime_tool_count=8,
    )

    assert "deepseek-chat" in model_event["details"]
    assert "上下文：32768" in model_event["details"]
    assert "会话挂载：数据集 2 个、知识库 1 个" in capability_event["details"]
    assert "本轮选用：数据集 4 个、知识库 2 个" in capability_event["details"]
    assert "当前用户有权限：数据集 7 个、知识库 6 个" in capability_event["details"]
    assert "可委派专家清单：已加载 5 个" in capability_event["details"]
    assert "已组装 2 个提示词区块" in prompt_event["details"]
    assert "assembled prompt" not in prompt_event["details"]


def test_preparation_logs_are_nested_under_one_auth_context_parent():
    parent = _build_preparation_parent_log(status="pending")
    state = []

    apply_stream_chunk(state, parent)
    apply_stream_chunk(
        state,
        {
            "type": "log",
            "id": "request:validation",
            "title": "请求校验",
            "status": "success",
            "parent_id": parent["id"],
        },
    )
    apply_stream_chunk(
        state,
        {
            "type": "log",
            "id": "context:history",
            "title": "会话上下文",
            "status": "success",
            "parent_id": parent["id"],
        },
    )

    assert parent["id"] == "preparation:auth_context_capability"
    assert parent["title"] == "鉴权及上下文与能力准备"
    assert state[0]["id"] == parent["id"]
    assert [child["id"] for child in state[0]["children"]] == [
        "request:validation",
        "context:history",
    ]


def test_capability_catalog_does_not_fake_permission_counts_when_catalog_is_unavailable():
    event = _build_capability_catalog_log(
        knowledge_dataset_count=0,
        configured_dataset_count=0,
        skill_count=0,
        delegable_agent_count=0,
        roster_loaded=False,
        runtime_tool_count=0,
    )

    assert "当前用户有权限：权限目录未统计" in event["details"]
    assert "暂不可用 个" not in event["details"]
