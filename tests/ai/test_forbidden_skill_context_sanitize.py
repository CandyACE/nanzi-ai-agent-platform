"""禁用公共技能：挂载提示的清洗时机与语义。

修复前的缺口：前端把 `/app/data/skills/<id>/SKILL.md` 拼进"可直接读"的提示里，后端
``enrich_messages_with_skill_meta`` 还会兜底重写；注入过滤只改 ``active_skills`` 局部列表，
既不动 ``messages[-1]["files"]``，也不清洗已写进 ``content`` 的提示——而那段 content 会被
``context_step`` 原样落进会话历史，等于每轮都在提示模型"这个被禁技能可以读"。

本文件钉住两件事：
1. 清洗必须发生在**写历史之前**（``memory_service.add_message``）与**重建提示之前**
   （``enrich_messages_with_skill_meta``）；
2. 清洗后不留任何被禁技能的绝对路径，但同名个人技能与其他附件提示不受影响。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.memory_service import memory_service
from app.services.ai.pipeline.context import PipelineContext
from app.services.ai.pipeline.steps.context_step import ContextStep
from app.utils.skill_metadata import sanitize_forbidden_skill_context

pytestmark = pytest.mark.no_infrastructure

USER_INFO = {"u_id_val": 1, "id": 1, "user_id": 1, "user_name": "alice", "role": "user"}
FORBIDDEN_PATH = "/app/data/skills/gamma/SKILL.md"


def _mount_hint(name: str = "Gamma", skill_id: str = "gamma") -> str:
    return (
        f"用户本轮已调用生态技能工作流：{name}，对应的物理描述文件绝对路径是："
        f"/app/data/skills/{skill_id}/SKILL.md。\nskills meta 为：name: {name}"
    )


# --------------------------------------------------------------------------- #
# 1. 纯函数：清洗语义
# --------------------------------------------------------------------------- #


def test_sanitizer_drops_forbidden_attachment_and_rewrites_its_hint():
    messages = [
        {
            "role": "user",
            "content": (
                "帮我做表"
                "\n\n---\n\n"
                + _mount_hint()
                + "\n\n用户本轮已上传图片：a.png，该图片已作为视觉多模态输入随消息一并发送"
                "（托管路径：/app/data/uploads/a.png）。"
            ),
            "files": [
                {"type": "skill", "url": "gamma", "filename": "Gamma (技能)", "skillMeta": {"scope": "global"}},
                {"type": "upload", "url": "/api/v1/chat/fs/preview?path=/app/data/uploads/a.png"},
            ],
        }
    ]

    removed = sanitize_forbidden_skill_context(messages, {"gamma"})

    assert removed == 1
    assert [item["url"] for item in messages[0]["files"]] == [
        "/api/v1/chat/fs/preview?path=/app/data/uploads/a.png"
    ]
    content = messages[0]["content"]
    assert FORBIDDEN_PATH not in content
    assert "/app/data/skills/gamma" not in content
    assert "已被管理员禁用" in content
    # 用户正文与其他附件提示原样保留
    assert "帮我做表" in content
    assert "/app/data/uploads/a.png" in content


def test_sanitizer_keeps_same_named_personal_skill():
    """产品口径：禁的是平台发布的那一份，同名个人技能照旧可用、提示也照旧。"""
    messages = [
        {
            "role": "user",
            "content": "用 alpha 技能\n\n---\n\n" + _mount_hint("Alpha", "alpha"),
            "files": [
                {
                    "type": "skill",
                    "url": "alpha",
                    "filename": "Alpha (技能)",
                    "skillMeta": {"scope": "personal"},
                }
            ],
        }
    ]

    assert sanitize_forbidden_skill_context(messages, {"alpha"}) == 0
    assert "/app/data/skills/alpha/SKILL.md" in messages[0]["content"]
    assert len(messages[0]["files"]) == 1


def test_sanitizer_is_a_noop_without_forbidden_ids():
    content = _mount_hint()
    messages = [
        {"role": "user", "content": content, "files": [{"type": "skill", "url": "gamma"}]}
    ]

    assert sanitize_forbidden_skill_context(messages, set()) == 0
    assert messages[0]["content"] == content
    assert len(messages[0]["files"]) == 1


# --------------------------------------------------------------------------- #
# 2. ContextStep：写历史之前清洗
# --------------------------------------------------------------------------- #


async def _run_context_step(messages, *, history=None, forbidden={"gamma"}):
    ctx = PipelineContext(
        messages=messages,
        user_info=USER_INFO,
        conversation_id="conv-1",
    )
    with (
        patch.object(
            memory_service,
            "get_history",
            AsyncMock(return_value=list(history or [])),
        ),
        patch.object(memory_service, "add_message", AsyncMock()) as add_message,
        patch(
            "app.services.ai.pipeline.steps.context_step._apply_context_snapshot",
            AsyncMock(side_effect=lambda server_history, **_kwargs: server_history),
        ),
        patch(
            "app.services.config_service.ConfigService.get",
            AsyncMock(return_value="60"),
        ),
        patch(
            "app.services.ai.skills.policy.get_forbidden_skill_ids",
            AsyncMock(return_value=set(forbidden)),
        ),
    ):
        async for _chunk in ContextStep(None).run(ctx):
            pass
    return ctx, add_message


@pytest.mark.asyncio
async def test_context_step_cleans_forbidden_mount_before_history_write():
    messages = [
        {
            "role": "user",
            "content": "帮我做表\n\n---\n\n" + _mount_hint(),
            "files": [
                {
                    "type": "skill",
                    "url": "gamma",
                    "filename": "Gamma (技能)",
                    "skillMeta": {"scope": "global"},
                }
            ],
        }
    ]

    ctx, add_message = await _run_context_step(messages)

    assert add_message.await_count == 1
    stored_content = add_message.await_args.args[3]
    stored_files = add_message.await_args.kwargs["files"]
    assert "/app/data/skills/gamma" not in stored_content
    assert "已被管理员禁用" in stored_content
    assert stored_files == []
    # user_query 也不能带着被禁技能的可读路径进路由 / 技能扫描
    assert "SKILL.md" not in ctx.user_query
    assert "/app/data/skills/gamma" not in json.dumps(ctx.messages, ensure_ascii=False)


@pytest.mark.asyncio
async def test_context_step_cleans_old_history_hints_before_model():
    """禁用**之前**写进历史的旧提示同样会随窗口进模型，必须在读取侧一并净化。"""
    history = [
        {
            "role": "user",
            "content": "老问题\n\n---\n\n" + _mount_hint(),
            "files": [{"type": "skill", "url": "gamma", "filename": "Gamma (技能)"}],
        },
        {"role": "assistant", "content": "好的"},
    ]

    ctx, _add_message = await _run_context_step([{"role": "user", "content": "新问题"}], history=history)

    dumped = json.dumps(ctx.messages, ensure_ascii=False)
    assert "/app/data/skills/gamma" not in dumped
    assert "已被管理员禁用" in dumped
    assert "/app/data/skills/gamma" not in json.dumps(
        ctx.shared_state["context_source_history"], ensure_ascii=False
    )


@pytest.mark.asyncio
async def test_context_step_keeps_allowed_skill_mount_and_still_enriches_it():
    """反向断言：未被禁的技能照旧挂载、照旧生成"可直接读"的提示与 meta。"""
    messages = [
        {
            "role": "user",
            "content": "用 alpha 技能\n\n---\n\n" + _mount_hint("Alpha", "alpha"),
            "files": [
                {
                    "type": "skill",
                    "url": "alpha",
                    "filename": "Alpha (技能)",
                    "skillMeta": {"name": "Alpha", "description": "演示", "scope": "global"},
                }
            ],
        }
    ]

    ctx, add_message = await _run_context_step(messages)

    stored_files = add_message.await_args.kwargs["files"]
    assert [item["url"] for item in stored_files] == ["alpha"]
    assert "/app/data/skills/alpha/SKILL.md" in add_message.await_args.args[3]
    assert "/app/data/skills/alpha/SKILL.md" in json.dumps(ctx.messages, ensure_ascii=False)
    assert "skills meta 为：" in json.dumps(ctx.messages, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# 3. 源码级时序契约
# --------------------------------------------------------------------------- #


def test_sanitize_runs_before_history_write_and_before_enrichment():
    source = Path("app/services/ai/pipeline/steps/context_step.py").read_text(encoding="utf-8")

    current_message_sanitize = source.index(
        "sanitize_forbidden_skill_context(messages, forbidden_skill_ids)"
    )
    history_sanitize = source.index(
        "sanitize_forbidden_skill_context(server_history, forbidden_skill_ids)"
    )
    assert current_message_sanitize < source.index("await memory_service.add_message(")
    assert current_message_sanitize < source.index("context.user_query = user_query")
    assert current_message_sanitize < source.index("enrich_messages_with_skill_meta(messages)")
    assert history_sanitize < source.index("context.messages = messages")
