from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_api_key
from app.core.orm import AsyncSessionLocal, get_db_session
from app.schemas.browser import (
    BrowserPolicyUpdateRequest,
    BrowserProfileResponse,
    BrowserSessionOpenRequest,
    BrowserSessionResponse,
)
from app.services.ai.browser.browser_policy import BrowserUrlBlocked
from app.services.ai.browser.browser_runtime import browser_runtime
from app.services.ai.browser.browser_profile_service import (
    BrowserProfileAccessDenied,
    BrowserProfileService,
)
from app.services.ai.browser.browser_session_service import (
    BrowserAccessDenied,
    BrowserSessionService,
)


router = APIRouter()
viewer_router = APIRouter()
logger = logging.getLogger(__name__)


def _user_id(user_info: dict[str, Any]) -> int:
    raw_user_id = user_info.get("user_id") or user_info.get("id")
    if raw_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少用户身份")
    try:
        return int(raw_user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效") from exc


def _viewer_cookie_name(session_id: str) -> str:
    return f"browser_viewer_{session_id}"


@router.get("/profiles", response_model=list[BrowserProfileResponse])
async def list_browser_profiles(
    user_info: dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    service = BrowserProfileService(db)
    return await service.list_owned(user_id=_user_id(user_info))


@router.post("/sessions/open", response_model=BrowserSessionResponse)
async def open_browser_session(
    payload: BrowserSessionOpenRequest,
    user_info: dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = BrowserSessionService(db)
        session = await service.open_or_resume(
            user_id=_user_id(user_info),
            conversation_id=payload.conversation_id,
            url=payload.url,
            profile_id=payload.profile_id,
        )
        await browser_runtime.open_session(db, session)
        return session
    except BrowserUrlBlocked as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except BrowserProfileAccessDenied as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to open browser session")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="浏览器启动失败，请稍后重试") from exc


@router.get("/sessions/active", response_model=list[BrowserSessionResponse])
async def list_active_browser_sessions(
    user_info: dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    service = BrowserSessionService(db)
    return await service.list_owned_active(user_id=_user_id(user_info))


@router.get("/sessions/{session_id}", response_model=BrowserSessionResponse)
async def get_browser_session(
    session_id: str,
    user_info: dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await BrowserSessionService(db).get_owned_session(
            user_id=_user_id(user_info), session_id=session_id
        )
    except BrowserAccessDenied as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/sessions/{session_id}/policy", response_model=BrowserSessionResponse)
async def update_browser_policy(
    session_id: str,
    payload: BrowserPolicyUpdateRequest,
    user_info: dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await BrowserSessionService(db).set_approval_mode(
            user_id=_user_id(user_info), session_id=session_id, mode=payload.approval_mode
        )
    except BrowserAccessDenied as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/detach", response_model=BrowserSessionResponse)
async def detach_browser_session(
    session_id: str,
    user_info: dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await BrowserSessionService(db).detach(
            user_id=_user_id(user_info), session_id=session_id
        )
    except BrowserAccessDenied as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/continue", response_model=BrowserSessionResponse)
async def continue_browser_session(
    session_id: str,
    user_info: dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        session = await BrowserSessionService(db).get_owned_session(
            user_id=_user_id(user_info), session_id=session_id
        )
        session.status = "active"
        await db.flush()
        return session
    except BrowserAccessDenied as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}")
async def close_browser_session(
    session_id: str,
    destroy_profile: bool = Query(False),
    user_info: dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    user_id = _user_id(user_info)
    try:
        session = await BrowserSessionService(db).get_owned_session(
            user_id=user_id, session_id=session_id
        )
        await BrowserSessionService(db).close(
            user_id=user_id,
            session_id=session_id,
            destroy_profile=destroy_profile,
        )
        await browser_runtime.close(session.id)
        return {"success": True, "session_id": session_id}
    except BrowserAccessDenied as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/viewer-token")
async def issue_browser_viewer_token(
    session_id: str,
    request: Request,
    response: Response,
    user_info: dict[str, Any] = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        token, expires_at = await BrowserSessionService(db).issue_viewer_token(
            user_id=_user_id(user_info), session_id=session_id
        )
        response.set_cookie(
            key=_viewer_cookie_name(session_id),
            value=token,
            max_age=30 * 60,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
            path=f"/api/v1/chat/browser/sessions/{session_id}",
        )
        return {"session_id": session_id, "token": token, "expires_at": expires_at}
    except BrowserAccessDenied as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/snapshot")
async def get_browser_snapshot(
    session_id: str,
    user_info: dict[str, Any] = Depends(require_api_key),
):
    user_id = _user_id(user_info)
    async with AsyncSessionLocal() as db:
        try:
            session = await BrowserSessionService(db).get_owned_session(
                user_id=user_id, session_id=session_id
            )
            if not browser_runtime.has_session(session.id):
                await browser_runtime.open_session(db, session)
            snapshot = await browser_runtime.snapshot(session.id)
            await db.commit()
            payload = snapshot.model_dump(mode="json")
            payload["screenshot_ref"] = None
            return payload
        except BrowserAccessDenied as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@viewer_router.get("/sessions/{session_id}/screenshot")
async def get_browser_screenshot(
    session_id: str,
    request: Request,
    token: str | None = Query(None, min_length=20),
    snapshot_id: str | None = Query(None, min_length=8, max_length=128),
):
    viewer_token = token or request.cookies.get(_viewer_cookie_name(session_id))
    if not viewer_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少浏览器查看令牌")
    async with AsyncSessionLocal() as db:
        try:
            session = await BrowserSessionService(db).resolve_viewer_token(viewer_token)
            if session.id != session_id:
                raise BrowserAccessDenied("浏览器查看令牌与会话不匹配")
            if snapshot_id:
                if not browser_runtime.has_session(session.id):
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="浏览器截图已过期，请刷新页面")
                try:
                    snapshot = browser_runtime.cached_snapshot(session.id, snapshot_id)
                except ValueError as exc:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="浏览器截图已过期，请刷新页面") from exc
            else:
                if not browser_runtime.has_session(session.id):
                    await browser_runtime.open_session(db, session)
                snapshot = await browser_runtime.snapshot(session.id)
                await db.commit()
        except BrowserAccessDenied as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    screenshot_ref = snapshot.screenshot_ref
    if not screenshot_ref or not Path(screenshot_ref).is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="浏览器截图不存在")
    return FileResponse(screenshot_ref, media_type="image/png", filename=f"{session_id}.png")


def _viewer_snapshot_payload(session_id: str, snapshot) -> dict[str, Any]:
    payload = snapshot.model_dump(mode="json")
    if snapshot.screenshot_ref:
        payload["screenshot_ref"] = f"/api/v1/chat/browser/sessions/{session_id}/screenshot"
    return payload


def _viewer_token_from_websocket(websocket: WebSocket) -> tuple[str | None, str | None]:
    protocols = [item.strip() for item in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    for protocol in protocols:
        if protocol.startswith("browser-viewer."):
            return protocol[len("browser-viewer."):], protocol
    return websocket.query_params.get("token"), None


async def _send_viewer_control_state(
    websocket: WebSocket,
    session_id: str,
    snapshot=None,
) -> None:
    state = browser_runtime.control_state(session_id)
    await websocket.send_json({"type": "control_state", **state})
    if snapshot is not None:
        detected = snapshot.page_state == "captcha"
        await websocket.send_json(
            {
                "type": "captcha",
                "detected": detected,
                "reason": "页面要求人工完成安全验证" if detected else None,
            }
        )


@viewer_router.websocket("/sessions/{session_id}/viewer")
async def browser_viewer(websocket: WebSocket, session_id: str):
    token, selected_protocol = _viewer_token_from_websocket(websocket)
    if not token:
        await websocket.close(code=4403)
        return
    async with AsyncSessionLocal() as db:
        try:
            session = await BrowserSessionService(db).resolve_viewer_token(token)
            if session.id != session_id:
                raise BrowserAccessDenied("浏览器查看令牌与会话不匹配")
            await websocket.accept(subprotocol=selected_protocol)
            if not browser_runtime.has_session(session.id):
                await browser_runtime.open_session(db, session)
            snapshot = await browser_runtime.snapshot(session.id)
            await db.commit()
            await websocket.send_json({"type": "snapshot", "snapshot": _viewer_snapshot_payload(session_id, snapshot)})
            await _send_viewer_control_state(websocket, session.id, snapshot)

            while True:
                message = await websocket.receive_json()
                event = str(message.get("type", ""))
                try:
                    if event == "snapshot":
                        snapshot = await browser_runtime.snapshot(session.id)
                    elif event in {"mouse_click", "mouse_down", "mouse_move", "mouse_up", "key", "text", "scroll"}:
                        info = await browser_runtime.manual_input(
                            session.id,
                            event=event,
                            payload=message,
                        )
                        session.current_url = info.url
                        session.page_title = info.title
                        session.last_seen_at = datetime.now()
                        await db.commit()
                        if event != "mouse_move":
                            await _send_viewer_control_state(websocket, session.id)
                        if event in {"mouse_down", "mouse_move"}:
                            continue
                        if event == "mouse_click":
                            await websocket.send_json({"type": "focus", "focused_input": info.focused_input})
                        snapshot = await browser_runtime.snapshot(session.id)
                    elif event == "release_control":
                        await browser_runtime.release_human_control(session.id)
                        snapshot = await browser_runtime.snapshot(session.id)
                    elif event == "navigate":
                        info = await browser_runtime.navigate(session.id, str(message.get("url", "")))
                        session.current_url = info.url
                        session.page_title = info.title
                        session.last_seen_at = datetime.now()
                        await db.commit()
                        snapshot = await browser_runtime.snapshot(session.id)
                    elif event == "semantic_click":
                        result = await browser_runtime.click(
                            session.id,
                            target_ref=str(message.get("target_ref", "")),
                            snapshot_id=str(message.get("snapshot_id", "")),
                            approval_mode=session.approval_mode,
                            confirmed=True,
                        )
                        session.current_url = result.url
                        session.page_title = result.title
                        await db.commit()
                        snapshot = await browser_runtime.snapshot(session.id)
                    elif event == "semantic_fill":
                        result = await browser_runtime.fill(
                            session.id,
                            target_ref=str(message.get("target_ref", "")),
                            snapshot_id=str(message.get("snapshot_id", "")),
                            value=str(message.get("value", "")),
                            sensitive=bool(message.get("sensitive", False)),
                        )
                        session.current_url = result.url
                        session.page_title = result.title
                        await db.commit()
                        snapshot = await browser_runtime.snapshot(session.id)
                    else:
                        await websocket.send_json({"type": "error", "message": "不支持的浏览器输入事件"})
                        continue
                    await _send_viewer_control_state(websocket, session.id, snapshot)
                    await websocket.send_json({"type": "snapshot", "snapshot": _viewer_snapshot_payload(session_id, snapshot)})
                except Exception as op_exc:
                    logger.exception("Browser viewer operation failed")
                    await websocket.send_json({"type": "error", "message": "浏览器操作失败，请刷新后重试"})
        except BrowserAccessDenied:
            await websocket.close(code=4403)
        except WebSocketDisconnect:
            await browser_runtime.release_human_control(session_id)
            return
        except Exception as exc:
            logger.exception("Browser viewer operation failed")
            await websocket.send_json({"type": "error", "message": "浏览器操作失败，请刷新后重试"})
