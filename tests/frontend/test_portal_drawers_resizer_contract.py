from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_portal_drawers_resizer_contract():
    dataset_drawer = ROOT / "frontend/src/components/chatbi/DatasetPortalDrawer.vue"
    knowledge_drawer = ROOT / "frontend/src/components/knowledge/KnowledgePortalDrawer.vue"

    assert dataset_drawer.exists(), "DatasetPortalDrawer.vue must exist"
    assert knowledge_drawer.exists(), "KnowledgePortalDrawer.vue must exist"

    dataset_content = dataset_drawer.read_text(encoding="utf-8")
    knowledge_content = knowledge_drawer.read_text(encoding="utf-8")

    # Dataset Portal Drawer checks
    assert "nanzi_dataset_portal_drawer_width" in dataset_content
    assert "cursor-col-resize" in dataset_content
    assert "@mousedown=\"startResize\"" in dataset_content
    assert "drawerPanelStyle" in dataset_content

    # Knowledge Portal Drawer checks
    assert "nanzi_knowledge_portal_drawer_width" in knowledge_content
    assert "cursor-col-resize" in knowledge_content
    assert "@mousedown=\"startResize\"" in knowledge_content
    assert "drawerPanelStyle" in knowledge_content

    # Workspace Browser Drawer checks
    workspace_drawer = ROOT / "frontend/src/components/embed/WorkspaceBrowserDrawer.vue"
    assert workspace_drawer.exists(), "WorkspaceBrowserDrawer.vue must exist"
    workspace_content = workspace_drawer.read_text(encoding="utf-8")
    assert "nanzi_workspace_browser_drawer_width" in workspace_content
    assert "cursor-col-resize" in workspace_content
    assert "@mousedown=\"startResize\"" in workspace_content
    assert "drawerPanelStyle" in workspace_content


def test_embed_capability_panels_default_pinned_on_desktop():
    """桌面端未写偏好时，查数/知识/工作空间抽屉默认钉住。"""
    dataset = (ROOT / "frontend/src/composables/useDatasetPortal.ts").read_text(encoding="utf-8")
    knowledge = (ROOT / "frontend/src/composables/useKnowledgePortal.ts").read_text(encoding="utf-8")
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert "readStoredBoolean(pinStorageKey, true)" in dataset
    assert 'readStoredBoolean("knowledge_portal_pinned", true)' in knowledge
    assert 'readStoredBoolean("embed_workspace_pinned", true)' in embed
