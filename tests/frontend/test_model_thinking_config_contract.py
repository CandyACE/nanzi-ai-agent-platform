from pathlib import Path
import re

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
MODEL_API = ROOT / "frontend/src/api/model.ts"
MODEL_REGISTRY = ROOT / "frontend/src/components/system/ModelRegistry.vue"
CHAT_INPUT = ROOT / "frontend/src/components/embed/ChatInput.vue"
EMBED_CHAT = ROOT / "frontend/src/views/EmbedChat.vue"
AGENT_DEBUG = ROOT / "frontend/src/views/AgentDebug.vue"


def test_model_api_declares_thinking_configuration():
    source = MODEL_API.read_text(encoding="utf-8")

    assert "export type ReasoningEffort" in source
    for field in (
        "thinking_enable",
        "thinking_only",
        "allow_disable_thinking",
        "reasoning_effort",
        "supported_reasoning_efforts",
    ):
        assert source.count(field) >= 3
    for value in ("none", "minimal", "low", "medium", "high", "xhigh"):
        assert value in source


def test_model_registry_shows_dependent_thinking_controls():
    source = MODEL_REGISTRY.read_text(encoding="utf-8")

    assert "思考模式" in source
    assert "仅思考模式" in source
    assert "允许关闭思考" in source
    assert "默认思考强度" in source
    assert "支持的思考强度" in source
    assert "thinking_enable" in source
    assert "v-if=\"modelForm.thinking_enable\"" in source
    assert "supported_reasoning_efforts" in source
    assert "reasoning_effort" in source
    assert "thinking_only" in source
    assert "allow_disable_thinking" in source


def test_model_registry_preserves_hidden_values_and_sends_configuration():
    source = MODEL_REGISTRY.read_text(encoding="utf-8")

    assert "handleReasoningEffortChange" in source
    assert "reasoningEffort" in source or "reasoning_effort" in source
    assert "supportedReasoningEfforts" in source or "supported_reasoning_efforts" in source
    assert "thinking_enable: modelForm.value.thinking_enable" in source
    assert "thinking_only: modelForm.value.thinking_only" in source
    assert "allow_disable_thinking: modelForm.value.allow_disable_thinking" in source


def test_model_registry_hides_advanced_settings_for_embedding_models():
    source = MODEL_REGISTRY.read_text(encoding="utf-8")

    assert 'v-if="modelForm.type !== \'embedding\'"' in source


def test_model_registry_places_thinking_section_above_context_section():
    source = MODEL_REGISTRY.read_text(encoding="utf-8")
    template = source[source.index("<template>"):]

    assert "思考模式" in template
    assert "上下文与输出" in template
    assert template.index("思考模式") < template.index("上下文与输出")
    assert "thinking-mode-section" in template
    assert "advanced-context-section" in template


def test_model_registry_explains_reasoning_effort_scenarios():
    source = MODEL_REGISTRY.read_text(encoding="utf-8")

    for scenario in (
        "常规代码、一般分析",
        "Debug、SQL、复杂分析、Agent",
        "极难 Coding Agent、长任务",
    ):
        assert scenario in source


def test_model_registry_gives_default_effort_its_own_full_width_section():
    source = MODEL_REGISTRY.read_text(encoding="utf-8")
    template = source[source.index("<template>"):]

    assert "default-reasoning-effort-row" in template
    assert "supported-reasoning-section" in template
    assert template.index("default-reasoning-effort-row") < template.index("supported-reasoning-section")
    assert "default-reasoning-effort-select" in source


def test_model_registry_groups_each_reasoning_effort_in_a_card():
    source = MODEL_REGISTRY.read_text(encoding="utf-8")

    assert "thinking-effort-option-selected" in source
    assert ".thinking-effort-option" in source
    assert "grid-template-columns: repeat(3" in source


def test_shared_chat_input_exposes_session_reasoning_submenu_contract():
    source = CHAT_INPUT.read_text(encoding="utf-8")

    assert "thinkingEnableOverride" in source
    assert "reasoningEffortOverride" in source
    assert "update:thinking-enable-override" in source
    assert "update:reasoning-effort-override" in source
    assert "思考强度" in source
    assert "关闭思考" in source
    assert "supported_reasoning_efforts" in source


def test_embedchat_and_agentdebug_send_session_reasoning_overrides():
    embed_source = EMBED_CHAT.read_text(encoding="utf-8")
    debug_source = AGENT_DEBUG.read_text(encoding="utf-8")

    for source in (embed_source, debug_source):
        assert "thinking_enable" in source
        assert "reasoning_effort" in source
        assert "update:thinking-enable-override" in source
        assert "update:reasoning-effort-override" in source
        assert "reset" in source and "ThinkingOverrides" in source


def test_chat_input_keeps_model_menu_compact_and_surfaces_current_thinking_mode():
    source = CHAT_INPUT.read_text(encoding="utf-8")

    assert "w-[min(560px" in source
    assert "max-h-[min(448px" in source
    assert "thinkingSummaryLabel" in source
    assert "aria-pressed" in source
    assert "overflow-y-auto" in source


def test_thinking_switch_thumb_stays_inside_the_switch_track():
    source = CHAT_INPUT.read_text(encoding="utf-8")

    assert source.count("left-0.5 top-0.5 h-5 w-5") >= 1
    assert source.count("overflow-hidden") >= 2


def test_thinking_effort_options_are_expanded_without_a_second_click():
    source = CHAT_INPUT.read_text(encoding="utf-8")

    assert "showReasoningEffortPanel" not in source
    assert "跟随模型默认" in source
    assert "v-for=\"option in supportedReasoningEfforts\"" in source


def test_reasoning_panel_only_renders_after_reasoning_content_arrives():
    for path in (EMBED_CHAT, AGENT_DEBUG):
        source = path.read_text(encoding="utf-8")
        match = re.search(
            r'<div\s+v-if="([^"]+)"\s+class="reasoning-content-panel',
            source,
        )
        assert match is not None
        assert match.group(1) == "msg.reasoningContent"


def test_reasoning_panel_is_collapsible_and_uses_light_quote_style():
    for path in (EMBED_CHAT, AGENT_DEBUG):
        source = path.read_text(encoding="utf-8")
        assert "isReasoningExpanded?: boolean" in source
        assert "@click=\"msg.isReasoningExpanded = !msg.isReasoningExpanded\"" in source
        assert 'v-show="msg.isReasoningExpanded !== false"' in source
        assert "bg-slate-50" in source
        assert "border-l-4" in source
        assert "border-slate-200" in source


def test_reasoning_panel_uses_model_inference_label():
    for path in (EMBED_CHAT, AGENT_DEBUG):
        source = path.read_text(encoding="utf-8")
        panel_start = source.index("reasoning-content-panel")
        panel_end = source.index("<!-- Main Content", panel_start)
        panel = source[panel_start:panel_end]
        assert "本次会话已启用模型推理" in panel
        assert "思考过程" not in panel
