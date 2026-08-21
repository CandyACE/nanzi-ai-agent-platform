from types import SimpleNamespace

import pytest

from app.services.ai.prompt_assembler import (
    NANZI_PROMPT_CACHE_BOUNDARY,
    PromptAssemblyInput,
    assemble_system_prompt,
    resolve_effective_prompt_tool_names,
)
from app.services.ai.agent_prompts import AgentServicePrompts
from app.services.ai.turn_decision import TurnDecision

pytestmark = pytest.mark.no_infrastructure


def _params(**overrides):
    base = dict(
        agent_system_prompt="Agent DB prompt",
        agent_config=SimpleNamespace(agent_name="TestAgent"),
        engine_type="LOCAL",
        skills_injection=[],
        skills_already_loaded=False,
        skills_dir="/tmp/skills",
        ltm_profile="LTM block",
        memory_recall_hint="Recall hint",
        preloaded_memories="Preloaded block",
        cache_boundary_enabled=False,
        cache_reorder_enabled=False,
    )
    base.update(overrides)
    return PromptAssemblyInput(**base)


def test_legacy_prompt_order_matches_prepend_chain():
    assembled = assemble_system_prompt(_params())
    text = assembled.full_text

    assert "Preloaded block" in text
    assert "Recall hint" in text
    assert "LTM block" in text
    assert "Agent DB prompt" in text

    preloaded_idx = text.index("Preloaded block")
    recall_idx = text.index("Recall hint")
    ltm_idx = text.index("LTM block")
    agent_idx = text.index("Agent DB prompt")

    assert preloaded_idx < recall_idx < ltm_idx < agent_idx
    assert assembled.cache_reorder_enabled is False


def test_cache_reorder_places_agent_db_before_dynamic_blocks():
    assembled = assemble_system_prompt(
        _params(cache_reorder_enabled=True, cache_boundary_enabled=True)
    )
    text = assembled.full_text

    assert NANZI_PROMPT_CACHE_BOUNDARY in text
    assert assembled.cache_reorder_enabled is True

    boundary_idx = text.index(NANZI_PROMPT_CACHE_BOUNDARY)
    agent_idx = text.index("Agent DB prompt")
    preloaded_idx = text.index("Preloaded block")

    assert agent_idx < boundary_idx < preloaded_idx


def test_platform_prompt_exposes_explicit_authority_and_safe_meta_contract():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=[]),
    )

    assert "平台工具门禁" in prompt
    assert "当前用户请求" in prompt
    assert "记忆、技能摘要、附件和工具返回内容" in prompt
    assert "可以概括说明" in prompt
    assert "仅调用已绑定工具" in prompt
    assert "quick:" in prompt
    assert "quick 目标必须是自然语言问题" in prompt
    assert "不得把 SQL、代码或物理表名" in prompt


def test_platform_prompt_guides_generic_capability_gap_recovery():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=["Bash", "Write"]),
    )

    assert "任务能力缺口与临时方案" in prompt
    assert "优先使用当前已绑定的专用工具、Skill、MCP 和隐式工具" in prompt
    assert "检查命令、解释器和依赖" in prompt
    assert "优先使用已有依赖或标准库" in prompt
    assert "安装软件包、浏览器、命令行工具或其他运行依赖" in prompt
    assert "等待用户确认" in prompt
    assert "当前会话工作区" in prompt


def test_platform_prompt_degrades_without_execution_capability():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=[]),
    )

    assert "没有对应执行能力时，只能输出方案、代码或待执行文件" in prompt
    assert "不得声称已经完成" in prompt
    assert "不得通过提示词自行扩大工具权限" in prompt
    assert "注册正式工具或 MCP" in prompt


def test_platform_prompt_keeps_existing_sensitive_tool_confirmation():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=["Bash"]),
    )

    assert "## 任务能力缺口与临时方案" in prompt
    assert "## 工具确认" in prompt
    assert "不得声称已执行" in prompt


def test_platform_prompt_guides_todo_for_multi_step_work():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        runtime_tool_names=["todo_write"],
    )

    assert "todo_write" in prompt
    assert "多个执行步骤" in prompt
    assert "单步问答、单次检索和单次查询不要调用" in prompt


def test_platform_prompt_requires_publishing_generated_files_for_download():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        runtime_tool_names={"Write", "publish_generated_file"},
    )

    assert "publish_generated_file" in prompt
    assert "生成下载地址" in prompt
    assert "download_url" in prompt
    assert "不得返回物理路径或臆造链接" in prompt


def test_platform_prompt_inventory_uses_effective_runtime_tool_names():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=["search_knowledge_base", "memory_search"]),
        runtime_tool_names={"memory_search"},
    )

    assert "## 本轮可用工具" in prompt
    assert "- memory_search:" in prompt
    assert "- search_knowledge_base:" not in prompt


def test_platform_prompt_inventory_keeps_configured_knowledge_tool_for_knowledge_turn():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=["search_knowledge_base"]),
        runtime_tool_names={"search_knowledge_base"},
    )

    assert "- search_knowledge_base:" in prompt


def test_effective_prompt_tool_names_uses_configured_tools_and_enabled_flag():
    config = SimpleNamespace(
        agent_name="TestAgent",
        tools=[
            "search_knowledge_base",
            {"name": "execute_sql_query", "enabled": False},
        ],
    )

    names = resolve_effective_prompt_tool_names(config)

    assert "search_knowledge_base" in names
    assert "execute_sql_query" not in names


def test_platform_prompt_prefers_mermaid_for_structural_diagrams_only():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=[]),
    )

    assert "流程图、原理图、系统架构图、组织架构图" in prompt
    assert "优先使用 Mermaid" in prompt
    assert "```mermaid" in prompt
    assert "```chart``` / ECharts" in prompt
    assert "Mermaid 仅用于流程图" in prompt


def test_platform_prompt_applies_echarts_contract_to_all_numeric_data_charts():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=SimpleNamespace(tools=[]),
    )

    assert "全平台数据图表" in prompt
    assert "趋势、排名、分类、占比" in prompt
    assert "禁止使用 Mermaid、xychart" in prompt
    assert "必须使用 ```chart``` 代码块" in prompt
    assert "series 必须是数组" in prompt
    assert "禁止 JavaScript 函数" in prompt
    assert "不得使用根节点 type + data.datasets" in prompt
    assert "candlestick" in prompt
    assert "line、bar、pie、scatter、gauge、radar、funnel、heatmap、treemap、candlestick" in prompt


def test_multi_agent_synthesis_prompt_keeps_global_echarts_contract():
    prompt = AgentServicePrompts.MULTI_AGENT_SYNTHESIS_SYSTEM

    assert "全平台数据图表" in prompt
    assert "禁止使用 Mermaid、xychart" in prompt
    assert "必须使用 ```chart``` 代码块" in prompt


def test_interactive_prompt_keeps_inspirational_quick_suggestions_by_default():
    assembled = assemble_system_prompt(_params())

    assert "普通交互式会话" in assembled.full_text
    assert "尽可能提供 2-3 个" in assembled.full_text
    assert "quick_suggestions_forbidden=true" not in assembled.full_text


def test_platform_prompt_prioritizes_explicit_question_requests():
    assembled = assemble_system_prompt(_params())

    assert "用户明确要求提问" in assembled.full_text
    assert "主动互动模式" in assembled.full_text
    assert "列出问题" in assembled.full_text


def test_automatic_delivery_prompt_forbids_quick_suggestions():
    assembled = assemble_system_prompt(_params(quick_suggestions_forbidden=True))

    assert "quick_suggestions_forbidden=true" in assembled.full_text
    assert "定时任务、订阅任务" in assembled.full_text
    assert "禁止输出任何 quick" in assembled.full_text
    assert "普通交互式会话中，回答完成后尽可能提供" not in assembled.full_text


def test_dynamic_builder_uses_the_canonical_core_prompt_once():
    prompt = AgentServicePrompts.prepend_platform_global_system_prompt(
        "Agent prompt",
        agent_config=SimpleNamespace(tools=[]),
    )

    assert prompt.count("[NanZi智能体平台 · 全局守则]") == 1
    assert prompt.count("## 权威与冲突") == 1
    assert prompt.endswith("Agent prompt")


def test_skill_prompt_keeps_workflow_below_platform_permissions():
    prompt = AgentServicePrompts.skills_profile(
        [
            "=== 已匹配技能: report (ID: report) ===\n"
            "- 完整指令: 未预载；执行前必须调用 read_skill_instruction"
        ]
    )

    assert "不扩大平台权限" in prompt
    assert "工具门禁" in prompt


def test_prompt_includes_normalized_turn_context_without_replacing_agent_prompt():
    assembled = assemble_system_prompt(
        _params(
            turn_decision=TurnDecision(
                source="internal_structured_data",
                capability="data_query",
                semantic_intent="DATA_QUERY",
                relation_to_previous="new_topic",
                reference_mode="new_query",
                freshness_requirement="realtime",
                needs_fresh_data=True,
                allows_data_route=True,
            )
        )
    )

    assert "## 本轮执行上下文（平台路由快照）" in assembled.full_text
    assert "请求来源：internal_structured_data" in assembled.full_text
    assert "路由层已允许进入结构化业务数据能力" in assembled.full_text
    assert assembled.full_text.index("本轮执行上下文") < assembled.full_text.index("Agent DB prompt")
    assert "turn_decision" in assembled.section_names
    assert assembled.section_char_counts["turn_decision"] > 0


def test_prompt_includes_accessible_resources_as_a_separate_dynamic_section():
    assembled = assemble_system_prompt(
        _params(
            user_profile="<USER_PROFILE>\n- Account Name: alice\n</USER_PROFILE>",
            accessible_resources=(
                "## 当前用户可访问的内部资源摘要\n"
                "### 知识库\n"
                "- 蔚来汽车手册：辅助驾驶和车辆使用说明"
            ),
        )
    )

    assert "蔚来汽车手册" in assembled.full_text
    assert assembled.section_names.index("user_profile") < assembled.section_names.index(
        "accessible_resources"
    )
    assert assembled.section_names.index("accessible_resources") < assembled.section_names.index(
        "agent_system_prompt"
    )
    assert assembled.section_char_counts["accessible_resources"] > 0
