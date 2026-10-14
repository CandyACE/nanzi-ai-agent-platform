"""技能清单接口的 ``forbidden`` 标记必须支持智能体作用域。

背景：`GET /api/portal/skills` 下发的 `forbidden` 决定前端技能中心是否置灰。它原先只按
全局用算（`get_forbidden_skill_ids(user_id)`），于是"只在该智能体被禁"的技能显示为可挂载，
用户挂上后被后端 `drop_forbidden_skill_items` 静默丢弃（只写 warning 日志），界面全无反馈。

本用例钉住两件事：接口**接受** `agent_id`，且**原样透传**给策略层。
"""

import pytest

from app.api.portal.endpoints import skills as skills_module

pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_list_skills_passes_agent_scope_to_the_policy(tmp_path, monkeypatch):
    """接口必须把 agent_id 透传给 get_forbidden_skill_ids。"""
    import app.services.ai.skills.policy as policy
    from app.core.config import settings

    skill_dir = tmp_path / "skills" / "pdf"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# PDF\n描述", encoding="utf-8")
    # SKILLS_DIR 是 config.Settings 上的 **property**（不是字段），所以既不能 setattr、
    # model_copy(update=...) 也改不动它——只能在类上替换属性本身，monkeypatch 事后还原。
    monkeypatch.setattr(
        type(settings),
        "SKILLS_DIR",
        property(lambda self: str(tmp_path / "skills")),
    )

    captured = {}

    async def fake_get_forbidden_skill_ids(explicit_user_id=None, explicit_agent_id=None):
        captured["user_id"] = explicit_user_id
        captured["agent_id"] = explicit_agent_id
        return {"pdf"}

    monkeypatch.setattr(policy, "get_forbidden_skill_ids", fake_get_forbidden_skill_ids)

    result = await skills_module.list_skills(user={"user_id": 178}, agent_id="agent-x")

    assert captured["agent_id"] == "agent-x", (
        "agent_id 必须透传，否则 forbidden 只有全局口径，智能体级禁用在前端不可见"
    )
    assert captured["user_id"] == 178
    assert result["data"][0]["forbidden"] is True, "透传后标记应落到条目上"


@pytest.mark.asyncio
async def test_list_skills_without_agent_scope_stays_global(tmp_path, monkeypatch):
    """不传 agent_id 时保持既有行为（全局口径），旧调用方不受影响。"""
    import app.services.ai.skills.policy as policy
    from app.core.config import settings

    skill_dir = tmp_path / "skills" / "pdf"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# PDF", encoding="utf-8")
    # SKILLS_DIR 是 config.Settings 上的 **property**（不是字段），所以既不能 setattr、
    # model_copy(update=...) 也改不动它——只能在类上替换属性本身，monkeypatch 事后还原。
    monkeypatch.setattr(
        type(settings),
        "SKILLS_DIR",
        property(lambda self: str(tmp_path / "skills")),
    )

    captured = {}

    async def fake_get_forbidden_skill_ids(explicit_user_id=None, explicit_agent_id=None):
        captured["agent_id"] = explicit_agent_id
        return set()

    monkeypatch.setattr(policy, "get_forbidden_skill_ids", fake_get_forbidden_skill_ids)

    # 显式传 None：直接调用函数时 FastAPI 不解析 Query(None) 默认值（拿到的是 Query 对象）
    result = await skills_module.list_skills(user={"user_id": 178}, agent_id=None)

    assert captured["agent_id"] is None
    assert result["data"][0]["forbidden"] is False
