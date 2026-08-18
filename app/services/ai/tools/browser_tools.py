import json
from typing import Optional

from app.core.context import get_current_agent_context
from app.core.orm import AsyncSessionLocal
from app.services.ai.browser.browser_runtime import browser_runtime
from app.services.ai.tools.tool_compat import tool


def _context_or_error():
    context = get_current_agent_context()
    if context is None or context.user_id is None:
        raise RuntimeError("浏览器工具需要登录用户上下文")
    return context


def _session_id(context) -> str:
    session_id = getattr(context, "browser_session_id", None)
    if not session_id:
        raise RuntimeError("当前对话尚未绑定右侧浏览器会话")
    return str(session_id)


async def _owned_session(context):
    from app.services.ai.browser.browser_session_service import BrowserSessionService

    session_id = _session_id(context)
    async with AsyncSessionLocal() as db:
        return await BrowserSessionService(db).get_owned_session(
            user_id=int(context.user_id), session_id=session_id
        )


@tool
async def browser_open(url: str = "https://www.baidu.com/", profile_id: Optional[str] = None) -> str:
    """打开或恢复当前用户的服务端浏览器，会话登录状态可跨对话复用。"""
    context = _context_or_error()
    session = await browser_runtime.open_for_user(
        user_id=int(context.user_id),
        conversation_id=getattr(context, "conversation_id", None),
        url=url,
        profile_id=profile_id,
    )
    context.browser_session_id = session.id
    snapshot = await browser_runtime.snapshot(session.id)
    return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)


@tool
async def browser_snapshot() -> str:
    """读取当前服务端浏览器页面的语义快照，返回可供 click/fill 使用的 target_ref。"""
    context = _context_or_error()
    session = await _owned_session(context)
    snapshot = await browser_runtime.snapshot(session.id)
    return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)


@tool
async def browser_click(
    target_ref: str,
    snapshot_id: str,
) -> str:
    """按快照中的语义 target_ref 点击页面元素；执行前由 AgentScope 运行时权限确认。"""
    context = _context_or_error()
    session_id = _session_id(context)
    async with AsyncSessionLocal() as db:
        from app.services.ai.browser.browser_session_service import BrowserSessionService

        session = await BrowserSessionService(db).get_owned_session(
            user_id=int(context.user_id), session_id=session_id
        )
        result = await browser_runtime.click(
            session_id,
            target_ref=target_ref,
            snapshot_id=snapshot_id,
            approval_mode=session.approval_mode,
            # 只有 AgentScope 已通过 check_permissions 才会进入工具调用；
            # confirmed 不暴露给模型，避免模型参数绕过 guarded 模式。
            confirmed=True,
        )
        session.current_url = result.url
        session.page_title = result.title
        await db.commit()
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)


@tool
async def browser_fill(
    target_ref: str,
    snapshot_id: str,
    value: str,
) -> str:
    """向当前浏览器语义输入框填值；敏感值不会进入工具结果或审计预览。"""
    context = _context_or_error()
    session_id = _session_id(context)
    await _owned_session(context)
    result = await browser_runtime.fill(
        session_id,
        target_ref=target_ref,
        snapshot_id=snapshot_id,
        value=value,
        sensitive=None,
    )
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
