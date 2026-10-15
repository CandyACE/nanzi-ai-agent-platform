"""聊天接口消息模型的契约：附件类型与技能来源口径（scope）都不能在解析时丢掉。

``ChatCompletionRequest.messages[].files[]`` 里的 ``scope`` 是"这份技能属于谁"的唯一来源标记。
Pydantic 2 默认 ``extra='ignore'``：未声明的字段会被**静默丢弃**（连 warning 都没有），而
``create_chat_completion`` 用 ``[msg.model_dump() for msg in ...]`` 还原历史消息，一丢就再也
拿不回来——下游只能按公共技能处理个人技能。这里把"能解析出来、能原样带回、怪值不炸"钉死。
"""

import logging

import pytest

from app.api.v1.endpoints.chat import ChatCompletionRequest, ChatFile, ChatMessage, SkillMeta


pytestmark = pytest.mark.no_infrastructure


def _skill_file(**overrides) -> dict:
    payload = {
        "type": "skill",
        "url": "brainstorming",
        "filename": "brainstorming (技能)",
        "size": 0,
        "ext": "skill",
    }
    payload.update(overrides)
    return payload


def test_chat_message_preserves_skill_file_type():
    """
    Skill selections must survive request parsing so the service can load SKILL.md
    instead of treating the skill id as an uploaded file path.
    """
    message = ChatMessage(
        role="user",
        content="",
        files=[
            {
                "type": "skill",
                "url": "brainstorming",
                "filename": "brainstorming (技能)",
                "size": 0,
                "ext": "skill",
            }
        ],
    )

    dumped = message.dict()

    assert dumped["files"][0]["type"] == "skill"
    assert dumped["files"][0]["url"] == "brainstorming"


# ---------------------------------------------------------------------------
# scope：解析、缺省、非法值
# ---------------------------------------------------------------------------

def test_chat_file_keeps_scope_from_frontend_payload():
    """前端 handleSelectSkill 在附件与 skillMeta 两处都发 scope，两处都必须解析出来。"""
    payload = _skill_file(
        scope="personal",
        skillMeta={"id": "brainstorming", "name": "头脑风暴", "description": "", "scope": "personal"},
    )

    file_obj = ChatFile(**payload)

    assert file_obj.scope == "personal"
    assert file_obj.skillMeta is not None
    assert file_obj.skillMeta.scope == "personal"


def test_chat_file_scope_defaults_to_none_when_absent():
    """老前端 / 老历史没有 scope：缺省必须是 None（=公共口径），不能因为新增字段而 422。"""
    file_obj = ChatFile(**_skill_file())

    assert file_obj.scope is None
    assert SkillMeta(**{"id": "x"}).scope is None
    assert SkillMeta(**{"id": "x", "scope": None}).scope is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("personal", "personal"),
        ("PERSONAL", "personal"),
        (" personal ", "personal"),
        ("global", "public"),
        ("public", "public"),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_chat_scope_is_normalized_to_two_values(raw, expected):
    """归一化到 personal / public：前端写 global、历史写 public，下游只该看到一种写法。"""
    assert SkillMeta(id="x", scope=raw).scope == expected
    assert ChatFile(**_skill_file(scope=raw)).scope == expected


@pytest.mark.parametrize("raw", ["weird", "个人信息", 0, 1, {"scope": "personal"}, ["personal"]])
def test_chat_scope_never_raises_on_unknown_value(raw, caplog):
    """非法值按"未指定"处理并留 warning：它来自客户端载荷，不能因为拼错就整轮 500。"""
    with caplog.at_level(logging.WARNING):
        file_obj = ChatFile(**_skill_file(scope=raw))
        meta = SkillMeta(**{"id": "x", "scope": raw})

    assert file_obj.scope is None
    assert meta.scope is None
    assert any("未知技能 scope" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------
# 历史消息 round-trip：scope 必须能带回来
# ---------------------------------------------------------------------------

def test_scope_survives_history_roundtrip():
    """``create_chat_completion`` 的历史还原路径：model_dump → 重新构造请求，scope 不能丢。

    这是本缺陷的关键一环：字段没声明时 model_dump() 里根本没有 scope，注入器只能把个人技能
    当成公共技能（按公共库解析 SKILL.md、被公共禁用集合连坐）。
    """
    request = ChatCompletionRequest(
        messages=[
            {
                "role": "user",
                "content": "",
                "files": [
                    _skill_file(
                        scope="personal",
                        skillMeta={"id": "brainstorming", "name": "头脑风暴", "scope": "personal"},
                    )
                ],
            }
        ]
    )

    # 与 app/api/v1/endpoints/chat.py 里的 history 还原完全一致
    history = [msg.model_dump() for msg in request.messages]

    assert history[0]["files"][0]["scope"] == "personal", "顶层附件 scope 丢了"
    assert history[0]["files"][0]["skillMeta"]["scope"] == "personal", "skillMeta.scope 丢了"

    restored = ChatCompletionRequest(messages=history)
    restored_file = restored.messages[0].files[0]
    assert restored_file.scope == "personal"
    assert restored_file.skillMeta is not None
    assert restored_file.skillMeta.scope == "personal"


def test_scope_missing_from_payload_has_no_scope_key_to_lose():
    """反向对照：修复前附件里根本没有 scope 这个键，下游无从判断来源。"""
    file_obj = ChatFile(**_skill_file())

    assert file_obj.model_dump()["scope"] is None

    lossy = _skill_file()  # 模拟"字段未声明"时下游实际拿到的 dict：没有任何来源标记
    assert "scope" not in lossy
