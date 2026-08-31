from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend/src/components/embed/WorkspaceBrowserDrawer.vue"


def test_workspace_browser_uses_semantic_icons_and_refresh_action():
    source = SOURCE.read_text(encoding="utf-8")

    assert "ArrowPathIcon" in source
    assert "XMarkIcon" in source
    assert '@click="refreshDirectory()"' in source
    assert ':disabled="loading"' in source


def test_workspace_browser_exposes_list_and_grid_modes_with_list_default():
    source = SOURCE.read_text(encoding="utf-8")

    assert "type ViewMode = 'list' | 'grid'" in source
    assert "const viewMode = ref<ViewMode>('list')" in source
    assert "切换到列表视图" in source
    assert "切换到文件夹视图" in source


def test_workspace_browser_grid_reuses_display_items_and_existing_interactions():
    source = SOURCE.read_text(encoding="utf-8")

    assert "viewMode === 'grid'" in source
    assert 'v-else class="flex-1 overflow-y-auto custom-scrollbar' in source
    assert 'v-for="item in paginatedDisplayItems"' in source
    assert '@dblclick="handleDoubleClick(item)"' in source
    assert '@contextmenu="handleItemContextMenu($event, item)"' in source
    assert "toggleMultiSelect(item)" in source
