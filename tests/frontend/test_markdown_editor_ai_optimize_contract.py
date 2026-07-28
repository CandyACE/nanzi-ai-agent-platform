from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure


def test_markdown_editor_exposes_ai_optimize_when_enabled():
    editor = Path("frontend/src/components/MarkdownEditor.vue").read_text()
    optimize = Path("frontend/src/components/PromptAiOptimize.vue").read_text()

    assert "enableOptimize" in editor
    assert "PromptAiOptimize" in editor
    assert ":disabled=\"disabled\"" in editor
    assert ":readonly=\"disabled\"" in editor
    assert "disabled?: boolean" in optimize
    assert "requirePermission?: boolean" in optimize
    assert "endpoint?: string" in optimize
    assert "!props.disabled" in optimize
    assert "AI 润色" in optimize
    assert "/api/portal/prompts/optimize" in optimize
    assert "props.endpoint" in optimize
    assert "element:prompts:optimize" in optimize
    assert "应用此方案" in optimize
    assert "z-[10000]" in optimize
    assert "z-[10050]" in optimize
    assert "取消润色" in optimize
    assert "cancelOptimize" in optimize
    assert "AbortController" in optimize
    assert "aria-label=\"关闭润色遮罩\"" in optimize


def test_agent_version_editor_enables_prompt_ai_optimize():
    drawer = Path("frontend/src/components/agent/AgentVersionEditorDrawer.vue").read_text()

    assert "MarkdownEditor" in drawer
    assert "enable-optimize" in drawer or ':enable-optimize="true"' in drawer or "enableOptimize" in drawer
    assert ':disabled="!canEditVersion"' in drawer
    assert ':require-optimize-permission="false"' in drawer
    assert '/api/portal/prompts/optimize/agent-editor' in drawer


def test_agent_editor_optimize_endpoint_is_distinct_from_permissioned_prompt_studio_endpoint():
    prompts_api = Path("app/api/portal/endpoints/prompts.py").read_text()

    assert 'async def optimize_agent_editor_prompt' in prompts_api
    assert '@router.post("/optimize/agent-editor"' in prompts_api
    assert 'dependencies=[Depends(require_permission("element", "element:prompts:optimize"))]' not in prompts_api.split(
        'async def optimize_agent_editor_prompt', 1
    )[0][-300:]
