"""微信身份绑定表 ORM 模型。

对应迁移 db-prod/V170 与 db-prod-pg/V71。
身份映射刻意使用独立表而非 ai_agent_users.extra_data：
后者没有索引、无法保证 (appid, openid) 唯一，也无法承载 unionid 回退查询。
"""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint

from app.core.orm import Base


class WechatBinding(Base):
    __tablename__ = "ai_agent_wechat_bindings"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    # ⚠️ ai_agent_users.id 在**数据库里是 BIGINT**（尽管 User 模型把它声明为 Integer）。
    # 指向它的外键列一律用 BigInteger —— 这既是平台既有做法（UserRoleRelation.user_id、
    # SavedReport.created_by、Artifact.owner_user_id 等 6 处都是 BigInteger），
    # 也是 MySQL 的硬要求：外键两侧整数类型必须完全一致，写成 INT 会报 errno 3780。
    user_id = Column(BigInteger, ForeignKey("ai_agent_users.id", ondelete="CASCADE"), index=True, nullable=False)
    appid = Column(String(64), nullable=False)
    openid = Column(String(64), nullable=False)
    unionid = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("appid", "openid", name="ux_wechat_binding_appid_openid"),
    )
