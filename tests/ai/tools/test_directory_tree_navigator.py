import pytest

from app.services.ai.tools.advanced_auxiliary_tools import directory_tree_navigator


pytestmark = pytest.mark.no_infrastructure


def test_directory_tree_navigator_allows_project_and_data_navigation():
    project_root = __file__.split("/tests/ai/tools/")[0]

    project_result = directory_tree_navigator.invoke(
        {"path": f"{project_root}/tests/ai/tools"}
    )
    data_result = directory_tree_navigator.invoke({"path": f"{project_root}/data"})

    assert "test_directory_tree_navigator.py" in project_result
    assert "安全拦截" not in data_result


def test_directory_tree_navigator_rejects_paths_outside_navigation_roots(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()

    result = directory_tree_navigator.invoke({"path": str(outside)})

    assert "安全拦截" in result


def test_directory_tree_navigator_rejects_prefix_lookalike_project_path():
    project_root = __file__.split("/tests/ai/tools/")[0]

    result = directory_tree_navigator.invoke({"path": f"{project_root}_not_project"})

    assert "安全拦截" in result
