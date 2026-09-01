from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ["frontend/src/views/Roles.vue", "frontend/src/views/Users.vue"])
def test_permission_tree_cascades_menu_selection_to_child_elements(path: str):
    source = _source(path)
    assert "getMenuDescendantIds" in source
    assert "isMenuPartiallySelected" in source
    assert "descendantIds" in source
    assert "permissionData.value.elements" in source
    assert "menu.children" in source


@pytest.mark.parametrize("path", ["frontend/src/views/Roles.vue", "frontend/src/views/Users.vue"])
def test_permission_tree_explains_menu_and_element_permission_levels(path: str):
    source = _source(path)
    assert "菜单权限" in source
    assert "功能点权限" in source
    assert "viewBox=\"0 0 24 24\"" in source
    assert "isMenuPartiallySelected(menu.id)" in source
