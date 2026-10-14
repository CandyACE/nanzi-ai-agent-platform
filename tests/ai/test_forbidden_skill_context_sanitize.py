"""禁用公共技能：挂载提示的清洗时机与语义。

修复前的缺口：前端把 `/app/data/skills/<id>/SKILL.md` 拼进"可直接读"的提示里，后端
``enrich_messages_with_skill_meta`` 还会兜底重写；注入过滤只改 ``active_skills`` 局部列表，
既不动 ``messages[-1]["files"]``，也不清洗已写进 ``content`` 的提示——而那段 content 会被
``context_step`` 原样落进会话历史，等于每轮都在提示模型"这个被禁技能可以读"。

本文件钉住三件事：
1. 清洗必须发生在**写历史之前**（``memory_service.add_message``）与**重建提示之前**
   （``enrich_messages_with_skill_meta``）；
2. 提示里的技能身份标记两种都要认——新格式靠「技能 ID」，历史格式靠 SKILL.md 绝对路径
   （禁用特性上线前落库的老会话里只有后者），任一条失效都会让被禁技能重新进模型；
3. 清洗后不留被禁技能的任何身份信息（含紧随的 skills meta 行），但同名个人技能与
   其他附件提示不受影响。
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
    """**历史格式**：禁用特性上线前落库的老会话里就是这个形状（带绝对路径）。"""
    return (
        f"用户本轮已调用生态技能工作流：{name}，对应的物理描述文件绝对路径是："
        f"/app/data/skills/{skill_id}/SKILL.md。\nskills meta 为：name: {name}"
    )


def _new_mount_hint(name: str = "Gamma", skill_id: str = "gamma") -> str:
    """**当前格式**：不再带任何文件系统路径，只有「技能 ID」这一个身份标记。"""
    return (
        f"用户本轮已调用生态技能工作流：{name}（技能 ID：{skill_id}）。"
        f"其 SKILL.md 正文已随本轮上下文预载，本轮直接按预载指令执行，无需再读取技能文件；"
        f"如需读取该技能附带的脚本或资源，请先用 list_accessible_directories "
        f"查询技能目录的真实位置。\nskills meta 为：name: {name}"
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


@pytest.mark.parametrize(
    "hint_builder",
    [_mount_hint, _new_mount_hint],
    ids=["历史格式", "新格式"],
)
def test_sanitizer_keeps_same_named_personal_skill(hint_builder):
    """产品口径：禁的是平台发布的那一份，同名个人技能照旧可用、提示也照旧。"""
    hint = hint_builder("Alpha", "alpha")
    messages = [
        {
            "role": "user",
            "content": "用 alpha 技能\n\n---\n\n" + hint,
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
    assert hint in messages[0]["content"]
    assert len(messages[0]["files"]) == 1


def test_sanitizer_rewrites_new_format_hint_by_skill_id():
    """新格式不带路径，清洗只能靠「技能 ID」标记——漏了它，被禁技能会再次进模型。"""
    messages = [
        {
            "role": "user",
            "content": "帮我做表\n\n---\n\n" + _new_mount_hint(),
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

    removed = sanitize_forbidden_skill_context(messages, {"gamma"})

    assert removed == 1
    content = messages[0]["content"]
    assert "技能 ID：gamma" not in content
    # 说明行与紧随其后的 meta 行是同一组：说明行被摘掉后 meta 行也必须摘掉，
    # 否则技能描述照旧留在提示里
    assert "skills meta 为：name: Gamma" not in content
    assert "已被管理员禁用" in content
    assert "帮我做表" in content


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
    """反向断言：未被禁的技能照旧挂载、照旧带 meta，且提示里不再有任何文件系统路径。"""
    messages = [
        {
            "role": "user",
            "content": "用 alpha 技能\n\n---\n\n" + _new_mount_hint("Alpha", "alpha"),
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
    stored_content = add_message.await_args.args[3]
    assert "技能 ID：alpha" in stored_content
    assert "/app/data/skills" not in stored_content
    dumped = json.dumps(ctx.messages, ensure_ascii=False)
    assert "/app/data/skills" not in dumped
    assert "skills meta 为：" in dumped


@pytest.mark.asyncio
async def test_context_step_upgrades_legacy_history_hint_for_allowed_skill():
    """未被禁的老提示也要升级：死路径照旧会把模型骗去读一次不存在的文件。

    这是「只在内存快照上升级」的语义——数据库里的历史一个字都不改，但进模型的
    那一份必须是新文案。
    """
    history = [
        {
            "role": "user",
            "content": "老问题\n\n---\n\n" + _mount_hint("Alpha", "alpha"),
            "files": [{"type": "skill", "url": "alpha", "filename": "Alpha (技能)"}],
        },
        {"role": "assistant", "content": "好的"},
    ]

    ctx, add_message = await _run_context_step(
        [{"role": "user", "content": "继续"}], history=history, forbidden=set()
    )

    model_view = json.dumps(
        [ctx.messages, ctx.shared_state["context_source_history"]], ensure_ascii=False
    )
    assert "/app/data/skills" not in model_view
    assert "技能 ID：alpha" in model_view
    assert "skills meta 为：name: Alpha" in model_view, "meta 行要原样保留（升级只重写说明行）"
    assert "老问题" in model_view, "用户自己的历史正文不动"
    # 落库的是当前轮，本来就该是干净的新格式
    assert "/app/data/skills" not in add_message.await_args.args[3]


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


def test_legacy_hint_upgrade_runs_after_sanitize_and_before_the_model_sees_them():
    """升级必须排在禁用清洗之后：被禁技能的整块提示已换成禁令，不能再被升级回正常文案。"""
    source = Path("app/services/ai/pipeline/steps/context_step.py").read_text(encoding="utf-8")

    assert source.index(
        "sanitize_forbidden_skill_context(messages, forbidden_skill_ids)"
    ) < source.index("upgrade_legacy_skill_mount_hints(messages)")
    assert source.index(
        "sanitize_forbidden_skill_context(server_history, forbidden_skill_ids)"
    ) < source.index("upgrade_legacy_skill_mount_hints(server_history)")
    # 历史快照的升级要发生在它被塞进 shared_state / 交给模型之前
    assert source.index("upgrade_legacy_skill_mount_hints(server_history)") < source.index(
        'context.shared_state["context_source_history"]'
    )
    assert source.index("upgrade_legacy_skill_mount_hints(server_history)") < source.index(
        "context.messages = messages"
    )
