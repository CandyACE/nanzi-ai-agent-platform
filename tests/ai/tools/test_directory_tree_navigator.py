from types import SimpleNamespace

import pytest

from app.services.ai.tools import advanced_auxiliary_tools as auxiliary_tools

from app.services.ai.tools.advanced_auxiliary_tools import directory_tree_navigator


pytestmark = pytest.mark.no_infrastructure


def _prepare_workspace_tree(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    fake_module_path = repo_root / "app/services/ai/tools/advanced_auxiliary_tools.py"
    data_root = repo_root / "data"
    workspace_root = data_root / "agent_workspaces"
    own_root = workspace_root / "alice__1"
    other_root = workspace_root / "bob__2"

    (own_root / "docs").mkdir(parents=True)
    (other_root / "docs").mkdir(parents=True)
    (own_root / "docs/own.md").write_text("own", encoding="utf-8")
    (other_root / "docs/secret.md").write_text("secret", encoding="utf-8")

    monkeypatch.setattr(auxiliary_tools, "__file__", str(fake_module_path))
    monkeypatch.setattr("app.utils.fs_access.get_data_base_dir", lambda: str(data_root))
    monkeypatch.setattr("app.utils.fs_paths.get_data_base_dir", lambda: str(data_root))
    monkeypatch.setattr(
        "app.services.ai.runtime.agentscope.workspace.default_workspace_root",
        lambda: str(workspace_root),
    )
    return repo_root, own_root, other_root


def _user_context(*, is_admin=False):
    return SimpleNamespace(
        user_id=1,
        is_admin=is_admin,
        user_dimensions={"user_name": "alice"},
    )


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


def test_regular_user_cannot_navigate_other_workspace_or_leak_it_from_parent(
    tmp_path, monkeypatch
):
    repo_root, own_root, other_root = _prepare_workspace_tree(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "app.services.ai.tools.advanced_auxiliary_tools.get_current_agent_context",
        lambda: _user_context(),
    )

    own_result = directory_tree_navigator.invoke({"path": str(own_root)})
    other_result = directory_tree_navigator.invoke({"path": str(other_root)})
    parent_result = directory_tree_navigator.invoke({"path": str(repo_root)})

    assert "own.md" in own_result
    assert "安全拦截" in other_result
    assert "bob__2" not in parent_result
    assert "secret.md" not in parent_result


def test_admin_can_navigate_other_workspace(tmp_path, monkeypatch):
    _, _, other_root = _prepare_workspace_tree(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "app.services.ai.tools.advanced_auxiliary_tools.get_current_agent_context",
        lambda: _user_context(is_admin=True),
    )

    result = directory_tree_navigator.invoke({"path": str(other_root)})

    assert "secret.md" in result
