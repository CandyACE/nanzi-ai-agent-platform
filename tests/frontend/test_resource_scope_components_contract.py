from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_embed_uses_resource_scope_bar_component_without_moving_workflow_state():
    source = _read("frontend/src/views/EmbedChat.vue")
    bar = _read("frontend/src/components/embed/SessionResourceScopeBar.vue")

    assert "<SessionResourceScopeBar" in source
    assert "<!-- Project / Session resource scope bar -->" not in source
    assert ':project-name="resourceScope.project_name"' in source
    assert ':mounted-resources="mountedResourceLabels"' in source
    assert '@manage="openResourceScopeModal"' in source
    assert '@remove="removeMountedResource"' in source
    assert "管理会话资源" in bar
    assert "remove" in bar


def test_embed_uses_resource_scope_modal_component_and_keeps_parent_workflow_handlers():
    source = _read("frontend/src/views/EmbedChat.vue")
    modal = _read("frontend/src/components/embed/ResourceScopeModal.vue")

    assert "<ResourceScopeModal" in source
    assert 'v-if="showResourceScopeModal"' not in source
    for binding in (
        ':draft="resourceScopeModalDraft"',
        ':groups="resourceOptionGroups"',
        ':option-search="resourceOptionSearch"',
        ':selected-count="modalSelectedCount"',
        ':sorted-options="sortedModalResourceOptions"',
    ):
        assert binding in source
    for handler in (
        '@close="closeResourceScopeModal"',
        '@refresh="refreshResourceOptions"',
        '@save="saveResourceScope"',
        '@remove-draft="removeModalDraftResource"',
        '@toggle-option="toggleModalResourceOption"',
    ):
        assert handler in source
    assert "项目会话资源" in modal
    assert "resource-scope-modal-title" in modal
    assert "role=\"tablist\"" in modal
    assert "实际执行 SQL" not in modal
