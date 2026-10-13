from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class ResourcePermissionBase(BaseModel):
    resource_type: str
    resource_id: str
    enabled: bool = True

class PermissionSet(BaseModel):
    """Represents a set of permissions grouped by resource type"""
    agents: List[str] = Field(default_factory=list, description="List of allowed Agent IDs")
    datasets: List[str] = Field(default_factory=list, description="List of allowed RagFlow Dataset IDs")
    apis: List[str] = Field(default_factory=list, description="List of allowed External API Routes")
    metadata: List[str] = Field(default_factory=list, description="List of allowed Metadata Dataset IDs")
    menus: List[str] = Field(default_factory=list, description="List of allowed Menu IDs")
    elements: List[str] = Field(default_factory=list, description="List of allowed Action/Element IDs")
    forbidden_tools: List[str] = Field(default_factory=list, description="List of forbidden tool names")
    forbidden_commands: List[str] = Field(default_factory=list, description="List of forbidden shell command keywords")
    forbidden_skills: List[str] = Field(
        default_factory=list, description="List of forbidden platform (global) skill IDs"
    )
    models: List[str] = Field(
        default_factory=list,
        description="聊天可手动切换的模型 ID 白名单（空 = 不限制，与 element 语义相反）",
    )

    @field_validator("forbidden_tools", "forbidden_commands", "forbidden_skills", mode="before")
    @classmethod
    def normalize_forbidden_policy_entries(cls, value):
        if value is None:
            return []
        normalized = []
        seen = set()
        for raw_entry in value:
            entry = str(raw_entry).strip()
            if not entry:
                continue
            # 上限与工具名对齐（SysApiTool.name 与外部 MCP 工具名可达 255）。此前是 100，
            # 一个超长工具名被勾中就会让整页权限（含菜单/元素/命令/技能）保存 422，且永远禁不掉。
            if len(entry) > 255:
                raise ValueError("Forbidden policy entries cannot exceed 255 characters")
            dedupe_key = entry.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(entry)
        return normalized

class ResourceDetail(BaseModel):
    id: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None

class PermissionSetDetail(BaseModel):
    """Detailed view of permissions with names and descriptions"""
    agents: List[ResourceDetail] = Field(default_factory=list)
    datasets: List[ResourceDetail] = Field(default_factory=list)
    apis: List[ResourceDetail] = Field(default_factory=list)
    metadata: List[ResourceDetail] = Field(default_factory=list)
    menus: List[ResourceDetail] = Field(default_factory=list)
    elements: List[ResourceDetail] = Field(default_factory=list)
    forbidden_tools: List[ResourceDetail] = Field(default_factory=list)
    forbidden_commands: List[ResourceDetail] = Field(default_factory=list)
    forbidden_skills: List[ResourceDetail] = Field(default_factory=list)
    models: List[ResourceDetail] = Field(default_factory=list)

class UserPermissionsResponse(BaseModel):
    roles: List[str] = Field(default_factory=list, description="Assigned roles (reserved)")
    permissions: PermissionSet
    details: Optional[PermissionSetDetail] = None
    direct_permissions: Optional[PermissionSet] = Field(
        default=None,
        description=(
            "仅该用户直配的权限（不含角色继承）。禁用资源页必须用它回显与提交："
            "permissions 是「用户 ∪ 角色」的有效权限，直接整份写回会把角色级禁用固化成"
            "用户级记录，导致角色侧取消后用户仍被禁（黑名单收不回来）。"
        ),
    )

class PermissionUpdate(PermissionSet):
    """Payload for updating user permissions"""
    pass
