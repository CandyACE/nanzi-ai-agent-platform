import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

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


async def _persist_browser_result(context: Any, result: Any) -> None:
    """把页面动作后的 URL 和标题写回会话，保证恢复时不会回到旧页面。"""
    if not getattr(result, "url", None) and not getattr(result, "title", None):
        return
    from app.services.ai.browser.browser_session_service import BrowserSessionService

    async with AsyncSessionLocal() as db:
        session = await BrowserSessionService(db).get_owned_session(
            user_id=int(context.user_id), session_id=_session_id(context)
        )
        if getattr(result, "url", None):
            session.current_url = result.url
        if getattr(result, "title", None):
            session.page_title = result.title
        session.last_seen_at = datetime.now()
        session.updated_at = datetime.now()
        await db.commit()


async def _browser_result_json(context: Any, result: Any) -> str:
    await _persist_browser_result(context, result)
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)


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
    payload = snapshot.model_dump(mode="json")
    payload["approval_mode"] = session.approval_mode
    return json.dumps(payload, ensure_ascii=False)


@tool
async def browser_snapshot() -> str:
    """读取当前服务端浏览器页面的语义快照，返回 target_ref、滚动元数据和页面文本；目标未出现时先滚动，不要伪造引用或无状态重复读取。"""
    context = _context_or_error()
    session = await _owned_session(context)
    snapshot = await browser_runtime.snapshot(session.id)
    return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)


@tool
async def browser_scroll(
    direction: Literal["up", "down", "top", "bottom"] = "down",
    amount: int = 640,
) -> str:
    """滚动当前服务端浏览器页面，并返回包含截图、页面文本和最新 target_ref 的新快照。"""
    context = _context_or_error()
    session = await _owned_session(context)
    snapshot = await browser_runtime.scroll(
        session.id,
        direction=direction,
        amount=amount,
    )
    return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)


@tool
async def browser_press(
    key: str,
    target_ref: Optional[str] = None,
    snapshot_id: Optional[str] = None,
) -> str:
    """向当前焦点或快照目标发送有限键盘操作，如 Enter、Tab、Escape 或方向键。"""
    context = _context_or_error()
    session = await _owned_session(context)
    if target_ref and not snapshot_id:
        raise ValueError("按目标发送键盘操作需要 snapshot_id")
    result = await browser_runtime.press(
        session.id,
        target_ref=target_ref,
        snapshot_id=snapshot_id,
        key=key,
    )
    return await _browser_result_json(context, result)


@tool
async def browser_wait_for(
    condition: Literal["text", "url", "target", "page_state"] = "text",
    value: str = "",
    timeout_ms: int = 5000,
) -> str:
    """等待页面文本、URL、可见目标或页面状态满足条件，并返回最新快照。"""
    context = _context_or_error()
    session = await _owned_session(context)
    snapshot = await browser_runtime.wait_for(
        session.id,
        condition=condition,
        value=value,
        timeout_ms=timeout_ms,
    )
    return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)


@tool
async def browser_select_option(
    target_ref: str,
    snapshot_id: str,
    value: Optional[str] = None,
    label: Optional[str] = None,
) -> str:
    """选择当前快照中的原生下拉框选项。value 和 label 至少提供一个。"""
    context = _context_or_error()
    session = await _owned_session(context)
    result = await browser_runtime.select_option(
        session.id,
        target_ref=target_ref,
        snapshot_id=snapshot_id,
        value=value,
        label=label,
    )
    return await _browser_result_json(context, result)


@tool
async def browser_read_visible() -> str:
    """读取当前截图视口内的页面文字，适合长列表等非交互内容。"""
    context = _context_or_error()
    session = await _owned_session(context)
    payload = await browser_runtime.read_visible(session.id)
    return json.dumps(payload, ensure_ascii=False)


@tool
async def browser_hover(target_ref: str, snapshot_id: str) -> str:
    """悬停当前快照目标，以展开菜单、日期选择器或提示信息。"""
    context = _context_or_error()
    session = await _owned_session(context)
    result = await browser_runtime.hover(session.id, target_ref=target_ref, snapshot_id=snapshot_id)
    return await _browser_result_json(context, result)


@tool
async def browser_drag(
    source_ref: str,
    target_ref: str,
    snapshot_id: str,
) -> str:
    """将当前快照中的一个目标拖到另一个目标。"""
    context = _context_or_error()
    session = await _owned_session(context)
    result = await browser_runtime.drag(
        session.id,
        source_ref=source_ref,
        target_ref=target_ref,
        snapshot_id=snapshot_id,
    )
    return await _browser_result_json(context, result)


@tool
async def browser_slider_drag(
    source_ref: str,
    snapshot_id: str,
    distance_px: int | None = None,
    gap_target_ref: str | None = None,
) -> str:
    """对滑块做拟人轨迹的坐标级拖拽，可配合缺口间距测量。

    - 提供 ``distance_px``：直接横向拖动指定的像素距离；
    - 或提供 ``gap_target_ref``：自动测量滑块与缺口元素的间距后拖动到缺口；
    - 两者至少提供其一。用于处理滑块验证图片等场景。
    """
    context = _context_or_error()
    session = await _owned_session(context)
    result = await browser_runtime.slider_drag(
        session.id,
        source_ref=source_ref,
        snapshot_id=snapshot_id,
        distance_px=distance_px,
        gap_target_ref=gap_target_ref,
    )
    return await _browser_result_json(context, result)


async def _browser_history_action(action: Literal["back", "forward", "reload"]) -> str:
    context = _context_or_error()
    session = await _owned_session(context)
    result = await browser_runtime.navigate_history(session.id, action=action)
    return await _browser_result_json(context, result)


@tool
async def browser_back() -> str:
    """返回当前浏览器历史记录上一页。"""
    return await _browser_history_action("back")


@tool
async def browser_forward() -> str:
    """前进当前浏览器历史记录下一页。"""
    return await _browser_history_action("forward")


@tool
async def browser_reload() -> str:
    """刷新当前浏览器页面并返回页面信息。"""
    return await _browser_history_action("reload")


@tool
async def browser_tabs() -> str:
    """列出当前浏览器会话的标签页，不返回令牌或 Playwright 对象。"""
    context = _context_or_error()
    session = await _owned_session(context)
    tabs = await browser_runtime.tabs(session.id)
    return json.dumps([tab.model_dump(mode="json") for tab in tabs], ensure_ascii=False)


@tool
async def browser_switch_tab(tab_id: str) -> str:
    """切换到当前浏览器会话中的指定标签页。"""
    context = _context_or_error()
    session = await _owned_session(context)
    result = await browser_runtime.switch_tab(session.id, tab_id)
    return await _browser_result_json(context, result)


@tool
async def browser_close_tab(tab_id: str) -> str:
    """关闭当前浏览器会话中的指定标签页，至少保留一个标签页。"""
    context = _context_or_error()
    session = await _owned_session(context)
    result = await browser_runtime.close_tab(session.id, tab_id)
    return await _browser_result_json(context, result)


def _browser_user_info(context: Any) -> dict[str, Any]:
    return {
        "user_id": getattr(context, "user_id", None),
        "id": getattr(context, "user_id", None),
        "user_name": getattr(context, "user_name", None),
        "username": getattr(context, "user_name", None),
    }


def _safe_browser_file_path(context: Any, file_path: str) -> Path:
    from app.services.ai.tools.generated_file_service import generated_files_root
    from app.utils.fs_access import get_user_private_workspace_root
    from app.utils.fs_paths import normalize_fs_path

    normalized = normalize_fs_path(file_path)
    candidate = Path(normalized).resolve() if normalized else None
    user_root = get_user_private_workspace_root(_browser_user_info(context))
    allowed_roots = [Path(user_root).resolve()] if user_root else []
    allowed_roots.append(generated_files_root().resolve())
    if candidate is None or not candidate.is_file() or not any(
        candidate == root or root in candidate.parents for root in allowed_roots
    ):
        raise ValueError("文件不存在或不属于当前用户允许的浏览器文件目录")
    return candidate


@tool
async def browser_upload(target_ref: str, snapshot_id: str, file_path: str) -> str:
    """把当前用户允许目录中的文件上传到快照目标，不返回服务器物理路径。"""
    context = _context_or_error()
    session = await _owned_session(context)
    source = _safe_browser_file_path(context, file_path)
    result = await browser_runtime.upload(
        session.id,
        target_ref=target_ref,
        snapshot_id=snapshot_id,
        file_path=str(source),
    )
    return await _browser_result_json(context, result)


@tool
async def browser_download(target_ref: str, snapshot_id: str) -> str:
    """点击快照中的下载目标，并返回带时效能力链接的下载结果。"""
    context = _context_or_error()
    session = await _owned_session(context)
    result = await browser_runtime.download(
        session.id,
        target_ref=target_ref,
        snapshot_id=snapshot_id,
    )
    await _persist_browser_result(context, result)
    download_path = str(result.data.get("download_path") or "")
    filename = str(result.data.get("filename") or "download")
    if not download_path:
        raise RuntimeError("浏览器下载结果缺少文件")
    from app.services.ai.tools.generated_file_service import publish

    artifact = publish(download_path, filename)
    payload = result.model_dump(mode="json")
    payload["data"] = artifact.to_tool_payload()
    return json.dumps(payload, ensure_ascii=False)


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
