from pathlib import Path


ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "frontend/src/components/embed/WorkspaceBrowserDrawer.vue"


def test_quick_navigation_uses_semantic_svg_components() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    quick_links_source = source[source.index("const quickNavLinks"):source.index("const isQuickLinkActive")]
    quick_menu_source = source[source.index('v-if="quickNavOpen"'):source.index('ref="recentFilesMenuRef"')]

    for icon in (
        "HomeIcon",
        "DocumentTextIcon",
        "ChatBubbleLeftEllipsisIcon",
        "ArrowUpTrayIcon",
        "ClockIcon",
        "TrashIcon",
    ):
        assert icon in source
    assert '<component :is="link.icon"' in quick_menu_source
    assert "<ClockIcon" in quick_menu_source
    assert "icon: '🏠'" not in quick_links_source
    assert "icon: '📄'" not in quick_links_source
    assert "icon: '💬'" not in quick_links_source
    assert "icon: '📤'" not in quick_links_source
