from pathlib import Path

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

    assert "思考模式配置" in source
    assert "默认思考模式" in source
    assert "新会话默认开思考" in source
    assert "允许关闭思考" in source
    assert "用户可在会话里关掉思考" in source
    assert "默认思考强度" in source
    assert "支持的思考强度" in source
    assert "thinking_enable" in source
    assert "v-if=\"modelForm.thinking_enable\"" in source
    assert "supported_reasoning_efforts" in source
    assert "reasoning_effort" in source
    assert "thinking_only" in source
    assert "allow_disable_thinking" in source
    assert source.count("thinking-mode-capsule") >= 3
    assert 'v-model="modelForm.thinking_only"' in source
    assert 'v-model="modelForm.allow_disable_thinking"' in source
    assert "modelForm.thinking_only ? '开启' : '关闭'" in source
    assert "modelForm.allow_disable_thinking ? '开启' : '关闭'" in source
    assert "thinking-option-card" in source
    assert "22 163 74" in source
    assert "min-width: 4.5rem" in source


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

    assert "思考模式配置" in template
    assert "上下文与输出" in template
    assert template.index("思考模式配置") < template.index("上下文与输出")
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


def test_chat_input_scrolls_to_selected_model_when_menu_opens():
    source = CHAT_INPUT.read_text(encoding="utf-8")

    assert "scrollSelectedModelIntoView" in source
    assert "modelListScrollRef" in source
    assert 'data-model-current' in source
    assert "list.scrollTop" in source
    assert "toggleModelDropdown" in source
    toggle_idx = source.index("const toggleModelDropdown")
    next_fn = source.find("\nconst ", toggle_idx + 1)
    toggle_body = source[toggle_idx:next_fn if next_fn != -1 else toggle_idx + 800]
    assert "scrollSelectedModelIntoView" in toggle_body


def test_chat_input_keeps_model_menu_compact_and_surfaces_current_thinking_mode():
    source = CHAT_INPUT.read_text(encoding="utf-8")

    assert "w-[min(560px" in source
    assert "max-h-[min(448px" in source
    assert "thinkingSummaryLabel" in source
    assert "aria-pressed" in source
    assert "overflow-y-auto" in source


def test_chat_input_uses_thinking_only_for_default_state_only():
    source = CHAT_INPUT.read_text(encoding="utf-8")

    assert "props.thinkingEnableOverride ?? Boolean(selectedModelConfig.value.thinking_only)" in source
    assert "const canToggleThinking = computed" in source
    assert "selectedModelConfig.value.allow_disable_thinking" in source
    assert "&& !selectedModelConfig.value.thinking_only" not in source


def test_task_prompt_composer_uses_thinking_only_for_default_state_only():
    source = (ROOT / "frontend/src/components/task/TaskPromptComposer.vue").read_text(encoding="utf-8")

    assert "props.thinkingEnableOverride ?? Boolean(selectedModelConfig.value.thinking_only)" in source
    assert "const canToggleThinking = computed" in source
    assert "&& !selectedModelConfig.value.thinking_only" not in source


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
    timeline = (ROOT / "frontend/src/components/chat/ChatExecutionTimeline.vue").read_text(encoding="utf-8")
    assert "reasoningContent" in timeline
    assert "item.textKind === 'reasoning'" in timeline
    for path in (EMBED_CHAT, AGENT_DEBUG):
        source = path.read_text(encoding="utf-8")
        assert "<ChatExecutionTimeline" in source
        assert ':reasoning-content="msg.reasoningContent"' in source


def test_reasoning_panel_is_collapsible_and_uses_light_quote_style():
    timeline = (ROOT / "frontend/src/components/chat/ChatExecutionTimeline.vue").read_text(encoding="utf-8")
    assert 'v-show="expanded"' in timeline
    assert "text-violet-500" not in timeline
    assert "text-violet-600" not in timeline
    assert "<blockquote" in timeline
    assert "border-l-2 border-gray-200" in timeline
    for path in (EMBED_CHAT, AGENT_DEBUG):
        source = path.read_text(encoding="utf-8")
        assert 'v-model="msg.isThoughtExpanded"' in source


def test_reasoning_panel_uses_model_inference_label():
    timeline = (ROOT / "frontend/src/components/chat/ChatExecutionTimeline.vue").read_text(encoding="utf-8")
    assert 'props.hasAnswer ? "思考完成" : "执行过程"' in timeline
    assert "深度思考" in timeline
    assert "item.textKind === 'reasoning'" in timeline
    assert "💭" in timeline
    assert "isReasoningBodyOpen" in timeline
    assert "item.textKind === 'reasoning' ? '🧠'" not in timeline
    assert 'item.category === "intent"' in timeline
    assert "rounded-full border border-violet" not in timeline
    for path in (EMBED_CHAT, AGENT_DEBUG):
        source = path.read_text(encoding="utf-8")
        assert "本次会话已启用模型思考推理" not in source


def test_history_loaders_restore_reasoning_content_separately_from_answer():
    assert "reasoningContent: item.reasoning_content ?? undefined" in EMBED_CHAT.read_text(encoding="utf-8")
    agent_debug = AGENT_DEBUG.read_text(encoding="utf-8")
    assert "reasoningContent: m.reasoning_content || undefined" in agent_debug


def test_history_loaders_restore_process_timeline_for_thinking_card():
    embed = EMBED_CHAT.read_text(encoding="utf-8")
    debug = AGENT_DEBUG.read_text(encoding="utf-8")
    assert "hydrateHistoryProcessTimeline" in embed
    assert "hydrateHistoryProcessTimeline" in debug
    assert "item.process_timeline" in embed
    assert "m.process_timeline" in debug
