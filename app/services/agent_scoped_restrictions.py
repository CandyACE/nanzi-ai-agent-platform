"""智能体级可限制资源的候选构建。

「功能限制」弹框要回答的问题是：**这个智能体本身绑定了什么**，管理员才能在其上做排除。
因此候选不是"平台全部资源"，而是该智能体当前版本的绑定集合：

- 内置工具 / 自定义 API 工具：``AIAgentVersion.tools`` 里的非 MCP 项；
- MCP：``AIAgentVersion.tools`` 里的 ``mcp-<server_id>:<tool_name>``，按 server 分组展示；
- 公共技能：``AIAgentVersion.skills``（本版本的公共技能白名单）；
- 个人技能：当前用户的私人技能目录。

落库的 ``resource_id`` 一律用**与全局禁用同一套标识**：
- 工具用纯工具名（MCP 也用 ``tool_name``，与 ``forbidden-catalog`` 的候选 id 一致），
  这样运行时 ``to_runtime_tool_names`` 那套别名/运行时名匹配可以直接复用，不必为
  "智能体级"再造一套匹配语义；
- 技能用技能 id。

``forbidden_globally`` 用于让弹框把全局已禁项置灰只读——排除机制只增不减，不允许在
智能体层面"放开"全局禁用，否则两层语义会互相打架。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AIAgent, AIAgentVersion
from app.models.mcp import McpToolCache
from app.models.tool import SysApiTool
from app.utils.skill_metadata import is_skill_enabled

logger = logging.getLogger(__name__)

MCP_TOOL_PREFIX = "mcp-"


def _as_list(raw: Any) -> List[str]:
    """``tools`` / ``skills`` 是 JSON 列，历史数据可能是字符串、None 或已解析的列表。"""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except Exception:
            return []
    if isinstance(raw, (list, tuple)):
        entries: List[str] = []
        for item in raw:
            # 工具项不一定是字符串：元数据集绑定、钉钉/邮件/飞书配置等会写成
            # {"name": "get_dataset_schema", "metadata_dataset_ids": [...]}。
            # 直接 str(item) 会得到一段 Python repr（约 200 字符），既让**真工具名彻底
            # 不可限定**，又在候选里多出一条永远匹配不到的垃圾 id（前端还会把它当历史项
            # 长期保留）。这里按 name/tool_name/id 取真名。
            if isinstance(item, dict):
                raw_name = item.get("name") or item.get("tool_name") or item.get("id")
                text = str(raw_name).strip() if raw_name else ""
            else:
                text = str(item).strip()
            if text:
                entries.append(text)
        return entries
    return []


def split_agent_tool_bindings(tools: Any) -> tuple[List[str], List[tuple[str, str]]]:
    """把 ``AIAgentVersion.tools`` 拆成（普通工具名, [(server_id, tool_name)]）。

    MCP 项的真实形态是 ``mcp-<server_id>:<tool_name>``（见线上数据）。这里解析出
    ``tool_name`` 作为落库标识、``server_id`` 用于分组展示。
    """
    plain: List[str] = []
    mcp_pairs: List[tuple[str, str]] = []
    for entry in _as_list(tools):
        # 判据是「带冒号」而不是「以 mcp- 开头」——平台的 MCP 标识本质就是 server:tool
        # （运行时 is_platform_namespaced_tool_name 同样只看冒号），`mcp-` 只是可选的历史
        # 写法。此前只认 mcp- 前缀，导致服务名不含该前缀的自建/导入 MCP（例如
        # 「NanZi Echo 测试 MCP」）被归进「内置工具」：错页签、丢中文描述与分组，
        # 管理员在 MCP 页签里找不到它，等于列不出来也就禁不掉。
        if ":" in entry:
            head, _, tool_name = entry.partition(":")
            server_id = head[len(MCP_TOOL_PREFIX):] if head.startswith(MCP_TOOL_PREFIX) else head
            server_id, tool_name = server_id.strip(), tool_name.strip()
            if server_id and tool_name:
                mcp_pairs.append((server_id, tool_name))
                continue
        plain.append(entry)
    return plain, mcp_pairs


async def _latest_version(db: AsyncSession, agent_id: str) -> Optional[AIAgentVersion]:
    """取该智能体**最新**版本（优先已发布）。

    限制挂在 agent 维度而不是版本维度（产品口径），但候选清单必须来自某个具体版本。
    取最新已发布版本；若从未发布则退回最新版本，避免"草稿智能体无法配置限制"。
    """
    base = select(AIAgentVersion).where(AIAgentVersion.agent_id == agent_id)
    published = (
        await db.execute(
            base.where(AIAgentVersion.status == "PUBLISHED").order_by(
                AIAgentVersion.version_number.desc()
            ).limit(1)
        )
    ).scalar_one_or_none()
    if published is not None:
        return published
    return (
        await db.execute(
            base.order_by(AIAgentVersion.version_number.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def build_restrictable_resources(
    db: AsyncSession,
    *,
    agent_id: str,
    globally_forbidden_tools: Optional[set[str]] = None,
    globally_forbidden_skills: Optional[set[str]] = None,
    personal_skills: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """构建某智能体的可限制资源分组。

    ``globally_forbidden_*`` 与 ``personal_skills`` 由调用方传入（调用方已有用户上下文），
    这样本函数只依赖 ``db`` 与 agent_id，便于单测。
    """
    globally_forbidden_tools = globally_forbidden_tools or set()
    globally_forbidden_skills = globally_forbidden_skills or set()

    agent = await db.get(AIAgent, agent_id)
    if agent is None:
        raise ValueError(f"agent not found: {agent_id}")

    version = await _latest_version(db, agent_id)
    plain_tools, mcp_pairs = split_agent_tool_bindings(
        version.tools if version is not None else None
    )
    # 技能候选的范围由 ``skills_custom`` 决定（不是由 skills 是否为空决定）：
    # ``agent_manager`` 里注明 skills_custom=False 时运行时**使用全部公共技能**，
    # 此时若只列 version.skills（通常是空），管理员就没有任何技能可以限制，
    # 而那些技能在实际运行中全都生效。
    custom_skills = bool(getattr(version, "skills_custom", False)) if version is not None else False
    bound_skill_ids = _as_list(version.skills if version is not None else None)

    public_skill_metas: List[Dict[str, Any]] = []
    try:
        from app.services.ai.skill_resolver import list_global_skill_metas

        public_skill_metas = list(list_global_skill_metas() or [])
    except Exception:  # noqa: BLE001 —— 取不到就退回"只列已绑定的"，不能让整个弹框失败
        logger.debug("[agent-scope] failed to list global skills", exc_info=True)
    public_skill_labels = {
        str(meta.get("id")): str(meta.get("name") or meta.get("id"))
        for meta in public_skill_metas
        if str(meta.get("id") or "").strip()
    }
    public_skill_descriptions = {
        str(meta.get("id")): str(meta.get("description") or "").strip()
        for meta in public_skill_metas
        if str(meta.get("id") or "").strip() and str(meta.get("description") or "").strip()
    }

    if custom_skills:
        # 白名单：只列它真正会加载的那些
        candidate_skill_ids = [sid for sid in bound_skill_ids if sid]
    else:
        # 全量公共技能：启用中的都算（enabled=false 的技能不加载，列出来只会误导）
        candidate_skill_ids = [
            str(meta.get("id"))
            for meta in public_skill_metas
            if str(meta.get("id") or "").strip()
            and is_skill_enabled(meta)
        ]
        if not candidate_skill_ids:
            # 目录不可用时的兜底：至少把已绑定的列出来
            candidate_skill_ids = list(bound_skill_ids)

    # 自定义 API 工具：名字 → 注册表里填的业务分组 + 描述。
    # 分组要带出去，前端才能按「业务分组优先、否则按关键字猜能力域」展示（与智能体编辑页
    # 同一套规则）；描述要带出去，弹框才不至于只显示一个裸 id 而看不出这是什么工具。
    api_tool_rows = (
        await db.execute(select(SysApiTool.name, SysApiTool.group_name, SysApiTool.description))
    ).all()
    api_group_names: Dict[str, str] = {}
    api_tool_descriptions: Dict[str, str] = {}
    for name, group_name, description in api_tool_rows:
        clean_name = str(name or "").strip()
        if not clean_name:
            continue
        api_group_names[clean_name] = str(group_name or "").strip()
        clean_description = str(description or "").strip()
        if clean_description:
            api_tool_descriptions[clean_name] = clean_description
    api_names = set(api_group_names)

    # 内置工具的中文描述：与全局禁用资源的候选同源，复用同一份口径而不另抄一份。
    builtin_tool_descriptions: Dict[str, str] = {}
    try:
        from app.services.ai.tools.forbidden_catalog import (
            BUILTIN_FORBIDDEN_TOOL_CANDIDATES,
            builtin_tool_description,
        )

        for candidate in BUILTIN_FORBIDDEN_TOOL_CANDIDATES:
            description = str(getattr(candidate, "description", "") or "").strip()
            if description:
                builtin_tool_descriptions[str(candidate.id)] = description

        # 候选目录只收"执行与沙箱数据访问"类工具，绑定集合里还有文件/检索/子代理/文档等
        # 普通内置工具。不补描述的话它们在弹框里只显示裸英文 id（此前 25 个里只有 9 个
        # 有描述），管理员无法判断该不该限定。
        for name in builtin:
            if name in builtin_tool_descriptions:
                continue
            fallback = builtin_tool_description(name)
            if fallback:
                builtin_tool_descriptions[name] = fallback
    except Exception:  # noqa: BLE001 —— 仅影响副标题，取不到就退回显示 id
        logger.debug("[agent-scope] failed to build builtin descriptions", exc_info=True)

    # MCP 工具描述：缓存表的 tool_name 是「server_name:工具段」的**完整名**
    # （如 `mcp-private-admin-55555:get-current-date`），而版本绑定里只存工具段
    # （`get-current-date`）。所以按完整名建索引，取用时再把前缀拼回去——
    # 按 (server_id, tool_name) 建索引永远匹配不上，描述明明存在也会显示成裸 id。
    mcp_tool_descriptions: Dict[str, str] = {}
    try:
        for tname, tdesc in (
            await db.execute(
                select(McpToolCache.tool_name, McpToolCache.tool_description)
            )
        ).all():
            clean_name = str(tname or "").strip()
            clean_description = str(tdesc or "").strip()
            if clean_name and clean_description:
                mcp_tool_descriptions[clean_name] = clean_description
    except Exception:  # noqa: BLE001
        logger.debug("[agent-scope] failed to read mcp descriptions", exc_info=True)

    def tool_item(tool_id: str, description: str = "", label: str = "") -> Dict[str, Any]:
        """构造可限定项。``tool_id`` 是**落库标识**，``label`` 只是展示名。

        MCP 工具两者必须分开：落库要用 ``server_name:tool_name`` 全名（运行时注册名
        ``build_model_tool_name(全名)`` 由全名哈希而来，存工具段名永远匹配不上），
        而界面上显示 ``server_name:tool_name`` 又太啰嗦，所以展示仍用工具段名。
        """
        item: Dict[str, Any] = {
            "id": tool_id,
            "label": label or tool_id,
            "forbidden_globally": tool_id in globally_forbidden_tools,
        }
        group_name = api_group_names.get(tool_id)
        if group_name:
            item["group_name"] = group_name
        clean_description = str(description or "").strip()
        if clean_description:
            item["description"] = clean_description
        return item

    groups: List[Dict[str, Any]] = []

    builtin = [t for t in plain_tools if t not in api_names]
    api_tools = [t for t in plain_tools if t in api_names]
    if builtin:
        groups.append(
            {
                "key": "builtin_tools",
                "label": "内置工具",
                "items": [
                    tool_item(name, builtin_tool_descriptions.get(name, "")) for name in builtin
                ],
            }
        )
    if api_tools:
        groups.append(
            {
                "key": "api_tools",
                "label": "自定义 API 工具",
                "items": [
                    tool_item(name, api_tool_descriptions.get(name, "")) for name in api_tools
                ],
            }
        )

    if mcp_pairs:
        # 绑定里的 MCP 前缀不等于 `McpServer.id`：线上数据是 server_name，且常常是
        # 去掉开头 `mcp-` 的 server_name（如绑定 `private-admin-55555` 对应
        # server_name=`mcp-private-admin-55555`）。两种写法都建索引，才能既解析出
        # 分组名称、又拼出缓存表里的完整工具名。取不到就退回前缀本身（不能因此不展示，
        # 否则用户配不了）。
        mcp_prefixes = list(dict.fromkeys(prefix for prefix, _ in mcp_pairs))
        server_by_prefix: Dict[str, Dict[str, str]] = {}
        try:
            from app.models.mcp import McpServer

            server_rows = (
                await db.execute(select(McpServer.id, McpServer.server_name))
            ).all()
            for sid, sname in server_rows:
                clean_id = str(sid).strip()
                clean_name = str(sname or "").strip()
                record = {"id": clean_id, "name": clean_name}
                if clean_name:
                    server_by_prefix.setdefault(clean_name, record)
                    server_by_prefix.setdefault(
                        clean_name.removeprefix(MCP_TOOL_PREFIX), record
                    )
                if clean_id:
                    server_by_prefix.setdefault(clean_id, record)
        except Exception:  # noqa: BLE001 —— 仅影响分组标题，取不到就用前缀
            logger.debug("[agent-scope] failed to resolve MCP servers", exc_info=True)

        for prefix in mcp_prefixes:
            resolved = server_by_prefix.get(prefix) or {}
            server_name = str(resolved.get("name") or "")
            items = []
            for bound_prefix, tool_name in mcp_pairs:
                if bound_prefix != prefix:
                    continue
                # 缓存表用「server_name:工具段」作完整名；缓存未同步时仍然展示
                # （用户可见集合以绑定为准），只是没有描述可显示。
                # 全名不能依赖 McpServer 查询结果：绑定形如 mcp-<server_name>:<tool_name>，
                # 剥掉 mcp- 得到的 prefix 就是 server_name，所以 prefix 永远可用。
                # 用 prefix 兜底才能保证 id 恒为全名——否则查不到服务名时会退化成工具段名，
                # 运行时 build_model_tool_name(工具段) 与注册名（由全名哈希）对不上，勾了也禁不掉。
                scope_server_name = server_name or prefix
                full_name = f"{scope_server_name}:{tool_name}"
                description = mcp_tool_descriptions.get(full_name) or mcp_tool_descriptions.get(
                    tool_name, ""
                )
                if not description:
                    logger.debug(
                        "[agent-scope] no cached description for bound MCP tool %s/%s",
                        prefix,
                        tool_name,
                    )
                items.append(tool_item(full_name, description, label=tool_name))
            if items:
                groups.append(
                    {
                        "key": f"mcp:{prefix}",
                        "label": server_name or prefix,
                        "items": items,
                    }
                )

    if candidate_skill_ids:
        public_items: List[Dict[str, Any]] = []
        for skill_id in candidate_skill_ids:
            item: Dict[str, Any] = {
                "id": skill_id,
                "label": public_skill_labels.get(skill_id) or skill_id,
                "forbidden_globally": skill_id in globally_forbidden_skills,
            }
            description = public_skill_descriptions.get(skill_id, "")
            if description:
                item["description"] = description
            public_items.append(item)
        groups.append({"key": "public_skills", "label": "公共技能", "items": public_items})

    personal_items = []
    for meta in personal_skills or []:
        skill_id = str(meta.get("id") or "").strip()
        if not skill_id:
            continue
        item: Dict[str, Any] = {
            "id": skill_id,
            "label": str(meta.get("name") or skill_id),
            "forbidden_globally": skill_id in globally_forbidden_skills,
            # 个人技能**永远**不受限：权限侧三处过滤（清单 excluded_skill_ids、显式挂载
            # drop_forbidden_skill_items、上下文清洗）全部把个人技能排除在外，理由是个人技能
            # 与公共技能可能同名，只按 id 判定会连坐用户自建的那一份。
            # 所以这里必须标记为不可限定——否则管理员勾了能保存、库里也真写了，
            # 运行时却任何一处都不读，是个查不出原因的空转。
            "not_restrictable": True,
            "not_restrictable_reason": "个人技能不支持限定：权限侧只对公共技能生效",
        }
        description = str(meta.get("description") or "").strip()
        if description:
            item["description"] = description
        personal_items.append(item)
    if personal_items:
        groups.append({"key": "personal_skills", "label": "个人技能", "items": personal_items})

    # 候选清单来自**某一个具体版本**，而弹框是按 agent 维度配置限制的。把来源版本一并返回，
    # 前端才能解释"为什么这里的数量与智能体编辑页不同"——编辑页看的是正在编辑的草稿版本。
    source_version: Dict[str, Any] = {}
    if version is not None:
        source_version = {
            "id": version.id,
            "version_number": version.version_number,
            "status": str(version.status or ""),
            # 运行时实际生效的是已发布版本，取不到已发布才退回最新版本
            "is_published": str(version.status or "").upper() == "PUBLISHED",
        }

    return {"agent_id": agent_id, "groups": groups, "source_version": source_version}


def list_personal_skill_metas(user_info: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """当前用户的个人技能清单（扫描失败返回空列表，不影响弹框其它分区）。"""
    if not user_info:
        return []
    try:
        from app.services.ai.skill_resolver import (
            _scan_skill_dir,
            get_user_personal_skills_dir,
        )

        skills_dir = get_user_personal_skills_dir(user_info)
        if not skills_dir or not os.path.isdir(skills_dir):
            return []
        # 兼容历史遗留的 .seed 布局（见 skill_resolver.iter_personal_skill_dirs）
        return _scan_skill_dir(skills_dir, "personal", allow_seed=True) or []
    except Exception:  # noqa: BLE001
        logger.debug("[agent-scope] failed to scan personal skills", exc_info=True)
        return []
