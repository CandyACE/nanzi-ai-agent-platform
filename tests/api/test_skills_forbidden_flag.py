"""技能列表接口的禁用标记：被禁技能仍返回，但带 ``forbidden`` 供前端置灰。

为什么不直接从列表里剔除：用户需要看见"技能还在、但被管理员禁用了"，
否则只会认为技能丢了（产品已确认：置灰不可选 + 写明原因）。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from app.api.portal.endpoints import skills as skills_endpoint


pytestmark = pytest.mark.no_infrastructure


def _write_skill(root: Path, skill_id: str) -> None:
    skill_dir = root / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: 演示 {skill_id}\n---\n\n# {skill_id}\n",
        encoding="utf-8",
    )


@pytest.fixture()
def skills_env(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "docx")
    _write_skill(root, "pdf")
    # SKILLS_DIR 是只读 property，只能按既有测试的写法用 PropertyMock 顶替
    with patch("app.core.config.Settings.SKILLS_DIR", new_callable=PropertyMock) as mock_dir:
        mock_dir.return_value = str(root)
        yield root


@pytest.mark.asyncio
async def test_forbidden_skills_are_flagged_but_still_listed(skills_env):
    with patch(
        "app.services.ai.skills.policy.get_forbidden_skill_ids",
        AsyncMock(return_value={"docx"}),
    ):
        response = await skills_endpoint.list_skills(user={"user_id": 1})

    by_id = {item["id"]: item for item in response["data"]}
    assert set(by_id) == {"docx", "pdf"}, "被禁技能必须仍在列表里（前端要显示并说明原因）"
    assert by_id["docx"]["forbidden"] is True
    assert by_id["pdf"]["forbidden"] is False


@pytest.mark.asyncio
async def test_nothing_is_flagged_when_the_user_has_no_forbidden_skills(skills_env):
    with patch(
        "app.services.ai.skills.policy.get_forbidden_skill_ids",
        AsyncMock(return_value=set()),
    ):
        response = await skills_endpoint.list_skills(user={"user_id": 1})

    assert all(item["forbidden"] is False for item in response["data"])


@pytest.mark.asyncio
async def test_policy_failure_degrades_to_unflagged_instead_of_failing_the_request(skills_env):
    """禁用策略查不动时不能让技能列表整个 500——退化为不标记，功能可用性优先。"""
    with patch(
        "app.services.ai.skills.policy.get_forbidden_skill_ids",
        AsyncMock(side_effect=RuntimeError("policy down")),
    ):
        response = await skills_endpoint.list_skills(user={"user_id": 1})

    assert len(response["data"]) == 2
    assert all(item["forbidden"] is False for item in response["data"])
