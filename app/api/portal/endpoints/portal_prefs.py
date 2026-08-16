"""
数据门户个人偏好接口（Portal Preferences）

存储用户置顶的数据门户卡片 ID 列表到 Redis。
Key: agent:portal_prefs:{user_id}
Value: JSON 字符串，结构为 { "pinned_group_ids": ["id1", "id2"] }
"""
import json
import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.dependencies import require_api_key
from app.core.orm import get_db_session
from app.core.redis import get_redis
from app.services.ai.agent_manager import AgentManagerService

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_PINNED_GROUPS = 50  # 最多允许置顶的卡片数，防止滥用
MAX_CARD_ORDER = 200   # 最多记录排序的卡片数
MAX_QUESTION_CLICKS = 500  # 最多记录的问题点击 key 数


def _redis_key(user_id: int) -> str:
    return f"agent:portal_prefs:{user_id}"


class PortalPrefs(BaseModel):
    pinned_group_ids: List[str] = Field(default_factory=list, description="已置顶的数据门户卡片 ID 列表，保持插入顺序")
    card_order: List[str] = Field(default_factory=list, description="拖拽自定义排序的卡片 ID 全量列表")
    expanded_group_ids: List[str] = Field(default_factory=list, description="已展开相关数据面板的卡片 ID 列表")
    question_clicks: Dict[str, int] = Field(default_factory=dict, description="本地问题点击次数备份（query → count），用于跨 session 保留常问数据")
    pinned_kb_dataset_ids: List[str] = Field(default_factory=list, description="已置顶的知识库数据集 ID 列表")
    markdown_theme: str = Field(default="", description="用户自定义的 AI 消息排版样式偏好")
    routing_mode: Literal["auto", "expert"] = Field(default="auto", description="Embed 路由模式")
    expert_agent_id: str = Field(default="", description="Embed 默认智能体 ID")
    routing_configured: bool = Field(default=False, description="用户是否明确设置过 Embed 路由模式")


class PortalPrefsUpdate(BaseModel):
    pinned_group_ids: List[str] = Field(default_factory=list)
    card_order: List[str] = Field(default_factory=list)
    expanded_group_ids: List[str] = Field(default_factory=list)
    question_clicks: Dict[str, int] = Field(default_factory=dict)
    pinned_kb_dataset_ids: List[str] = Field(default_factory=list)
    markdown_theme: Optional[str] = None


class RoutingPreferenceUpdate(BaseModel):
    routing_mode: Literal["auto", "expert"] = "auto"
    expert_agent_id: str = ""


def _parse_portal_prefs(raw: Any) -> PortalPrefs:
    decoded = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    parsed = json.loads(decoded)
    if not isinstance(parsed, dict):
        raise ValueError("portal prefs must be an object")
    # 兼容新增标记前已经保存过的路由配置：存在路由字段即视为用户配置过。
    if "routing_configured" not in parsed:
        parsed["routing_configured"] = (
            "routing_mode" in parsed or "expert_agent_id" in parsed
        )
    return PortalPrefs.model_validate(parsed)


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="获取当前用户的数据门户偏好设置",
)
async def get_portal_prefs(
    user_info: Dict[str, Any] = Depends(require_api_key),
):
    redis = await get_redis()
    if not redis:
        return {"code": 0, "data": PortalPrefs().model_dump()}

    user_id = int(user_info["user_id"])
    key = _redis_key(user_id)
    try:
        raw = await redis.get(key)
    except Exception as e:
        logger.error("Failed to get portal prefs from Redis: %s", e)
        return {"code": 0, "data": PortalPrefs().model_dump()}

    if not raw:
        return {"code": 0, "data": PortalPrefs().model_dump()}

    try:
        decoded = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        prefs = _parse_portal_prefs(decoded)
    except Exception as e:
        logger.warning("Failed to parse portal prefs JSON: %s", e)
        prefs = PortalPrefs()

    return {"code": 0, "data": prefs.model_dump()}


@router.put(
    "",
    response_model=Dict[str, Any],
    summary="保存当前用户的数据门户偏好设置",
)
async def update_portal_prefs(
    body: PortalPrefsUpdate,
    user_info: Dict[str, Any] = Depends(require_api_key),
):
    redis = await get_redis()
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis 服务不可用",
        )

    user_id = int(user_info["user_id"])
    key = _redis_key(user_id)

    existing = PortalPrefs()
    try:
        raw = await redis.get(key)
        if raw:
            existing = _parse_portal_prefs(raw)
    except Exception as e:
        logger.warning("Failed to read existing portal prefs before update: %s", e)

    # --- 清理 pinned_group_ids ---
    seen: set = set()
    deduped_pins: List[str] = []
    for gid in body.pinned_group_ids:
        gid = gid.strip()
        if gid and gid not in seen:
            seen.add(gid)
            deduped_pins.append(gid)
            if len(deduped_pins) >= MAX_PINNED_GROUPS:
                break

    # --- 清理 card_order ---
    seen2: set = set()
    deduped_order: List[str] = []
    for gid in body.card_order:
        gid = gid.strip()
        if gid and gid not in seen2:
            seen2.add(gid)
            deduped_order.append(gid)
            if len(deduped_order) >= MAX_CARD_ORDER:
                break

    # --- 清理 expanded_group_ids ---
    deduped_expanded = list(dict.fromkeys(
        gid.strip() for gid in body.expanded_group_ids if gid.strip()
    ))

    # --- 清理 pinned_kb_dataset_ids ---
    deduped_kb_pins = list(dict.fromkeys(
        kid.strip() for kid in body.pinned_kb_dataset_ids if kid.strip()
    ))

    # --- 清理 question_clicks：只保留正整数，限制 key 数量 ---
    clean_clicks: Dict[str, int] = {}
    for q, cnt in body.question_clicks.items():
        q = q.strip()
        if q and isinstance(cnt, int) and cnt > 0:
            clean_clicks[q] = cnt
            if len(clean_clicks) >= MAX_QUESTION_CLICKS:
                break

    prefs = PortalPrefs(
        pinned_group_ids=deduped_pins,
        card_order=deduped_order,
        expanded_group_ids=deduped_expanded,
        question_clicks=clean_clicks,
        pinned_kb_dataset_ids=deduped_kb_pins,
        markdown_theme=(
            body.markdown_theme.strip()
            if body.markdown_theme is not None
            else existing.markdown_theme
        ),
        # 路由偏好只允许通过 /routing 更新，并在该接口完成智能体权限校验。
        routing_mode=existing.routing_mode,
        expert_agent_id=existing.expert_agent_id if existing.routing_mode == "expert" else "",
        routing_configured=existing.routing_configured,
    )

    try:
        # 不设置 TTL，长期保留用户偏好
        await redis.set(key, prefs.model_dump_json())
    except Exception as e:
        logger.error("Failed to save portal prefs to Redis: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存偏好设置失败",
        )

    return {"code": 0, "data": prefs.model_dump(), "message": "偏好已保存"}


@router.put(
    "/routing",
    response_model=Dict[str, Any],
    summary="更新当前用户的 Embed 智能体路由偏好",
)
async def update_routing_prefs(
    body: RoutingPreferenceUpdate,
    session: AsyncSession = Depends(get_db_session),
    user_info: Dict[str, Any] = Depends(require_api_key),
):
    routing_mode = body.routing_mode
    expert_agent_id = body.expert_agent_id.strip()

    if routing_mode == "expert" and not expert_agent_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="默认智能体模式必须选择智能体",
        )

    if routing_mode == "expert":
        try:
            agent = await AgentManagerService.resolve_embed_agent_access(
                session,
                expert_agent_id,
                user_info,
            )
            active_config = await AgentManagerService.get_active_agent_config(
                session,
                agent_id=str(agent.id),
            )
            if not active_config:
                raise LookupError("agent_not_ready")
        except LookupError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="智能体不存在、已停用或尚未发布",
            ) from None
        except PermissionError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权使用该智能体",
            ) from None

    redis = await get_redis()
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis 服务不可用",
        )

    user_id = int(user_info["user_id"])
    key = _redis_key(user_id)
    prefs = PortalPrefs()
    try:
        raw = await redis.get(key)
        if raw:
            prefs = _parse_portal_prefs(raw)
    except Exception as e:
        logger.warning("Failed to read existing portal prefs before routing update: %s", e)

    prefs.routing_mode = routing_mode
    prefs.expert_agent_id = expert_agent_id if routing_mode == "expert" else ""
    prefs.routing_configured = True

    try:
        await redis.set(key, prefs.model_dump_json())
    except Exception as e:
        logger.error("Failed to save routing prefs to Redis: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存路由偏好失败",
        ) from e

    return {
        "code": 0,
        "data": {
            "routing_mode": prefs.routing_mode,
            "expert_agent_id": prefs.expert_agent_id,
        },
        "message": "路由偏好已保存",
    }


class MarkdownThemeUpdate(BaseModel):
    theme: str


@router.put(
    "/markdown-theme",
    response_model=Dict[str, Any],
    summary="更新当前用户的 AI 消息排版样式偏好",
)
async def update_markdown_theme(
    body: MarkdownThemeUpdate,
    user_info: Dict[str, Any] = Depends(require_api_key),
):
    redis = await get_redis()
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis 服务不可用",
        )

    user_id = int(user_info["user_id"])
    key = _redis_key(user_id)

    # 1. 读取原有的配置
    prefs = PortalPrefs()
    try:
        raw = await redis.get(key)
        if raw:
            prefs = _parse_portal_prefs(raw)
    except Exception as e:
        logger.warning("Failed to read exist portal prefs: %s", e)

    # 2. 修改排版样式
    prefs.markdown_theme = body.theme.strip()

    # 3. 重新写入 Redis
    try:
        await redis.set(key, prefs.model_dump_json())
    except Exception as e:
        logger.error("Failed to save portal prefs to Redis: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存排版样式偏好失败",
        )

    return {"code": 0, "data": {"markdown_theme": prefs.markdown_theme}, "message": "样式偏好已保存"}
