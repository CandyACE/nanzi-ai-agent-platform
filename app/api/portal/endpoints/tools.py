from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import json

from app.core.dependencies import require_admin, require_permission, require_api_key
from app.core.orm import get_db_session
from app.models.tool import SysApiTool
from app.models.mcp import McpServer, McpToolCache
from app.schemas.tool import (
    SysApiToolBatchGroupRequest,
    SysApiToolCreate,
    SysApiToolResponse,
    SysApiToolUpdate,
)
from app.services.ai.tools.forbidden_catalog import (
    BUILTIN_FORBIDDEN_TOOL_CANDIDATES,
    api_tool_group,
    mcp_tool_group,
    ForbiddenToolCandidate,
    merge_forbidden_tool_candidates,
)

router = APIRouter()

# 注册表写操作所需的权限依赖抽成具名对象：避免同一字符串散落多处，也便于测试覆盖。
SYSTEM_CONFIG_SAVE_PERMISSION = require_permission("element", "element:system:config_save")

def _visible_published_mcp_tool_stmt(user: Dict[str, Any]):
    """已发布且可用的 MCP 工具：平台公共服务 + 当前登录用户的个人私有服务。"""
    from sqlalchemy.orm import joinedload

    current_user_id = user.get("user_id") if user.get("user_id") is not None else user.get("id")
    try:
        current_user_id = int(current_user_id) if current_user_id is not None else None
    except Exception:
        pass

    global_cond = or_(McpServer.scope == "global", McpServer.scope.is_(None))
    personal_cond = and_(McpServer.scope == "personal", McpServer.user_id == current_user_id)

    return (
        select(McpToolCache)
        .join(McpToolCache.server)
        .options(joinedload(McpToolCache.server))
        .where(
            McpToolCache.is_published == True,  # noqa: E712 - 与既有查询写法一致
            McpToolCache.is_available == True,  # noqa: E712
            McpServer.enabled_status == 1,
            or_(global_cond, personal_cond),
        )
    )


async def _list_visible_published_mcp_tools(db: AsyncSession, user: Dict[str, Any]):
    result = await db.execute(_visible_published_mcp_tool_stmt(user))
    return result.scalars().all()


@router.get("/mcp", response_model=List[Dict[str, Any]])
async def list_published_mcp_tools(
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(require_api_key),
):
    """列出已发布的 MCP 工具：包含平台公共 MCP 工具，以及当前登录用户自己创建的个人私有 MCP 工具。"""
    tools = await _list_visible_published_mcp_tools(db, user)

    return [
        {
            "id": t.id,
            "name": t.tool_name,
            "description": t.tool_description,
            "server_name": t.server.server_name if t.server else "Unknown",
            "server_remark": (t.server.remark if t.server else None) or None,
            "scope": t.server.scope if (t.server and t.server.scope) else "global",
            "parameter_schema": json.loads(t.parameter_schema or "{}")
        } for t in tools
    ]


def _list_forbidden_skill_candidates() -> list[dict[str, Any]]:
    """可禁用的技能候选：只列**已启用的平台（全局）技能**。

    个人技能属于用户自己的资源，不在管理员配置范围内；而列出本来就已经禁用的技能也没有
    意义（禁用是为了拦住"目前能用"的技能）。
    """
    from app.services.ai.skill_resolver import list_global_skill_metas

    candidates: list[dict[str, Any]] = []
    for meta in list_global_skill_metas():
        skill_id = str(meta.get("id") or "").strip()
        if not skill_id or meta.get("enabled", "true") == "false":
            continue
        candidates.append(
            {
                "id": skill_id,
                "label": str(meta.get("name") or skill_id),
                "description": str(meta.get("description") or ""),
                # 技能暂不细分来源，统一一个分组；仍带 group_key/group 以便前端复用同一套分组渲染
                "group_key": "skill:__all__",
                "group": "公共技能",
            }
        )
    return candidates


@router.get("/forbidden-catalog", response_model=Dict[str, Any])
async def list_forbidden_tool_catalog(
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(require_permission("element", "element:user:edit")),
):
    """返回可禁用的工具候选：内置高危工具（含运行时别名）+ 自定义 API 与已发布 MCP 工具 + 公共技能。

    只读、幂等；不返回任何用户已配置的禁用项（已选项由权限接口回显）。
    权限与"保存禁用项"的接口保持一致：能配禁用才需要看候选，避免任意登录用户枚举全部工具/MCP/技能清单。
    """
    api_tools = (
        await db.execute(select(SysApiTool).order_by(SysApiTool.created_at.desc()))
    ).scalars().all()
    mcp_tools = await _list_visible_published_mcp_tools(db, user)

    # 分组字段（v2）：API 按业务分组、MCP 按服务名，缺失时各自兜底。
    dynamic_candidates: list[ForbiddenToolCandidate] = []
    for tool in api_tools:
        name = str(tool.name or "").strip()
        if not name:
            continue
        group_key, group = api_tool_group(getattr(tool, "group_name", None))
        dynamic_candidates.append(
            ForbiddenToolCandidate(
                id=name,
                label=name,
                description=str(tool.description or "自定义 API 工具"),
                category="api",
                aliases=(name,),
                group_key=group_key,
                group=group,
            )
        )
    for tool in mcp_tools:
        name = str(tool.tool_name or "").strip()
        if not name:
            continue
        server = getattr(tool, "server", None)
        group_key, group = mcp_tool_group(getattr(server, "server_name", None))
        dynamic_candidates.append(
            ForbiddenToolCandidate(
                id=name,
                label=name,
                description=str(tool.tool_description or "MCP 注册工具"),
                category="mcp",
                aliases=(name,),
                group_key=group_key,
                group=group,
            )
        )

    merged = merge_forbidden_tool_candidates(
        BUILTIN_FORBIDDEN_TOOL_CANDIDATES,
        dynamic_candidates,
    )
    return {
        "candidates": [
            {
                "id": candidate.id,
                "label": candidate.label,
                "description": candidate.description,
                "category": candidate.category,
                "aliases": list(candidate.aliases),
                "group_key": candidate.group_key,
                "group": candidate.group,
            }
            for candidate in merged
        ],
        "skill_candidates": _list_forbidden_skill_candidates(),
    }


@router.get("", response_model=List[SysApiToolResponse])
async def list_tools(
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(require_api_key),
):
    """列出系统 HTTP/API 工具（任意持有有效 API Key 的登录用户可读，供智能体配置勾选）。"""
    query = select(SysApiTool).order_by(SysApiTool.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.post("", response_model=SysApiToolResponse)
async def create_tool(
    tool_in: SysApiToolCreate,
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(require_permission("element", "element:system:config_save"))
):
    """Create a new API tool"""
    # ... (rest of function)
    # Check if name exists
    existing = await db.execute(select(SysApiTool).where(SysApiTool.name == tool_in.name))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Tool name already exists")
    
    # Dump Dicts to JSON strings for DB
    data = tool_in.model_dump()
    if data.get("headers") is not None:
        data["headers"] = json.dumps(data["headers"], ensure_ascii=False)
    if data.get("parameter_schema") is not None:
        data["parameter_schema"] = json.dumps(data["parameter_schema"], ensure_ascii=False)
        
    new_tool = SysApiTool(
        id=str(uuid.uuid4()),
        **data
    )
    db.add(new_tool)
    await db.commit()
    await db.refresh(new_tool)
    return new_tool

@router.put("/{tool_id}", response_model=SysApiToolResponse)
async def update_tool(
    tool_id: str,
    tool_in: SysApiToolUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(require_permission("element", "element:system:config_save"))
):
    """Update an API tool"""
    # ... (rest of function)
    result = await db.execute(select(SysApiTool).where(SysApiTool.id == tool_id))
    tool = result.scalars().first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    update_data = tool_in.model_dump(exclude_unset=True)
    
    # Dump Dicts to JSON strings for DB
    if "headers" in update_data:
         val = update_data["headers"]
         update_data["headers"] = json.dumps(val, ensure_ascii=False) if val is not None else None
         
    if "parameter_schema" in update_data:
        val = update_data["parameter_schema"]
        update_data["parameter_schema"] = json.dumps(val, ensure_ascii=False) if val is not None else None

    for field, value in update_data.items():
        setattr(tool, field, value)
        
    await db.commit()
    await db.refresh(tool)
    return tool

@router.post("/batch-group")
async def batch_set_tool_group(
    payload: SysApiToolBatchGroupRequest,
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(SYSTEM_CONFIG_SAVE_PERMISSION),
):
    """批量设置业务分组（注册表页多选后一次改完）。

    只改 ``group_name``：``group_name`` 留空表示清除分组，回到「未分组」状态。
    刻意不做「按名称前缀自动归类」——分组口径由使用者决定，代码里不写死任何前缀。
    """
    result = await db.execute(select(SysApiTool).where(SysApiTool.id.in_(payload.ids)))
    tools = result.scalars().all()
    for tool in tools:
        tool.group_name = payload.group_name
    await db.commit()
    return {"updated": len(tools), "group_name": payload.group_name}


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(require_permission("element", "element:system:config_save"))
):
    """Delete an API tool"""
    result = await db.execute(select(SysApiTool).where(SysApiTool.id == tool_id))
    tool = result.scalars().first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    await db.delete(tool)
    await db.commit()
    return {"status": "success", "message": "Tool deleted"}
