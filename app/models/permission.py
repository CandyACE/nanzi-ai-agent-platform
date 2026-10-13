from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, Index, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.orm import Base

class Role(Base):
    __tablename__ = "ai_agent_roles"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    description = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    users = relationship("User", secondary="ai_agent_user_role_relations", back_populates="roles")

class UserRoleRelation(Base):
    __tablename__ = "ai_agent_user_role_relations"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("ai_agent_users.id"), index=True, nullable=False)
    role_id = Column(BigInteger, ForeignKey("ai_agent_roles.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

class ResourcePermission(Base):
    __tablename__ = "ai_agent_resource_permissions"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, index=True, nullable=True) # Intentionally no FK constraint in ORM for loose coupling, or add ForeignKey if strict
    role_id = Column(BigInteger, index=True, nullable=True)
    # 注意：智能体级作用域列 agent_id **刻意不在这里声明**。
    # 映射里声明它，SELECT 的字段列表与 INSERT 都会带上该列，于是"代码先于迁移上线"
    # 会让权限系统整体报 Unknown column（禁用资源页直接 503）。因此 agent 维度的读写
    # 走 PermissionService 里的原生 SQL，并由列探测（_supports_agent_scope）开关：
    # 未迁移时降级为既有行为，迁移后自动启用。
    resource_type = Column(String(20), nullable=False) # agent, dataset, api
    # 与 db-prod/V167 的扩列保持一致：禁用项候选（工具名 / MCP 运行时名 / 技能 id）可达 255
    resource_id = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Composite indexes are defined in DB, but can be declared here in __table_args__ if needed for migrations
    # __table_args__ = (
    #     Index('idx_user_res', "user_id", "resource_type"),
    # )
