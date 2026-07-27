import json
import logging
import hashlib
import re
from typing import Dict, Any
from pydantic import create_model, Field
from app.services.ai.tools.tool_compat import StructuredTool
from app.models.mcp import McpToolCache
from app.services.ai.tools.mcp_client import McpClientService
from app.services.ai.grounding.models import EvidenceType

logger = logging.getLogger(__name__)


def _build_model_tool_name(tool_name: str) -> str:
    """将平台 MCP 标识转换为模型 Function Calling 可接受的稳定工具名。

    平台以 ``server_name:tool_name`` 保存 MCP 工具，用冒号避免跨服务器重名；
    但 OpenAI 兼容模型只允许字母、数字、下划线和连字符。保留可读部分并追加
    原始名称哈希，既避免非法字符，也避免不同原名清洗后发生碰撞。
    """
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(tool_name)).strip("_")
    readable_name = normalized or "mcp_tool"
    name_hash = hashlib.sha256(str(tool_name).encode("utf-8")).hexdigest()[:10]
    # OpenAI Function Calling 通常限制工具名最多 64 个字符，提前截断以兼容该约束。
    max_readable_length = 64 - len("mcp_") - len(name_hash) - 1
    return f"mcp_{readable_name[:max_readable_length]}_{name_hash}"


class McpToolFactory:
    @staticmethod
    def create_tool(tool_record: McpToolCache) -> StructuredTool:
        """
        Creates a runtime StructuredTool-compatible wrapper from a cached MCP tool record.
        """
        
        # 1. Parse JSON Schema from MCP
        schema_def = json.loads(tool_record.parameter_schema or "{}")
        properties = schema_def.get("properties", {})
        required_fields = set(schema_def.get("required", []))

        fields = {}
        for param_name, param_def in properties.items():
            p_type = str
            type_str = param_def.get("type", "string")
            if type_str == "integer": p_type = int
            elif type_str == "boolean": p_type = bool
            elif type_str == "number": p_type = float
            
            p_desc = param_def.get("description", "")
            p_default = ... if param_name in required_fields else param_def.get("default", None)
            
            fields[param_name] = (p_type, Field(default=p_default, description=p_desc))
        
        # Create dynamic Pydantic model for args
        args_schema = create_model(f"Mcp_{tool_record.tool_name.replace(':', '_')}Args", **fields)
        
        # 2. Define execution logic
        async def _execute(**kwargs) -> Any:
            # Extract raw tool name (remove our prefix)
            # Full name: "server_name:raw_tool_name"
            if ":" in tool_record.tool_name:
                raw_name = tool_record.tool_name.split(":", 1)[1]
            else:
                raw_name = tool_record.tool_name
                
            return await McpClientService.call_remote_tool(
                server_id=tool_record.server_id,
                tool_name=raw_name,
                arguments=kwargs
            )
        
        _execute.__doc__ = tool_record.tool_description or f"MCP tool: {tool_record.tool_name}"
        
        # 数据库存储的冒号名称仅作平台标识；模型侧使用合法别名，执行闭包仍保留原始 MCP 名称。
        tool = StructuredTool.from_function(
            func=None,
            coroutine=_execute,
            name=_build_model_tool_name(tool_record.tool_name),
            description=tool_record.tool_description or "",
            args_schema=args_schema
        )
        declared_types = set()
        for value in schema_def.get("x-nanzi-evidence-types") or []:
            try:
                declared_types.add(EvidenceType(value))
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid evidence type %r for %s", value, tool_record.tool_name)
        annotations = schema_def.get("x-nanzi-mcp-annotations") or {}
        if annotations.get("readOnlyHint") is False or annotations.get("read_only_hint") is False:
            tool.evidence_inference_disabled = True
        if declared_types:
            tool.evidence_types = frozenset(declared_types)
        elif annotations.get("readOnlyHint") is True or annotations.get("read_only_hint") is True:
            tool.evidence_types = frozenset({EvidenceType.EXTERNAL_TOOL})
        if getattr(tool, "evidence_types", None):
            declared_policy = schema_def.get("x-nanzi-evidence-policy")
            tool.evidence_policy = (
                declared_policy
                if declared_policy in {"non_empty", "structured_success", "allow_empty_success"}
                else "allow_empty_success"
            )
        return tool
