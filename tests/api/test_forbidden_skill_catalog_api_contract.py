"""禁用公共技能：候选目录接口与权限字段接入。

- 目录接口只列"已启用的平台（全局）技能"：个人技能不在管理员配置范围内，
  已禁用的技能列出来也没意义。
- 权限字段 ``forbidden_skills`` 与 ``forbidden_tools`` / ``forbidden_commands`` 完全平行。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from app.api.portal.endpoints import tools as tools_endpoint
from app.schemas.permission import PermissionSet, ResourcePermissionBase
from app.services.permission_service import PermissionService


pytestmark = pytest.mark.no_infrastructure


def _write_skill(root: Path, skill_id: str, *, enabled: bool = True, name: str | None = None) -> None:
    skill_dir = root / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    display = name or skill_id
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {display}\ndescription: 演示 {skill_id} 的能力\n"
        f"enabled: {str(enabled).lower()}\n---\n\n# {display}\n",
        encoding="utf-8",
    )


def _db_with(api_tools, mcp_tools):
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: api_tools)),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: mcp_tools)),
        ]
    )
    return db


@pytest.mark.asyncio
async def test_catalog_lists_only_enabled_global_skills(tmp_path, monkeypatch):
    global_root = tmp_path / "global"
    personal_root = tmp_path / "personal"
    _write_skill(global_root, "docx", name="Word 文档")
    _write_skill(global_root, "retired", enabled=False)
    _write_skill(personal_root, "mine")

    monkeypatch.setattr(
        "app.services.ai.skill_resolver.get_user_personal_skills_dir",
        lambda _user: str(personal_root),
    )

    with patch("app.core.config.Settings.SKILLS_DIR", new_callable=PropertyMock) as mock_dir:
        mock_dir.return_value = str(global_root)
        response = await tools_endpoint.list_forbidden_tool_catalog(
            _db_with([], []),
            {"role": "admin", "user_id": 1},
        )

    candidates = response["skill_candidates"]
    assert [candidate["id"] for candidate in candidates] == ["docx"]
    assert candidates[0]["label"] == "Word 文档"
    assert candidates[0]["group"] == "公共技能"
    assert candidates[0]["group_key"] == "skill:__all__"
    # 工具候选不受影响
    assert "candidates" in response


def test_permission_set_normalizes_forbidden_skills():
    perm_set = PermissionSet(forbidden_skills=[" docx ", "DOCX", "", "pdf"])

    # 去空白 + 大小写不敏感去重（与 forbidden_tools 同一套归一化）
    assert perm_set.forbidden_skills == ["docx", "pdf"]


def test_resource_permission_type_is_a_free_form_string():
    """复用 ResourcePermission 存禁用技能：resource_type 长度足够，无需迁移。"""
    perm = ResourcePermissionBase(resource_type="forbidden_skill", resource_id="docx")

    assert perm.resource_type == "forbidden_skill"
    assert len("forbidden_skill") <= 20


def test_aggregate_permissions_collects_forbidden_skills():
    service = PermissionService(db=None)  # type: ignore[arg-type]
    perm_set = PermissionSet()
    rows = [
        SimpleNamespace(resource_type="forbidden_skill", resource_id="docx"),
        SimpleNamespace(resource_type="forbidden_skill", resource_id="pdf"),
        SimpleNamespace(resource_type="forbidden_skill", resource_id="docx"),
        SimpleNamespace(resource_type="forbidden_tool", resource_id="exec_command"),
    ]

    service._aggregate_permissions(perm_set, rows)

    assert perm_set.forbidden_skills == ["docx", "pdf"]
    assert perm_set.forbidden_tools == ["exec_command"]


def test_save_and_read_paths_cover_forbidden_skill():
    """保存/回显链路的源码级契约：5 处接入缺一不可。"""
    source = Path("app/services/permission_service.py").read_text(encoding="utf-8")

    assert source.count('resource_type="forbidden_skill"') == 2, "用户级与角色级保存各需一处"
    # 删除范围现在是按 model_fields_set 条件追加的映射表（F5：未提交的字段不重建记录），
    # 用户级与角色级各有一份。
    assert source.count('("forbidden_skills", "forbidden_skill"),') == 2
    assert 'p.resource_type == "forbidden_skill"' in source
    assert "details.forbidden_skills = [" in source
