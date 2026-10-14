"""``create_skills`` 的覆盖语义回归测试。

回归背景：该工具此前是**静默 upsert**——``makedirs(exist_ok=True)`` 之后直接
``open(w)`` 整份覆盖已存在的 SKILL.md，却无条件返回 ``NANZI_SKILL_CREATED``，
前端据此弹「已创建个人技能」横幅。用户以为新增了一个技能，实际把已有技能
（可能已被发布成平台技能、已被智能体的 resource_scope 挂载）的正文清空替换。

现在的契约：
* 不存在 → 写入并返回 ``NANZI_SKILL_CREATED``；
* 已存在且未显式 ``overwrite=True`` → **不碰磁盘**，返回 ``NANZI_SKILL_EXISTS``；
* 已存在且 ``overwrite=True`` → 覆盖并返回 ``NANZI_SKILL_UPDATED``（文案/横幅随之区分）。
"""
from __future__ import annotations

import pytest

from app.services.ai.tools import system_executive_tools as exec_tools
from app.utils.context import current_user_info

pytestmark = pytest.mark.no_infrastructure

SKILL_MD = """---
name: 演示技能
description: 用于回归测试
---

按步骤执行。
"""


class _ContextStub:
    """最小 contextvar 替身：让工具内的 ``current_user_info.get()`` 拿到测试用户。"""

    def __init__(self, value):
        self._value = value

    def get(self, default=None):
        return self._value


@pytest.fixture
def personal_root(tmp_path, monkeypatch):
    """把个人技能根指向临时目录，并放行路径校验与用户身份。"""
    root = tmp_path / "personal" / "skills"
    root.mkdir(parents=True)
    monkeypatch.setattr(exec_tools, "validate_safe_path", lambda path: path)
    monkeypatch.setattr(
        "app.services.ai.skill_resolver.get_user_personal_skills_dir",
        lambda user_info: str(root),
    )
    monkeypatch.setattr(
        "app.services.ai.skill_resolver.resolve_personal_skill_dir",
        lambda skills_dir, skill_id: None,
    )
    # 工具内部是 `from app.utils.context import current_user_info`：局部导入每次都会
    # 重新取模块属性，因此打桩模块属性即可生效。
    monkeypatch.setattr(
        "app.utils.context.current_user_info",
        _ContextStub({"id": 1, "name": "tester", "role": "user"}),
    )
    return root


def _call(skill_id: str, content: str = SKILL_MD, **kwargs) -> str:
    return exec_tools.create_skills.func(
        skill_id=skill_id,
        name="演示技能",
        description="用于回归测试",
        skill_md_content=content,
        **kwargs,
    )


def test_first_creation_emits_created_marker(personal_root):
    result = _call("demo-skill")
    assert "NANZI_SKILL_CREATED:" in result
    assert "NANZI_SKILL_EXISTS:" not in result
    assert (personal_root / "demo-skill" / "SKILL.md").read_text(encoding="utf-8") == SKILL_MD


def test_second_call_without_overwrite_does_not_touch_disk(personal_root):
    """默认必须拒写：这是本次修复的核心，避免「以为新建、其实替换」。"""
    _call("demo-skill")
    skill_md = personal_root / "demo-skill" / "SKILL.md"
    original = skill_md.read_text(encoding="utf-8")

    result = _call("demo-skill", content="# 完全不同的新内容\n")

    assert "NANZI_SKILL_EXISTS:" in result
    assert "NANZI_SKILL_CREATED:" not in result
    assert "未做任何修改" in result
    # 磁盘内容必须一模一样
    assert skill_md.read_text(encoding="utf-8") == original


def test_explicit_overwrite_replaces_and_emits_updated_marker(personal_root):
    _call("demo-skill")
    skill_md = personal_root / "demo-skill" / "SKILL.md"

    result = _call("demo-skill", content="# 新版正文\n", overwrite=True)

    assert "NANZI_SKILL_UPDATED:" in result
    assert "NANZI_SKILL_CREATED:" not in result
    assert "已覆盖更新" in result
    assert skill_md.read_text(encoding="utf-8") == "# 新版正文\n"


def test_marker_payload_is_parseable(personal_root):
    """标记必须是可直接 JSON 解析的单行载荷（前端正则依赖它）。"""
    import json

    result = _call("demo-skill")
    marker = [line for line in result.splitlines() if line.startswith("NANZI_SKILL_CREATED:")][0]
    payload = json.loads(marker.split(":", 1)[1])
    assert payload == {"skill_id": "demo-skill", "scope": "personal", "name": "演示技能"}
