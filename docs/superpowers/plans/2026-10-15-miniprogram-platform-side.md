# 小程序微端（平台侧）实施计划

> **执行方式：** 由 subagent 逐任务实施（每个 Task 一个全新 subagent，任务间由主 agent 审查交接）。⚠️ 本环境**没有** `subagent-driven-development` / `executing-plans` 这两个 skill，不要尝试调用；直接按下方 Task 顺序执行。步骤用 `- [ ]` 勾选跟踪。

**Goal:** 在 NanZi 平台侧落地小程序微端的服务端能力——按微信 openid 自动开户、签发 embed ticket，并让 EmbedChat 在小程序 `web-view` 内正常工作。

**Architecture:** 新增一张独立身份绑定表承载 `openid ↔ user_id` 映射（不写 `extra_data`）；新增一个受 API Key 保护且**显式校验权限**的接口，把「按 openid 开户」与「签发 ticket」合成一步，底层复用既有 `EmbedService.create_ticket`。EmbedChat 的 ticket 认证链路**零改动**，只增加"宿主是小程序"时的行为分支。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.x async / Pydantic 2 / MySQL + PostgreSQL 双套迁移 / Vue 3 + TS / pytest

**Spec:** `docs/superpowers/specs/2026-10-15-miniprogram-embedchat-design.md`

---

## 执行前必读

1. **不要执行 `git commit`**（团队规范）。每个任务末尾的「检查点」只要求汇报改动与验证结果，提交时机与 commit message 由用户决定。
2. **不要执行 `./dev.sh`、部署脚本或生产数据库操作**。
3. **迁移由用户手工导入**。`app/core/database.py:init_db()` 只做健康检查（`SELECT 1`）、**不建表**，因此：
   - Task 1、Task 2 的测试是**纯文本契约测试**，不连数据库，任何情况下都能跑；
   - Task 4、Task 5 的集成测试**必须先请用户导入迁移**（MySQL 导 V170/V171，PG 导 V71/V72），否则会因表不存在而失败。每个相关任务都标注了这个前置条件。
4. **测试命令必须用项目 venv**：一律写成 `.venv/bin/python -m pytest ...`。裸 `pytest` 会报 `ModuleNotFoundError: No module named 'app'`（已实测）。
5. 本计划只覆盖**本仓库（平台侧）**。小程序工程在仓库外（`/Users/chenxiaolong/WeChatProjects/miniprogram-nanzi-ai`），见配套计划 `2026-10-15-miniprogram-miniapp-side.md`。
6. **权限模型的两个硬约束**（写错会直接 403 或留下安全洞）：
   - 接口路径含 `/embed` 会被 `is_v1_api_whitelisted` 放行（`app/core/v1_api_access.py:123`，子串匹配），**自动权限检查不生效**，必须自己挂 `require_permission`；
   - 校验必须**前置于建号**。`create_ticket` 内部也会检查 `POST:/api/v1/embed/tickets`（`app/services/embed_service.py:79-94`），但那发生在**建号之后**——若不前置，未授权者拿不到 ticket 却能刷出账号。

## 文件结构

| 文件 | 职责 |
|---|---|
| `db-prod/V170-create_wechat_bindings.sql` | 建绑定表（MySQL） |
| `db-prod-pg/V71-create_wechat_bindings.sql` | 建绑定表（PG） |
| `db-prod/V171-seed_miniprogram_role_and_config.sql` | 种空角色 + 开关（MySQL） |
| `db-prod-pg/V72-seed_miniprogram_role_and_config.sql` | 种空角色 + 开关（PG） |
| `app/models/wechat_binding.py` | 绑定表 ORM 模型 |
| `app/services/wechat_miniprogram_service.py` | openid 校验 / `instance_id` 派生 / 身份解析与开户 |
| `app/api/v1/endpoints/embed.py`（改） | 新增 `POST /miniprogram/session` |
| `frontend/src/views/EmbedChat.vue`（改） | 小程序宿主分支：环境检测、下载改写、凭证自救、无智能体兜底 |
| `tests/test_miniprogram_migrations.py` | 迁移契约测试（纯文本） |
| `tests/services/test_wechat_miniprogram_service.py` | 服务层测试 |
| `tests/api/v1/test_miniprogram_session.py` | 接口测试 |
| `tests/frontend/test_embedchat_miniprogram_host_contract.py` | 前端契约测试 |
| `tests/CHECKLIST.md`（改） | 测试清单登记 |

---

### Task 1: 迁移 — 建微信身份绑定表

**Files:**
- Create: `tests/test_miniprogram_migrations.py`
- Create: `db-prod/V170-create_wechat_bindings.sql`
- Create: `db-prod-pg/V71-create_wechat_bindings.sql`

- [ ] **Step 1: 写失败的契约测试**

创建 `tests/test_miniprogram_migrations.py`：

```python
"""小程序微端迁移文件的契约测试。

这些断言只读 SQL 文本、不连数据库——迁移由用户手工导入，
测试环境不会自动执行迁移（app/core/database.py:init_db 只做 SELECT 1 健康检查）。
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

REPO_ROOT = Path(__file__).resolve().parents[1]
MYSQL_DIR = REPO_ROOT / "db-prod"
PG_DIR = REPO_ROOT / "db-prod-pg"

MYSQL_CREATE = MYSQL_DIR / "V170-create_wechat_bindings.sql"
PG_CREATE = PG_DIR / "V71-create_wechat_bindings.sql"
MYSQL_SEED = MYSQL_DIR / "V171-seed_miniprogram_role_and_config.sql"
PG_SEED = PG_DIR / "V72-seed_miniprogram_role_and_config.sql"

TABLE = "ai_agent_wechat_bindings"


def test_migration_files_exist():
    for path in (MYSQL_CREATE, PG_CREATE, MYSQL_SEED, PG_SEED):
        assert path.exists(), f"缺少迁移文件: {path}"


def test_mysql_create_table_is_idempotent_and_has_unique_binding_key():
    sql = MYSQL_CREATE.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert TABLE in sql
    # (appid, openid) 必须唯一，否则同一微信会开出多个账号
    assert "ux_wechat_binding_appid_openid" in sql
    for column in ("user_id", "appid", "openid", "unionid", "last_login_at"):
        assert column in sql


def test_pg_create_table_is_idempotent_and_has_unique_binding_key():
    sql = PG_CREATE.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert TABLE in sql
    assert "ux_wechat_binding_appid_openid" in sql
    # PG 侧索引用 IF NOT EXISTS 保证可重复导入
    assert "CREATE INDEX IF NOT EXISTS" in sql


def test_role_seed_is_idempotent_in_both_dialects():
    mysql = MYSQL_SEED.read_text(encoding="utf-8")
    pg = PG_SEED.read_text(encoding="utf-8")

    assert "INSERT IGNORE" in mysql
    assert "ON CONFLICT" in pg
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_miniprogram_migrations.py -v`

Expected: FAIL —— `test_migration_files_exist` 报 `缺少迁移文件: .../V170-create_wechat_bindings.sql`

- [ ] **Step 3: 写 MySQL 建表迁移**

创建 `db-prod/V170-create_wechat_bindings.sql`：

```sql
-- V170: 微信小程序用户身份绑定表（MySQL 方言）
-- 变更原因：小程序微端需要按 openid 定位平台账号。该映射不能塞进
--           ai_agent_users.extra_data——那里没有索引，也无法保证 (appid, openid) 唯一。
-- 需求背景：微信小程序静默登录自动开户（见 docs/superpowers/specs/2026-10-15-miniprogram-embedchat-design.md）
-- 创建时间：2026-10-15
-- 注意事项：本脚本仅由 Agent 生成，不得自动执行，请由用户手工导入更新到数据库。
--           apply_sql.py 无 schema_migrations 记录表，幂等必须写在 SQL 自身。

CREATE TABLE IF NOT EXISTS ai_agent_wechat_bindings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    user_id BIGINT NOT NULL COMMENT '平台账号ID（ai_agent_users.id）',
    appid VARCHAR(64) NOT NULL COMMENT '小程序 AppID',
    openid VARCHAR(64) NOT NULL COMMENT '该 AppID 下的微信用户标识',
    unionid VARCHAR(64) NULL COMMENT '微信开放平台统一标识，可空；用于跨应用复用同一账号',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_login_at DATETIME NULL COMMENT '最近一次命中该绑定的时间',
    CONSTRAINT fk_wechat_binding_user
        FOREIGN KEY (user_id) REFERENCES ai_agent_users(id)
        ON DELETE CASCADE,
    UNIQUE KEY ux_wechat_binding_appid_openid (appid, openid),
    KEY ix_wechat_binding_user_id (user_id),
    KEY ix_wechat_binding_unionid (unionid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='微信小程序身份绑定表';
```

- [ ] **Step 4: 写 PG 建表迁移**

创建 `db-prod-pg/V71-create_wechat_bindings.sql`：

```sql
-- =====================================================================
-- 变更原因：小程序微端需要按 openid 定位平台账号。该映射不能塞进
--           ai_agent_users.extra_data——那里没有索引，也无法保证 (appid, openid) 唯一。
-- 需求背景：微信小程序静默登录自动开户（PostgreSQL 方言）
-- 创建时间：2026-10-15
-- 注意事项：该脚本仅做生成，不得由 Agent 自动执行，由用户手动导入更新到数据库。
--           apply_sql.py 无 schema_migrations 记录表，幂等必须写在 SQL 自身。
-- =====================================================================

CREATE TABLE IF NOT EXISTS "ai_agent_wechat_bindings" (
    "id" BIGSERIAL PRIMARY KEY,
    -- 平台账号ID（ai_agent_users.id）
    "user_id" BIGINT NOT NULL,
    -- 小程序 AppID
    "appid" VARCHAR(64) NOT NULL,
    -- 该 AppID 下的微信用户标识
    "openid" VARCHAR(64) NOT NULL,
    -- 微信开放平台统一标识，可空；用于跨应用复用同一账号
    "unionid" VARCHAR(64),
    -- 创建时间
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- 最近一次命中该绑定的时间
    "last_login_at" TIMESTAMP,
    CONSTRAINT "fk_wechat_binding_user"
        FOREIGN KEY ("user_id") REFERENCES "ai_agent_users" ("id")
        ON DELETE CASCADE,
    CONSTRAINT "ux_wechat_binding_appid_openid" UNIQUE ("appid", "openid")
);

CREATE INDEX IF NOT EXISTS "ix_wechat_binding_user_id"
    ON "ai_agent_wechat_bindings" ("user_id");

CREATE INDEX IF NOT EXISTS "ix_wechat_binding_unionid"
    ON "ai_agent_wechat_bindings" ("unionid");
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `pytest tests/test_miniprogram_migrations.py -v`

Expected: 4 个测试中 `test_migration_files_exist`、两个建表测试 PASS；`test_role_seed_is_idempotent_in_both_dialects` 仍 FAIL（种子文件尚未创建）——这是预期的，Task 2 会修好。

- [ ] **Step 6: 检查点（不提交）**

汇报：新增了哪两个 SQL 文件、`pytest tests/test_miniprogram_migrations.py -v` 的实际输出。等待用户决定是否提交。

---

### Task 2: 迁移 — 种「小程序用户」空角色与功能开关

**Files:**
- Create: `db-prod/V171-seed_miniprogram_role_and_config.sql`
- Create: `db-prod-pg/V72-seed_miniprogram_role_and_config.sql`
- Modify: `tests/test_miniprogram_migrations.py`（追加两个测试）

- [ ] **Step 1: 追加失败的测试**

在 `tests/test_miniprogram_migrations.py` 末尾追加：

```python
def test_role_seed_uses_stable_code_and_grants_no_permissions():
    """D3：只种空角色。种了权限行会让「可见智能体」白名单被意外放宽。"""
    for path in (MYSQL_SEED, PG_SEED):
        sql = path.read_text(encoding="utf-8")
        assert "miniprogram_user" in sql
        assert "小程序用户" in sql
        assert "ai_agent_resource_permissions" not in sql


def test_config_seed_defaults_disabled_and_never_overwrites_value():
    """开关默认关闭；且种子不得覆盖管理员已改过的 value。"""
    for path in (MYSQL_SEED, PG_SEED):
        sql = path.read_text(encoding="utf-8")
        assert "miniprogram_enabled" in sql
        assert "'false'" in sql
        # 不允许 DO UPDATE / ON DUPLICATE KEY UPDATE——那会在重复导入时
        # 覆盖管理员已开启的开关状态
        assert "ON DUPLICATE KEY UPDATE" not in sql
        assert "DO UPDATE" not in sql
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_miniprogram_migrations.py -v`

Expected: 两条新测试 FAIL（种子文件不存在 → `FileNotFoundError`）

- [ ] **Step 3: 写 MySQL 种子迁移**

创建 `db-prod/V171-seed_miniprogram_role_and_config.sql`：

```sql
-- V171: 小程序微端：业务角色种子 + 功能开关（MySQL 方言）
-- 设计决策 D3：只种【空角色】，不种任何权限行。
--   智能体可见性是白名单（系统智能体必须在角色权限聚合出的 allowed_ids 内才可见），
--   因此空角色 = 看不到任何智能体，属 fail-safe 默认；
--   可见智能体与配额由管理员在后台「角色管理」中勾选。
-- 注意事项：本脚本仅由 Agent 生成，不得自动执行，请由用户手工导入。
--   使用 INSERT IGNORE（幂等插入，不做覆盖式更新）：
--   重复导入时不得覆盖管理员已改过的 miniprogram_enabled 开关值。

INSERT IGNORE INTO `ai_agent_roles` (`code`, `name`, `description`)
VALUES (
    'miniprogram_user',
    '小程序用户',
    '微信小程序静默登录自动开户的用户；可见智能体与配额由管理员在后台配置'
);

INSERT IGNORE INTO `system_configs` (`key`, `value`, `description`, `category`, `is_secret`)
VALUES (
    'miniprogram_enabled',
    'false',
    '是否开启微信小程序微端自动开户与签票 (true/false)',
    'other',
    0
);
```

- [ ] **Step 4: 写 PG 种子迁移**

创建 `db-prod-pg/V72-seed_miniprogram_role_and_config.sql`：

```sql
-- =====================================================================
-- 变更原因：小程序微端需要业务角色与功能开关（PostgreSQL 方言）
-- 设计决策 D3：只种【空角色】，不种任何权限行。
--   智能体可见性是白名单，空角色 = 看不到任何智能体，属 fail-safe 默认；
--   可见智能体与配额由管理员在后台「角色管理」中勾选。
-- 创建时间：2026-10-15
-- 注意事项：该脚本仅做生成，不得由 Agent 自动执行，由用户手动导入。
--   使用 ON CONFLICT DO NOTHING（幂等插入，不做覆盖式更新）：
--   重复导入时不得覆盖管理员已改过的 miniprogram_enabled 开关值。
-- =====================================================================

INSERT INTO "ai_agent_roles" ("code", "name", "description")
VALUES (
    'miniprogram_user',
    '小程序用户',
    '微信小程序静默登录自动开户的用户；可见智能体与配额由管理员在后台配置'
)
ON CONFLICT ("code") DO NOTHING;

INSERT INTO "system_configs" ("key", "value", "description", "category", "is_secret")
VALUES (
    'miniprogram_enabled',
    'false',
    '是否开启微信小程序微端自动开户与签票 (true/false)',
    'other',
    FALSE
)
ON CONFLICT ("key") DO NOTHING;
```

- [ ] **Step 5: 运行测试，确认全部通过**

Run: `pytest tests/test_miniprogram_migrations.py -v`

Expected: 6 条测试全部 PASS

- [ ] **Step 6: 请用户导入迁移（阻塞后续集成测试）**

告知用户：**Task 4 与 Task 5 的集成测试需要这两张表和新角色存在**，请手工导入：

- MySQL 环境：`db-prod/V170-create_wechat_bindings.sql`、`db-prod/V171-seed_miniprogram_role_and_config.sql`
- PostgreSQL 环境：`db-prod-pg/V71-create_wechat_bindings.sql`、`db-prod-pg/V72-seed_miniprogram_role_and_config.sql`

（Agent 不代跑导入脚本。）

- [ ] **Step 7: 检查点（不提交）**

汇报：两个种子 SQL 文件、6 条测试通过的实际输出。

---

### Task 3: 绑定表 ORM 模型

**Files:**
- Create: `app/models/wechat_binding.py`
- Modify: `tests/services/test_wechat_miniprogram_service.py`（新建，先放模型契约测试）

- [ ] **Step 1: 写失败的模型契约测试**

创建 `tests/services/test_wechat_miniprogram_service.py`：

```python
"""小程序微端服务层测试。

模型部分为纯契约断言（不连库）；身份解析部分为集成测试，
依赖已导入的 V170/V171（或 PG 的 V71/V72）迁移。
"""

import pytest

pytestmark = pytest.mark.no_infrastructure


def test_binding_model_matches_migration_shape():
    from app.models.wechat_binding import WechatBinding

    assert WechatBinding.__tablename__ == "ai_agent_wechat_bindings"

    columns = {c.name for c in WechatBinding.__table__.columns}
    assert columns == {
        "id",
        "user_id",
        "appid",
        "openid",
        "unionid",
        "created_at",
        "last_login_at",
    }

    # (appid, openid) 唯一约束必须声明在 ORM 里，否则代码与迁移会漂移
    unique_columns = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in WechatBinding.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("appid", "openid") in unique_columns
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/services/test_wechat_miniprogram_service.py -v`

Expected: FAIL —— `ModuleNotFoundError: No module named 'app.models.wechat_binding'`

- [ ] **Step 3: 写模型**

创建 `app/models/wechat_binding.py`：

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/services/test_wechat_miniprogram_service.py -v`

Expected: PASS（1 条测试）

- [ ] **Step 5: 检查点（不提交）**

汇报：新增 `app/models/wechat_binding.py`、测试通过输出。

---

### Task 4: 服务层 — openid 校验、instance_id 派生、身份解析与开户

**Files:**
- Create: `app/services/wechat_miniprogram_service.py`
- Modify: `tests/services/test_wechat_miniprogram_service.py`（整体替换，再追加集成测试）

**前置条件：** 集成测试需要 `ai_agent_wechat_bindings` 表与 `miniprogram_user` 角色已存在，请先完成 Task 2 Step 6 的迁移导入。

- [ ] **Step 1: 重写测试文件（拆掉模块级 no_infrastructure，加纯函数测试）**

把 `tests/services/test_wechat_miniprogram_service.py` **整体替换**为：

```python
"""小程序微端服务层测试。

- 模型契约与纯函数测试不连库（no_infrastructure）；
- 身份解析测试需要真实数据库，依赖已导入的 V170/V171（或 PG 的 V71/V72）。

注意：这里不能用模块级 pytestmark——本文件同时含有需要数据库的集成测试。
"""

import pytest


# --------------------------------------------------------------------------- #
# 模型契约（不连库）
# --------------------------------------------------------------------------- #

@pytest.mark.no_infrastructure
def test_binding_model_matches_migration_shape():
    from app.models.wechat_binding import WechatBinding

    assert WechatBinding.__tablename__ == "ai_agent_wechat_bindings"

    columns = {c.name for c in WechatBinding.__table__.columns}
    assert columns == {
        "id",
        "user_id",
        "appid",
        "openid",
        "unionid",
        "created_at",
        "last_login_at",
    }

    # (appid, openid) 唯一约束必须声明在 ORM 里，否则代码与迁移会漂移
    unique_columns = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in WechatBinding.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("appid", "openid") in unique_columns


# --------------------------------------------------------------------------- #
# 纯函数（不连库）
# --------------------------------------------------------------------------- #

@pytest.mark.no_infrastructure
def test_derive_instance_id_is_stable_and_user_specific():
    from app.services.wechat_miniprogram_service import derive_instance_id

    a1 = derive_instance_id("oABC1234567890123456789012")
    a2 = derive_instance_id("oABC1234567890123456789012")
    b = derive_instance_id("oZZZ1234567890123456789012")

    assert a1 == a2, "同一 openid 必须派生出同一 instance_id（会话分桶需稳定）"
    assert a1 != b, "不同 openid 不得碰撞，否则会共用会话分桶"
    assert a1.startswith("wx_")
    assert len(a1) == 3 + 16


@pytest.mark.no_infrastructure
def test_derive_user_name_is_stable_and_does_not_leak_openid():
    from app.services.wechat_miniprogram_service import derive_user_name

    openid = "oABC1234567890123456789012"
    name = derive_user_name(openid)

    assert name == derive_user_name(openid)
    assert name.startswith("wx_")
    assert openid not in name, "账号名不得包含明文 openid"


@pytest.mark.no_infrastructure
@pytest.mark.parametrize(
    "openid,expected",
    [
        ("oABC1234567890123456789012", True),          # 28 位典型 openid
        ("abc_DEF-12345678901234567890", True),        # 允许 - 和 _
        ("", False),
        ("short", False),
        ("has space 12345678901234567", False),
        ("中文openid123456789012345", False),
        ("a" * 65, False),                             # 超长
    ],
)
def test_is_valid_openid(openid, expected):
    from app.services.wechat_miniprogram_service import is_valid_openid

    assert is_valid_openid(openid) is expected
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/services/test_wechat_miniprogram_service.py -v`

Expected: 模型契约测试 PASS；3 组纯函数测试 FAIL —— `ModuleNotFoundError: No module named 'app.services.wechat_miniprogram_service'`

- [ ] **Step 3: 写服务实现**

创建 `app/services/wechat_miniprogram_service.py`：

```python
"""微信小程序微端服务：按 openid 解析或创建平台账号，并派生会话实例标识。

设计要点见 docs/superpowers/specs/2026-10-15-miniprogram-embedchat-design.md：
- openid 由小程序云函数用 cloud.getWXContext() 取得，平台不自行调用 code2session；
- 身份映射落在独立绑定表 ai_agent_wechat_bindings，不写 ai_agent_users.extra_data；
- 自动开户只挂空角色「小程序用户」，不授予任何 api: 权限。
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Role, UserRoleRelation
from app.models.user import USER_STATUS_ENABLED, User
from app.models.wechat_binding import WechatBinding
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

MINIPROGRAM_ROLE_CODE = "miniprogram_user"
MINIPROGRAM_USER_REAL_NAME = "微信用户"

# 微信 openid 典型为 28 位 [A-Za-z0-9_-]；放宽到 16~64 位以兼容未知变化
_OPENID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


class MiniprogramIdentityError(ValueError):
    """openid / appid 等外部入参不合法。"""


def is_valid_openid(openid: Optional[str]) -> bool:
    """校验 openid 形态。非法值必须在入库前拦掉。"""
    return bool(openid) and bool(_OPENID_PATTERN.match(openid))


def _digest16(openid: str) -> str:
    return hashlib.sha256(openid.encode("utf-8")).hexdigest()[:16]


def derive_user_name(openid: str) -> str:
    """按 openid 确定性派生账号名。

    后台 UpdateUserRequest 不含 user_name（账号名建后不可改），因此必须自 openid
    派生以保证同一微信每次都命中同一账号名。仅在「建号」路径使用——改名后的
    二次识别走绑定表，不依赖本函数。
    """
    return f"wx_{_digest16(openid)}"


def derive_instance_id(openid: str) -> str:
    """按 openid 派生前端会话实例标识。

    该值决定 EmbedChat 的会话分桶与本地存储键（conversationStorageKey /
    EMBED_SESSION_STORAGE_PREFIX），必须逐用户隔离：写死会让所有微信用户共用一个分桶。
    """
    return f"wx_{_digest16(openid)}"


async def _find_binding(db: AsyncSession, appid: str, openid: str) -> Optional[WechatBinding]:
    stmt = select(WechatBinding).where(
        WechatBinding.appid == appid, WechatBinding.openid == openid
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _find_binding_by_unionid(db: AsyncSession, unionid: str) -> Optional[WechatBinding]:
    stmt = select(WechatBinding).where(WechatBinding.unionid == unionid).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _find_user_by_name(db: AsyncSession, user_name: str) -> Optional[User]:
    stmt = select(User).where(User.user_name == user_name)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _attach_miniprogram_role(db: AsyncSession, user_id: int) -> None:
    """挂上「小程序用户」角色；角色不存在时告警但不阻断开户。"""
    role = (
        await db.execute(select(Role).where(Role.code == MINIPROGRAM_ROLE_CODE))
    ).scalar_one_or_none()
    if role is None:
        logger.warning(
            "角色 %s 不存在，已跳过角色绑定（迁移 V171/V72 是否已导入？）",
            MINIPROGRAM_ROLE_CODE,
        )
        return

    existing = (
        await db.execute(
            select(UserRoleRelation).where(
                UserRoleRelation.user_id == user_id,
                UserRoleRelation.role_id == role.id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(UserRoleRelation(user_id=user_id, role_id=role.id))


async def resolve_or_create_user(
    openid: str,
    appid: str,
    db: AsyncSession,
    unionid: Optional[str] = None,
) -> Dict[str, Any]:
    """按 (appid, openid) 解析账号；未命中回退 unionid；仍未命中则建号。

    返回 {"user_id": int, "user_name": str, "is_new": bool}
    """
    if not is_valid_openid(openid):
        raise MiniprogramIdentityError("openid 缺失或格式非法")
    if not appid:
        raise MiniprogramIdentityError("appid 缺失")

    binding = await _find_binding(db, appid, openid)
    matched_by_unionid = False
    if binding is None and unionid:
        binding = await _find_binding_by_unionid(db, unionid)
        matched_by_unionid = binding is not None

    if binding is not None:
        user = (
            await db.execute(select(User).where(User.id == binding.user_id))
        ).scalar_one_or_none()
        if user is None:
            raise MiniprogramIdentityError("绑定记录指向的账号不存在")
        if user.status != USER_STATUS_ENABLED:
            raise PermissionError("账号已被禁用")

        if matched_by_unionid:
            # 同一微信换应用（多小程序/公众号）：补一条新绑定行，复用同一账号
            db.add(
                WechatBinding(user_id=user.id, appid=appid, openid=openid, unionid=unionid)
            )
        binding.last_login_at = datetime.now()
        await db.commit()
        return {"user_id": user.id, "user_name": user.user_name, "is_new": False}

    # 建号。generate_api_key 会签发长期 API Key：明文必须就地丢弃，
    # 绝不返回给调用方、绝不写日志。「小程序用户」角色不得有任何 api: 权限，
    # 否则这枚 Key 会成为绕过前端的 V1 接口通道。
    user_name = derive_user_name(openid)
    user = await _find_user_by_name(db, user_name)
    if user is None:
        await AuthService.generate_api_key(
            user_name=user_name,
            role="user",
            real_name=MINIPROGRAM_USER_REAL_NAME,
            status=USER_STATUS_ENABLED,
            db=db,
        )
        user = await _find_user_by_name(db, user_name)
        if user is None:
            raise RuntimeError("账号创建后无法查回")
        is_new = True
    else:
        # 账号名已存在但无绑定（例如管理员手工建过同名账号）：复用而不是报错
        is_new = False
        if user.status != USER_STATUS_ENABLED:
            raise PermissionError("账号已被禁用")

    await _attach_miniprogram_role(db, user.id)
    db.add(
        WechatBinding(
            user_id=user.id,
            appid=appid,
            openid=openid,
            unionid=unionid,
            last_login_at=datetime.now(),
        )
    )
    await db.commit()
    return {"user_id": user.id, "user_name": user.user_name, "is_new": is_new}


NEW_ACCOUNT_BURST_THRESHOLD = 5000


async def warn_if_new_account_burst() -> None:
    """高阈值建号熔断告警：只打日志，**绝不**阻断请求。

    这是「防雪崩」而非「风控」（spec §7.3）：云函数若因 bug 反复重试、
    或调用方被刷，会自动建出大量账号。达到阈值时告警一次，让人去看。
    刻意不做限流——云函数的出口 IP 是共享的、按调用者计数会误伤正常流量。
    """
    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        if redis is None:
            return
        key = f"miniprogram:new_accounts:{datetime.now().strftime('%Y%m%d')}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 172800)
        if count == NEW_ACCOUNT_BURST_THRESHOLD:
            logger.error(
                "小程序微端当日新建账号已达 %d 个，请检查云函数是否异常重试",
                NEW_ACCOUNT_BURST_THRESHOLD,
            )
    except Exception as e:  # 计数失败绝不能影响开户
        logger.warning("微端建号熔断计数失败（不影响开户）: %s", e)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/services/test_wechat_miniprogram_service.py -v`

Expected: 全部 PASS（模型契约 1 条 + 纯函数 3 组共 11 个用例）

- [ ] **Step 5: 追加集成测试（身份解析）**

在 `tests/services/test_wechat_miniprogram_service.py` 末尾追加：

```python
# --------------------------------------------------------------------------- #
# 身份解析与开户（需要真实数据库 + 已导入迁移）
# --------------------------------------------------------------------------- #

APPID = "wx1ca87185956d0071"


async def test_resolve_creates_account_with_role_and_binding(db_session):
    from sqlalchemy import select

    from app.models.permission import Role, UserRoleRelation
    from app.models.user import User
    from app.models.wechat_binding import WechatBinding
    from app.services.wechat_miniprogram_service import resolve_or_create_user

    openid = "oTestOpenid0000000000000001"

    result = await resolve_or_create_user(openid=openid, appid=APPID, db=db_session)

    assert result["is_new"] is True
    assert result["user_name"].startswith("wx_")

    user = (
        await db_session.execute(select(User).where(User.id == result["user_id"]))
    ).scalar_one()
    assert user.status == 1
    assert user.password_hash is None, "小程序账号不应有密码"
    assert user.role == "user"

    role = (
        await db_session.execute(select(Role).where(Role.code == "miniprogram_user"))
    ).scalar_one_or_none()
    if role is not None:
        relation = (
            await db_session.execute(
                select(UserRoleRelation).where(
                    UserRoleRelation.user_id == user.id,
                    UserRoleRelation.role_id == role.id,
                )
            )
        ).scalar_one_or_none()
        assert relation is not None, "必须挂上「小程序用户」角色"

    binding = (
        await db_session.execute(
            select(WechatBinding).where(
                WechatBinding.appid == APPID, WechatBinding.openid == openid
            )
        )
    ).scalar_one()
    assert binding.user_id == user.id


async def test_resolve_is_idempotent_for_same_openid(db_session):
    from app.services.wechat_miniprogram_service import resolve_or_create_user

    openid = "oTestOpenid0000000000000002"

    first = await resolve_or_create_user(openid=openid, appid=APPID, db=db_session)
    second = await resolve_or_create_user(openid=openid, appid=APPID, db=db_session)

    assert first["user_id"] == second["user_id"]
    assert first["is_new"] is True
    assert second["is_new"] is False


async def test_resolve_reuses_account_across_appids_via_unionid(db_session):
    from app.services.wechat_miniprogram_service import resolve_or_create_user

    unionid = "uTestUnionid000000000001"

    first = await resolve_or_create_user(
        openid="oTestOpenid0000000000000003",
        appid="wxappidA000000001",
        unionid=unionid,
        db=db_session,
    )
    second = await resolve_or_create_user(
        openid="oTestOpenid0000000000000004",
        appid="wxappidB000000002",
        unionid=unionid,
        db=db_session,
    )

    assert second["user_id"] == first["user_id"], "同 unionid 应复用同一账号"
    assert second["is_new"] is False


async def test_resolve_rejects_invalid_openid_without_creating_account(db_session):
    from sqlalchemy import func, select

    from app.models.user import User
    from app.services.wechat_miniprogram_service import (
        MiniprogramIdentityError,
        resolve_or_create_user,
    )

    before = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()

    with pytest.raises(MiniprogramIdentityError):
        await resolve_or_create_user(openid="bad openid", appid=APPID, db=db_session)

    after = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert after == before, "非法 openid 不得产生任何账号"
```

- [ ] **Step 6: 运行集成测试**

Run: `pytest tests/services/test_wechat_miniprogram_service.py -v`

Expected: 全部 PASS。若报 `Table 'xxx.ai_agent_wechat_bindings' doesn't exist`，说明迁移尚未导入——回到 Task 2 Step 6。

- [ ] **Step 7: 检查点（不提交）**

汇报：新增 service、测试通过输出、有没有 `角色 miniprogram_user 不存在` 的告警日志。

---

### Task 5: 新增接口 `POST /api/v1/embed/miniprogram/session`

**Files:**
- Modify: `app/api/v1/endpoints/embed.py`
- Create: `tests/api/v1/test_miniprogram_session.py`

- [ ] **Step 1: 写失败的接口测试**

创建 `tests/api/v1/test_miniprogram_session.py`：

```python
"""小程序微端签票接口测试。

前置条件：已导入 V170/V171（MySQL）或 V71/V72（PG）。
接口挂在 embed.py 的 router 上（v1_secured 之下，需 API Key）。
"""

import pytest
from sqlalchemy import func, select

from app.models.user import User
from app.services.config_service import ConfigService

URL = "/api/v1/embed/miniprogram/session"
OPENID = "oApiTestOpenid000000000001"
APPID = "wx1ca87185956d0071"


@pytest.fixture
async def miniprogram_on():
    """打开微端开关，结束后恢复原值。"""
    original = await ConfigService.get("miniprogram_enabled")
    await ConfigService.set_config(
        "miniprogram_enabled", "true", changed_by="pytest", change_reason="微端接口测试"
    )
    yield
    await ConfigService.set_config(
        "miniprogram_enabled",
        original if original is not None else "false",
        changed_by="pytest",
        change_reason="微端接口测试恢复",
    )


async def test_requires_api_key(client, miniprogram_on):
    resp = await client.post(URL, json={"openid": OPENID, "appid": APPID})
    assert resp.status_code in (401, 403), resp.text


async def test_user_without_impersonation_permission_is_forbidden_and_creates_no_account(
    client, valid_api_key, miniprogram_on, db_session
):
    """守护「权限校验前置于建号」——否则这是刷号入口。"""
    before = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()

    resp = await client.post(
        URL,
        json={"openid": OPENID, "appid": APPID},
        headers={"X-API-Key": valid_api_key},
    )

    assert resp.status_code == 403, resp.text

    after = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert after == before, "403 时不得产生任何新账号"


async def test_disabled_switch_returns_403(client, admin_api_key):
    # 迁移种子默认即为 false，这里显式确保
    await ConfigService.set_config("miniprogram_enabled", "false", changed_by="pytest")

    resp = await client.post(
        URL,
        json={"openid": OPENID, "appid": APPID},
        headers={"X-API-Key": admin_api_key},
    )

    assert resp.status_code == 403, resp.text
    assert "未开启" in resp.text


async def test_admin_gets_ticket_and_identity_summary(client, admin_api_key, miniprogram_on):
    resp = await client.post(
        URL,
        json={"openid": OPENID, "appid": APPID},
        headers={"X-API-Key": admin_api_key},
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["ticket"].startswith("emt_")
    assert data["expires_in"] > 0
    assert data["instance_id"].startswith("wx_")
    assert data["user"]["user_name"].startswith("wx_")
    assert data["user"]["is_new"] is True

    # 敏感字段绝不出现在响应里
    assert "api_key" not in resp.text
    assert OPENID not in resp.text


async def test_same_openid_is_idempotent(client, admin_api_key, miniprogram_on):
    first = await client.post(
        URL, json={"openid": OPENID, "appid": APPID}, headers={"X-API-Key": admin_api_key}
    )
    second = await client.post(
        URL, json={"openid": OPENID, "appid": APPID}, headers={"X-API-Key": admin_api_key}
    )

    assert first.status_code == 200 and second.status_code == 200, first.text + second.text
    a, b = first.json()["data"], second.json()["data"]

    assert a["user"]["user_id"] == b["user"]["user_id"]
    assert a["user"]["is_new"] is True
    assert b["user"]["is_new"] is False
    assert a["instance_id"] == b["instance_id"]


async def test_invalid_openid_returns_400_without_creating_account(
    client, admin_api_key, miniprogram_on, db_session
):
    before = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()

    resp = await client.post(
        URL,
        json={"openid": "bad openid", "appid": APPID},
        headers={"X-API-Key": admin_api_key},
    )

    assert resp.status_code == 400, resp.text

    after = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert after == before
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/api/v1/test_miniprogram_session.py -v`

Expected: 全部 FAIL（404，路由不存在）

- [ ] **Step 3: 加导入**

在 `app/api/v1/endpoints/embed.py` 顶部把导入改为：

```python
from app.core.dependencies import require_api_key, get_db_session, require_permission
from app.services.embed_service import EmbedService, TICKET_TTL_SECONDS
from app.services.wechat_miniprogram_service import (
    MiniprogramIdentityError,
    derive_instance_id,
    resolve_or_create_user,
    warn_if_new_account_burst,
)
```

（`require_api_key` / `get_db_session` 原本就有，只需补 `require_permission`、`TICKET_TTL_SECONDS` 与三个 service 符号。）

- [ ] **Step 4: 加请求/响应模型**

在 `app/api/v1/endpoints/embed.py` 里、`create_embed_ticket` 函数**之前**插入：

```python
class MiniprogramSessionRequest(BaseModel):
    openid: str = Field(
        ...,
        description=(
            "微信用户在该小程序下的 openid。由小程序云函数用 cloud.getWXContext() 取得；"
            "平台不接收浏览器直接传入的值（该接口仅对持 API Key 的云函数开放）。"
        ),
        json_schema_extra={"example": "oABC1234567890123456789012"},
    )
    appid: str = Field(
        ...,
        description="小程序 AppID",
        json_schema_extra={"example": "wx1ca87185956d0071"},
    )
    unionid: Optional[str] = Field(None, description="微信开放平台 unionid，可空")
    agent_id: Optional[str] = Field(None, description="可选：锁定智能体 ID")


class MiniprogramIdentitySummary(BaseModel):
    user_id: int = Field(..., description="平台账号 ID")
    user_name: str = Field(..., description="平台账号名（自 openid 派生）")
    is_new: bool = Field(..., description="本次调用是否新建了账号")


class MiniprogramSessionResponseData(BaseModel):
    ticket: str = Field(..., description="一次性短时 Ticket")
    expires_in: int = Field(..., description="Ticket 有效时长（秒）")
    instance_id: str = Field(
        ..., description="前端会话实例标识（逐 openid 派生，用于会话分桶）"
    )
    user: MiniprogramIdentitySummary = Field(
        ..., description="身份摘要（不含 openid / unionid / API Key）"
    )
```

- [ ] **Step 5: 加接口实现**

在 `app/api/v1/endpoints/embed.py` 的 `create_embed_ticket` 之后插入：

```python
@router.post(
    "/miniprogram/session",
    response_model=StandardResponse[MiniprogramSessionResponseData],
    summary="小程序微端：按 openid 自动开户并签发嵌入凭证",
    description=(
        "供微信小程序云函数调用（云函数用 cloud.getWXContext() 取得 openid 后转发）。"
        "平台按 (appid, openid) 解析账号；未命中且带了 unionid 则回退 unionid；仍未命中则自动开户、"
        "挂「小程序用户」角色，最后签发一次性 Ticket。"
        "权限复用 POST:/api/v1/embed/tickets —— /embed 路径在 V1 白名单内、自动校验不生效，"
        "故此处必须显式校验，且必须前置于建号，否则会成为刷号入口。"
    ),
    dependencies=[Depends(require_permission("api", "POST:/api/v1/embed/tickets"))],
)
async def create_miniprogram_session(
    payload: MiniprogramSessionRequest,
    current_user: dict = Depends(require_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    from app.services.config_service import ConfigService

    if await ConfigService.get("miniprogram_enabled") != "true":
        raise HTTPException(status_code=403, detail="微信小程序微端未开启")

    try:
        identity = await resolve_or_create_user(
            openid=payload.openid,
            appid=payload.appid,
            unionid=payload.unionid,
            db=db,
        )
    except MiniprogramIdentityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if identity["is_new"]:
        # 防雪崩：只告警、不阻断（见 service 中的 warn_if_new_account_burst）
        await warn_if_new_account_burst()

    try:
        ticket_data = await EmbedService.create_ticket(
            operator_user=current_user,
            target_user_id=identity["user_id"],
            agent_id=payload.agent_id,
            expires_in=TICKET_TTL_SECONDS,
            db=db,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to create miniprogram session ticket: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create miniprogram session")

    return StandardResponse(
        data=MiniprogramSessionResponseData(
            ticket=ticket_data["ticket"],
            expires_in=ticket_data["expires_in"],
            instance_id=derive_instance_id(payload.openid),
            user=MiniprogramIdentitySummary(**identity),
        )
    )
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `pytest tests/api/v1/test_miniprogram_session.py -v`

Expected: 6 条测试全部 PASS

- [ ] **Step 7: 回归 embed 既有测试**

Run: `pytest tests/ -k "embed" -v`

Expected: 既有 embed 测试全部 PASS（本次未改 `create_ticket` / `exchange_ticket`）

- [ ] **Step 8: 检查点（不提交）**

汇报：接口实现、6 条测试通过输出、embed 回归结果。

---

### Task 6: EmbedChat 小程序宿主适配

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Create: `tests/frontend/test_embedchat_miniprogram_host_contract.py`

**背景**：小程序 `web-view` 内不能触发 `<a download>`（会被微信拦截）；且 H5 → 小程序的**唯一即时通道**是 `wx.miniProgram.*`（`postMessage` 只在后退/销毁/分享时批量触发，不能用于实时通知）。

- [ ] **Step 1: 写失败的契约测试**

创建 `tests/frontend/test_embedchat_miniprogram_host_contract.py`：

```python
"""EmbedChat 小程序宿主适配契约测试。

只做源码静态断言（沿用 tests/frontend 既有风格），不启动浏览器。
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/views/EmbedChat.vue"


def test_view_exists():
    assert VIEW.exists(), f"缺少视图文件: {VIEW}"


def test_detects_miniprogram_host():
    view = VIEW.read_text(encoding="utf-8")

    # 微信 JSSDK 注入的环境标记；UA 作为兜底
    assert "__wxjs_environment" in view
    assert "miniProgram" in view
    assert "isMiniprogramHost" in view


def test_file_open_is_redirected_to_native_page():
    view = VIEW.read_text(encoding="utf-8")

    assert "/pages/file/file" in view
    assert "openFileInMiniapp" in view
    assert "navigateTo" in view


def test_credential_failure_can_relaunch_chat_page():
    """凭证失效时让小程序重新签票，而不是把用户留在白屏。"""
    view = VIEW.read_text(encoding="utf-8")

    assert "/pages/chat/chat" in view
    assert "relaunchMiniappChat" in view
    assert "reLaunch" in view


def test_has_no_agent_fallback_copy():
    """兜底文案必须真的被**渲染**——只断言字符串存在是假通过。"""
    view = VIEW.read_text(encoding="utf-8")

    assert "尚未开放智能体，请联系管理员" in view
    # 必须出现在模板插值里，而不是只定义了一个没人用的常量（那还会触发 TS6133）
    assert "{{ MINIPROGRAM_NO_AGENT_HINT }}" in view


def test_does_not_rely_on_postmessage_for_realtime_flow():
    """postMessage 只在后退/销毁/分享时批量触发，不能用于实时通知。"""
    view = VIEW.read_text(encoding="utf-8")

    assert "miniProgram.postMessage" not in view
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_embedchat_miniprogram_host_contract.py -v`

Expected: `test_view_exists` PASS；其余 FAIL

- [ ] **Step 3: 定位现有的文件下载/预览落点**

Run: `grep -n "createElement('a')\|createObjectURL\|download" frontend/src/views/EmbedChat.vue | head -20`

记下输出中负责「下载/预览文件」的函数名与行号，Step 5 要在那里插分支。

- [ ] **Step 4: 加工具函数与常量**

在 `frontend/src/views/EmbedChat.vue` 的 `<script setup>` 内、其它工具函数附近插入：

```ts
// ---------------------------------------------------------------------------
// 微信小程序宿主适配
// ---------------------------------------------------------------------------
// 小程序 web-view 内不能触发 <a download>（会被微信拦截），
// 且 H5 → 小程序的唯一【即时】通道是 wx.miniProgram.*：
// wx.miniProgram 的 postMessage 只在后退/组件销毁/分享/复制链接时批量触发，
// 不具备实时性，因此本文件不得用它做实时通知。
const MINIPROGRAM_FILE_PAGE = '/pages/file/file'
const MINIPROGRAM_CHAT_PAGE = '/pages/chat/chat'
const MINIPROGRAM_NO_AGENT_HINT = '尚未开放智能体，请联系管理员'

/** 是否运行在微信小程序 web-view 内 */
const isMiniprogramHost = (): boolean => {
  if (typeof window === 'undefined') return false
  const env = (window as any).__wxjs_environment
  if (env === 'miniprogram') return true
  return /miniProgram/i.test(navigator.userAgent || '')
}

/** 交给小程序原生页打开文件；返回 true 表示已接管 */
const openFileInMiniapp = (url: string): boolean => {
  const wx = (window as any).wx
  if (!isMiniprogramHost() || !wx?.miniProgram?.navigateTo || !url) return false
  wx.miniProgram.navigateTo({
    url: `${MINIPROGRAM_FILE_PAGE}?url=${encodeURIComponent(url)}`,
  })
  return true
}

/** 让小程序重新签票并回到聊天页；返回 true 表示已接管 */
const relaunchMiniappChat = (instanceId?: string): boolean => {
  const wx = (window as any).wx
  if (!isMiniprogramHost() || !wx?.miniProgram?.reLaunch) return false
  const query = instanceId ? `?instance_id=${encodeURIComponent(instanceId)}` : ''
  wx.miniProgram.reLaunch({ url: `${MINIPROGRAM_CHAT_PAGE}${query}` })
  return true
}
```

- [ ] **Step 5: 在下载/预览路径插入小程序分支**

在 Step 3 定位到的函数里，**在触发 `createElement('a')` / `download` 之前**插入：

```ts
    // 小程序 web-view 内 <a download> 会被微信拦截，改交原生文件页处理
    if (openFileInMiniapp(downloadUrl)) {
      return
    }
```

（`downloadUrl` 用该函数内实际持有的下载地址变量名。）

- [ ] **Step 6: 在凭证失败路径插入重新签票**

在 ticket 兑换失败的处理分支（`ticketExchangeFailureReason` 附近）插入：

```ts
    // 小程序宿主：凭证失效/未拿到时，让小程序重新签票回聊天页，避免停在白屏
    if (relaunchMiniappChat(config.instanceId)) {
      return
    }
```

（用文件内**实际存在**的实例标识——实测是 `config.instanceId`，**没有** `currentInstanceId` 这个 ref。回退成空字符串会丢掉 spec §9.4 的「接回原会话」。）

- [ ] **Step 7: 无可用智能体兜底文案**

⚠️ **`EmbedChat.vue` 里并没有「已授权智能体列表为空」的现成分支**——真实落点在子组件（`ExpertCascadeMenu.vue` 的「暂无系统专家」、`ChatSettings.vue` 的「暂无可用智能体」选项），`EmbedChat.vue` 只是把 `allowedAgents` 当 prop 传下去。所以这里**需要新增**一个小程序宿主专属分支，并按 spec §9「改动局限在小程序宿主分支内」的要求 **gate 在小程序宿主**：

```vue
      <div
        v-if="isMiniprogramHost() && !isLoadingAgents && allowedAgents.length === 0"
        class="px-4 py-3"
      >
        <p class="text-sm text-slate-500">{{ MINIPROGRAM_NO_AGENT_HINT }}</p>
      </div>
```

放置位置：`messages.length === 0` 的 WelcomeDashboard 空状态**附近**（例如其正上方）。

三条要求：
1. `isLoadingAgents` 若文件里没有同名变量，就换成文件里**实际存在**的加载标志——**不要新造状态**；
2. 样式沿用文件已有的 Tailwind 体系（`class` 可按实际微调）；
3. 加完这个渲染点，`MINIPROGRAM_NO_AGENT_HINT` 才算真正被使用——否则会报 TS6133「declared but never read」。

- [ ] **Step 8: 运行契约测试，确认通过**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_embedchat_miniprogram_host_contract.py -v`

Expected: 6 条全部 PASS

- [ ] **Step 9: 前端类型检查**

Run: `NODE_OPTIONS=--max-old-space-size=6144 npx vue-tsc -b --force`

⚠️ **不要用 `npx vue-tsc --noEmit`**：本仓库 `frontend/tsconfig.json` 是 solution 型（`"files": []` + `references`），不带 `-b` 时**不检查任何文件**、静默 `exit 0`——那是**假通过**。基线：全仓既有 **79 条** error TS（与本功能无关，实测 `-b` 与 `-p tsconfig.app.json` 均为 79），**验收标准是「不新增」**（总数 == 79），不是「0 错误」。不加 `--max-old-space-size` 会 OOM（`Abort trap: 6`）。

Expected: 无新增类型错误（与改动前对比）

- [ ] **Step 10: 检查点（不提交）**

汇报：EmbedChat 的四处改动（工具函数、下载分支、凭证自救、空状态文案）、契约测试与类型检查结果。

---

### Task 7: 管理端「微信绑定」视图

**Files:**
- Modify: `app/api/portal/endpoints/management.py`
- Modify: `frontend/src/views/Users.vue`
- Create: `tests/api/portal/test_wechat_bindings.py`
- Create: `tests/frontend/test_users_wechat_binding_contract.py`

**背景（spec §7.6）与既有模式：**

- `management.router` 整组已挂 `require_api_key`（`app/api/portal/api.py:43` 以 `/management` 前缀挂到 `/api/portal`），所以新接口的完整路径是 `/api/portal/management/wechat-bindings`；
- 列表接口返回**裸 dict** `{total, page, size, items}`（不是 `StandardResponse`），与 `GET /users` 保持一致；
- `require_permission` 对 `role == "admin"` **直接放行**（`app/core/dependencies.py:147`），所以 `admin_api_key` 能过、`valid_api_key`（普通用户）会被拒；
- 前端用 `axios`（`import axios from "../utils/axios"`）+ 完整路径，且已有 `copyToClipboard()` 工具可直接复用。

- [ ] **Step 1: 写失败的后端测试**

创建 `tests/api/portal/test_wechat_bindings.py`：

```python
"""管理端「微信绑定」视图接口测试。

前置条件：已导入 V170/V171（MySQL）或 V71/V72（PG）。
"""

import pytest
from sqlalchemy import select

from app.models.user import User
from app.models.wechat_binding import WechatBinding

BINDINGS_URL = "/api/portal/management/wechat-bindings"
USERS_URL = "/api/portal/management/users"

OPENID = "oMgmtTestOpenid000000000001"
UNIONID = "uMgmtTestUnionid0000000001"
APPID = "wx1ca87185956d0071"


@pytest.fixture
async def bound_user(db_session):
    """给 seed 出来的 test_user 造一条微信绑定（get-or-create，保证可重复运行）。"""
    user = (
        await db_session.execute(select(User).where(User.user_name == "test_user"))
    ).scalar_one()

    binding = WechatBinding(user_id=user.id, appid=APPID, openid=OPENID, unionid=UNIONID)
    db_session.add(binding)
    await db_session.commit()
    await db_session.refresh(binding)
    return user, binding


async def test_list_requires_permission(client, valid_api_key):
    """普通用户没有 menu:system:users，不得看到绑定列表。"""
    resp = await client.get(BINDINGS_URL, headers={"X-API-Key": valid_api_key})
    assert resp.status_code in (401, 403), resp.text


async def test_list_masks_openid_and_unionid(client, admin_api_key, bound_user):
    resp = await client.get(BINDINGS_URL, headers={"X-API-Key": admin_api_key})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1

    row = next(r for r in body["items"] if r["user_id"] == bound_user[0].id)

    # 列表不得出现完整值
    assert OPENID not in resp.text, "列表接口不得下发完整 openid"
    assert UNIONID not in resp.text, "列表接口不得下发完整 unionid"

    # 脱敏形态：首 6 + **** + 尾 4
    assert row["openid_masked"] == f"{OPENID[:6]}****{OPENID[-4:]}"
    assert row["user_name"] == "test_user"
    assert row["appid"] == APPID


async def test_raw_identity_requires_edit_level_permission(
    client, valid_api_key, admin_api_key, bound_user
):
    """明文取用必须比列表更严（element:user:edit）。"""
    _, binding = bound_user
    url = f"{BINDINGS_URL}/{binding.id}/identity"

    denied = await client.get(url, headers={"X-API-Key": valid_api_key})
    assert denied.status_code in (401, 403), denied.text
    assert OPENID not in denied.text

    allowed = await client.get(url, headers={"X-API-Key": admin_api_key})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["openid"] == OPENID
    assert allowed.json()["unionid"] == UNIONID


async def test_raw_identity_404_for_unknown_binding(client, admin_api_key):
    resp = await client.get(f"{BINDINGS_URL}/999999999/identity", headers={"X-API-Key": admin_api_key})
    assert resp.status_code == 404, resp.text


async def test_user_list_marks_wechat_bound(client, admin_api_key, bound_user):
    """用户列表要能一眼看出「这人是微端用户」。"""
    user, _ = bound_user

    resp = await client.get(
        USERS_URL,
        params={"search": user.user_name},
        headers={"X-API-Key": admin_api_key},
    )

    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json()["items"] if r["id"] == user.id)
    assert row["wechat_bound"] is True


async def test_user_list_marks_unbound_as_false(client, admin_api_key):
    """没有绑定的账号必须是 False——否则标识失去意义。"""
    resp = await client.get(
        USERS_URL, params={"search": "test_admin"}, headers={"X-API-Key": admin_api_key}
    )

    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json()["items"] if r["user_name"] == "test_admin")
    assert row["wechat_bound"] is False
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/api/portal/test_wechat_bindings.py -v`

Expected: 全部 FAIL（404 —— 路由不存在；`test_user_list_marks_wechat_bound` 会因缺 `wechat_bound` 键抛 `KeyError`）

- [ ] **Step 3: 实现后端**

在 `app/api/portal/endpoints/management.py` 的 `list_users` **之后**插入：

```python
# ---------------------------------------------------------------------------
# 微信绑定（小程序微端，见 spec §7.6）
# ---------------------------------------------------------------------------

def mask_openid(value: Optional[str]) -> Optional[str]:
    """openid/unionid 脱敏：保留首 6 尾 4，中间以 **** 代替。

    它不是凭证（拿它无法登录），但能关联到具体微信用户，列表页没必要裸奔；
    需要明文排查时走 /wechat-bindings/{id}/identity。
    """
    if not value:
        return value
    if len(value) <= 12:
        return value[:3] + "****"
    return f"{value[:6]}****{value[-4:]}"


@router.get("/wechat-bindings")
async def list_wechat_bindings(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    search: Optional[str] = None,
    appid: Optional[str] = None,
    admin: dict = Depends(require_permission("menu", "menu:system:users")),
    db: AsyncSession = Depends(get_db_session),
):
    """微信身份绑定记录列表。

    一行 = 一条绑定记录，而不是一行一个用户：同一账号将来可能挂多个微信身份
    （多小程序 / 网站应用），按绑定行展示才不会丢信息。
    """
    from app.models.wechat_binding import WechatBinding

    stmt = (
        select(WechatBinding, User)
        .join(User, User.id == WechatBinding.user_id)
        .order_by(desc(WechatBinding.last_login_at), desc(WechatBinding.id))
    )

    if appid:
        stmt = stmt.where(WechatBinding.appid == appid)
    if search:
        stmt = stmt.where(
            (User.user_name.like(f"%{search}%")) | (User.real_name.like(f"%{search}%"))
        )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar()

    rows = (await db.execute(stmt.offset((page - 1) * size).limit(size))).all()

    items = []
    for binding, user in rows:
        items.append({
            "id": binding.id,
            "user_id": user.id,
            "user_name": user.user_name,
            "real_name": user.real_name,
            "appid": binding.appid,
            "openid_masked": mask_openid(binding.openid),
            "unionid_masked": mask_openid(binding.unionid),
            "created_at": binding.created_at.strftime("%Y-%m-%d %H:%M:%S") if binding.created_at else None,
            "last_login_at": binding.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if binding.last_login_at else None,
        })

    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/wechat-bindings/{binding_id}/identity")
async def get_wechat_binding_identity(
    binding_id: int,
    admin: dict = Depends(require_permission("element", "element:user:edit")),
    db: AsyncSession = Depends(get_db_session),
):
    """取单条绑定的完整 openid/unionid，供对照云函数日志排查。

    单独成接口、且权限升到编辑级，而不是给列表加 include_raw 参数——
    后者一次请求就把整页明文全下发，脱敏等于白做。
    """
    from app.models.wechat_binding import WechatBinding

    binding = await db.get(WechatBinding, binding_id)
    if binding is None:
        raise HTTPException(status_code=404, detail="绑定记录不存在")

    logger.info(
        "管理员读取微信绑定明文身份: binding_id=%s user_id=%s operator=%s",
        binding_id, binding.user_id, admin.get("user_name"),
    )
    return {"openid": binding.openid, "unionid": binding.unionid}
```

- [ ] **Step 4: 给 `list_users` 加 `wechat_bound`**

在 `list_users` 里，`rows = (await db.execute(stmt)).scalars().all()` **之后**、`items = []` **之前**插入（一次 `IN` 查询，避免逐行 N+1）：

```python
    # 本页用户的微信绑定情况：一次 IN 查询，不要逐行查
    page_user_ids = [row.id for row in rows]
    bound_user_ids: set = set()
    if page_user_ids:
        from app.models.wechat_binding import WechatBinding

        bound_rows = await db.execute(
            select(WechatBinding.user_id)
            .where(WechatBinding.user_id.in_(page_user_ids))
            .distinct()
        )
        bound_user_ids = {r[0] for r in bound_rows.all()}
```

再在 `items.append({...})` 的字典里加一行：

```python
            "wechat_bound": row.id in bound_user_ids,
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `pytest tests/api/portal/test_wechat_bindings.py -v`

Expected: 6 条全部 PASS

- [ ] **Step 6: 写失败的前端契约测试**

创建 `tests/frontend/test_users_wechat_binding_contract.py`：

```python
"""用户管理页「微信绑定」视图契约测试。

只做源码静态断言（沿用 tests/frontend 既有风格），不启动浏览器。
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/views/Users.vue"


def test_view_exists():
    assert VIEW.exists(), f"缺少视图文件: {VIEW}"


def test_has_wechat_binding_tab():
    view = VIEW.read_text(encoding="utf-8")

    assert "微信绑定" in view
    assert "'wechat'" in view


def test_active_view_type_includes_wechat():
    """类型必须同步扩充：漏改会让 switchView 分支写不进去，vue-tsc 也会报错。"""
    view = VIEW.read_text(encoding="utf-8")

    assert '"list" | "review" | "wechat"' in view


def test_binding_list_renders_only_masked_fields():
    view = VIEW.read_text(encoding="utf-8")

    assert "openid_masked" in view
    assert "unionid_masked" in view
    # 列表页不得直接渲染未脱敏字段。
    # ⚠️ 必须用负向前瞻：`"row.openid"` 是 `"row.openid_masked"` 的**前缀**，
    # 写成 `not in` 会与本任务自己的模板互斥、造成假失败。
    assert not re.search(r"row\.openid(?!_masked)", view)
    assert not re.search(r"row\.unionid(?!_masked)", view)


def test_raw_identity_fetched_lazily_for_copy():
    view = VIEW.read_text(encoding="utf-8")

    assert "/identity" in view
    assert "copyBindingIdentity" in view


def test_user_list_shows_wechat_marker():
    view = VIEW.read_text(encoding="utf-8")

    assert "wechat_bound" in view


def test_switch_view_restores_status_filter_for_wechat_tab():
    """离开用户列表时必须还原 statusFilter，否则会把 status=2 带到绑定视图。"""
    view = VIEW.read_text(encoding="utf-8")

    assert 'view === "wechat"' in view
```

- [ ] **Step 7: 运行契约测试，确认失败**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_users_wechat_binding_contract.py -v`

Expected: `test_view_exists` PASS；其余 FAIL

- [ ] **Step 8: 改前端（7 处）**

**(1) tab 数组**（`Users.vue:143` 附近）加第三项：

```js
        v-for="tab in [
          { id: 'list', label: '用户列表' },
          { id: 'review', label: '待审核' },
          { id: 'wechat', label: '微信绑定' },
        ]"
```

**(2) 模板里的类型断言**（同一处 `@click`）：

```js
        @click="switchView(tab.id as 'list' | 'review' | 'wechat')"
```

**(3) `activeView` 类型**（`:2415`）：

```js
const activeView = ref<"list" | "review" | "wechat">("list");
```

**(4) `switchView`**（`:2492`）整体替换为：

```js
const switchView = async (view: "list" | "review" | "wechat") => {
  if (activeView.value === view) return;
  activeView.value = view;
  closeMenus();
  clearSelection();
  page.value = 1;
  if (view === "review") {
    // 待审核视图固定按 status=2 拉取；离开时还原，避免污染主列表筛选
    statusFilter.value = "2";
    await Promise.all([fetchUsers(), fetchPendingCount()]);
  } else if (view === "wechat") {
    // 同样要还原 statusFilter，否则会把 status=2 带到绑定视图
    statusFilter.value = "";
    bindingPage.value = 1;
    await fetchBindings();
  } else {
    statusFilter.value = "";
    await fetchUsers();
  }
};
```

**(5) 绑定视图的状态与请求函数**，紧接在 `fetchUsers` 定义**之后**插入：

```js
// --- 微信绑定视图（spec §7.6）---
// 一行 = 一条绑定记录：同一账号将来可能挂多个微信身份，不能按用户聚合。
const bindings = ref<any[]>([]);
const bindingPage = ref(1);
const bindingSize = ref(15);
const bindingTotal = ref(0);
const bindingTotalPages = ref(0);
const bindingSearch = ref("");
const bindingLoading = ref(false);

const fetchBindings = async () => {
  bindingLoading.value = true;
  try {
    const params: any = { page: bindingPage.value, size: bindingSize.value };
    if (bindingSearch.value) params.search = bindingSearch.value;
    const response = await axios.get("/api/portal/management/wechat-bindings", { params });
    bindings.value = response.data.items || [];
    bindingTotal.value = response.data.total || 0;
    bindingTotalPages.value = Math.ceil(bindingTotal.value / bindingSize.value);
  } catch (e: any) {
    showToast("获取微信绑定列表失败", "error");
  } finally {
    bindingLoading.value = false;
  }
};

/** 取完整 openid 并复制：明文单独走接口，避免整页明文下发 */
const copyBindingIdentity = async (row: any) => {
  try {
    const response = await axios.get(
      `/api/portal/management/wechat-bindings/${row.id}/identity`
    );
    const ok = await copyToClipboard(response.data?.openid || "");
    showToast(ok ? "已复制完整 openid" : "复制失败", ok ? "success" : "error");
  } catch (e: any) {
    showToast("读取完整 openid 失败", "error");
  }
};
```

（`axios` 与 `copyToClipboard` 都已在文件顶部导入，无需新增 import。）

**(6) 绑定视图内容区**，插入在 `<template v-if="activeView === 'list'">`（`:313`）**之前**：

```vue
    <!-- 微信绑定视图：一行 = 一条绑定记录（同一账号将来可能挂多个微信身份） -->
    <template v-if="activeView === 'wechat'">
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model="bindingSearch"
          type="text"
          placeholder="搜索用户名 / 姓名"
          class="w-64 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:ring-2 focus:ring-primary/30"
          @keyup.enter="bindingPage = 1; fetchBindings()"
        />
        <button
          type="button"
          class="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
          @click="bindingPage = 1; fetchBindings()"
        >查询</button>
      </div>

      <div class="bg-white border border-gray-200 shadow-sm rounded-lg">
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">用户</th>
                <th class="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">来源 AppID</th>
                <th class="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">openid</th>
                <th class="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">unionid</th>
                <th class="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">绑定时间</th>
                <th class="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">最后登录</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="row in bindings" :key="row.id" class="hover:bg-gray-50/80">
                <td class="px-5 py-4 whitespace-nowrap">
                  <div class="text-sm font-medium text-gray-900">{{ row.user_name }}</div>
                  <div class="text-xs text-gray-500">#{{ row.user_id }}</div>
                </td>
                <td class="px-5 py-4 whitespace-nowrap text-sm text-gray-700">{{ row.appid }}</td>
                <td class="px-5 py-4 whitespace-nowrap text-sm text-gray-700">
                  <span class="font-mono">{{ row.openid_masked }}</span>
                  <button
                    type="button"
                    class="ml-2 text-xs text-primary hover:underline"
                    title="复制完整 openid（会记入日志）"
                    @click="copyBindingIdentity(row)"
                  >复制完整值</button>
                </td>
                <td class="px-5 py-4 whitespace-nowrap text-sm text-gray-700">
                  <span class="font-mono">{{ row.unionid_masked || '—' }}</span>
                </td>
                <td class="px-5 py-4 whitespace-nowrap text-sm text-gray-500">{{ row.created_at || '—' }}</td>
                <td class="px-5 py-4 whitespace-nowrap text-sm text-gray-500">{{ row.last_login_at || '—' }}</td>
              </tr>
              <tr v-if="!bindingLoading && bindings.length === 0">
                <td colspan="6" class="px-5 py-10 text-center text-sm text-gray-500">
                  暂无微信绑定记录
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex items-center justify-between border-t border-gray-200 px-5 py-3">
          <div class="text-sm text-gray-600">
            共 {{ bindingTotal }} 条，第 {{ bindingPage }}/{{ bindingTotalPages || 1 }} 页
          </div>
          <div class="flex gap-2">
            <button
              type="button"
              class="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              :disabled="bindingPage <= 1"
              @click="bindingPage > 1 && (bindingPage--, fetchBindings())"
            >上一页</button>
            <button
              type="button"
              class="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              :disabled="bindingPage >= bindingTotalPages"
              @click="bindingPage < bindingTotalPages && (bindingPage++, fetchBindings())"
            >下一页</button>
          </div>
        </div>
      </div>
    </template>
```

**(7) 用户列表加「微信」标识**，在用户列 `<div class="flex items-center gap-1.5 min-w-0">`（`:397` 附近）**之后**插入：

```vue
                      <span
                        v-if="user.wechat_bound"
                        class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 bg-emerald-50"
                        title="该账号已绑定微信（小程序微端）"
                      >微信</span>
```

- [ ] **Step 9: 运行契约测试与类型检查**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_users_wechat_binding_contract.py -v`

Expected: 7 条全部 PASS

Run: `NODE_OPTIONS=--max-old-space-size=6144 npx vue-tsc -b --force`

⚠️ **不要用 `npx vue-tsc --noEmit`**：本仓库 `frontend/tsconfig.json` 是 solution 型（`"files": []` + `references`），不带 `-b` 时**不检查任何文件**、静默 `exit 0`——那是**假通过**。基线：全仓既有 **79 条** error TS（与本功能无关，实测 `-b` 与 `-p tsconfig.app.json` 均为 79），**验收标准是「不新增」**（总数 == 79），不是「0 错误」。不加 `--max-old-space-size` 会 OOM（`Abort trap: 6`）。

Expected: 无新增类型错误。**若报 `activeView` / `switchView` 类型不匹配，说明 Step 8 的 (3)(4) 漏改。**

- [ ] **Step 10: 检查点（不提交）**

汇报：后端两个接口与 `wechat_bound` 字段、前端 7 处改动、6+7 条测试通过输出、`vue-tsc -b` 的错误数（应为 **79**，与基线持平）。

---

### Task 8: 登记测试清单并做整体回归

**Files:**
- Modify: `tests/CHECKLIST.md`

- [ ] **Step 1: 读现有清单格式**

Run: `tail -40 tests/CHECKLIST.md`

按文件的既有格式追加，不要自行发明格式。

- [ ] **Step 2: 追加本次新增测试条目**

在 `tests/CHECKLIST.md` 中按既有格式登记：

```markdown
- [ ] 小程序微端迁移契约：`pytest tests/test_miniprogram_migrations.py -v`
- [ ] 小程序微端服务层：`pytest tests/services/test_wechat_miniprogram_service.py -v`
- [ ] 小程序微端接口：`pytest tests/api/v1/test_miniprogram_session.py -v`
- [ ] 管理端微信绑定接口：`pytest tests/api/portal/test_wechat_bindings.py -v`
- [ ] EmbedChat 小程序宿主契约：`pytest --confcutdir=tests/frontend tests/frontend/test_embedchat_miniprogram_host_contract.py -v`
- [ ] 用户管理页微信绑定契约：`pytest --confcutdir=tests/frontend tests/frontend/test_users_wechat_binding_contract.py -v`
```

- [ ] **Step 3: 全量回归**

Run: `pytest tests/test_miniprogram_migrations.py tests/services/test_wechat_miniprogram_service.py tests/api/v1/test_miniprogram_session.py tests/api/portal/test_wechat_bindings.py -v`

Expected: 全部 PASS

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_embedchat_miniprogram_host_contract.py tests/frontend/test_users_wechat_binding_contract.py -v`

Expected: 全部 PASS

- [ ] **Step 4: 确认没有误改 EmbedService**

Run: `git diff --stat app/services/embed_service.py app/core/v1_api_access.py frontend/src/views/EmbedChat.vue frontend/src/views/Users.vue app/api/v1/endpoints/embed.py app/api/portal/endpoints/management.py`

Expected: `embed_service.py` 与 `v1_api_access.py` **不出现在差异里**（本设计要求它们零改动）；其余四个文件有改动是预期的。

- [ ] **Step 5: 检查点（不提交）**

汇报：清单改动、全量回归结果、`git diff --stat` 输出，并提醒用户：
1. 迁移文件已就绪，请在控制台手工导入（MySQL: V170/V171；PG: V71/V72）；
2. 后台需人工配置：`miniprogram_enabled=true`、建 `miniprogram_gateway` 账号并只授「代他人签发嵌入凭证」、给「小程序用户」角色勾可见智能体；
3. 小程序侧实施见配套计划。

---

## 自检记录

**1. Spec 覆盖检查**

| Spec 章节 | 对应任务 |
|---|---|
| §6.1 绑定表 | Task 1、Task 3 |
| §6.2 账号字段 | Task 4（建号路径） |
| §7.1 接口（含显式权限、前置于建号） | Task 5 |
| §7.2 服务 | Task 4 |
| §7.3 配置/凭证/开关/熔断 | Task 2（开关与角色种子）、Task 5（开关校验、熔断调用）、Task 4（熔断实现） |
| §7.4 配置分层 | 小程序侧计划（环境变量） |
| §7.5 迁移 | Task 1、Task 2 |
| §9 EmbedChat 适配 | Task 6 |
| §11 测试计划 | Task 1/3/4/5/6/7 |
| §7.6 管理端展示 | Task 7 |
| §13 上线检查清单 | Task 8 Step 5（人工项） |

**已知缺口（有意留白，非遗漏）**：

- **小程序工程侧全部内容**不在本计划（在仓库外），见配套计划 `2026-10-15-miniprogram-miniapp-side.md`。
- **§6.4 的「设置登录名 + 密码」**为已确认的下一阶段，本期不实现。

**2. 占位符扫描**：本计划所有代码块均为可直接落盘的完整内容；命令均带预期输出；无 TBD/TODO/「类似 Task N」表述。

**3. 类型一致性检查**：

- `resolve_or_create_user(openid, appid, db, unionid=None)` 在 Task 4 定义、Task 5 以内层 `db` 传入调用，参数名一致；
- 返回键 `user_id` / `user_name` / `is_new` 与 Task 5 的 `MiniprogramIdentitySummary(**identity)` 字段一一对应；
- `derive_instance_id(openid)` 在 Task 4 定义、Task 5 调用，签名一致；
- `MINIPROGRAM_FILE_PAGE` / `MINIPROGRAM_CHAT_PAGE` / `MINIPROGRAM_NO_AGENT_HINT` 在 Task 6 Step 4 定义，Step 7 的模板与 Step 1 的断言字符串完全一致；
- `TICKET_TTL_SECONDS` 从 `app.services.embed_service` 导入（该常量在 `embed_service.py:14` 定义）。
- `mask_openid()` 在 Task 7 Step 3 定义、同任务内被 `list_wechat_bindings` 使用；`openid_masked` / `unionid_masked` 的字段名在「后端返回 → Step 6 契约断言 → Step 8 模板绑定」三处完全一致；
- `wechat_bound` 由 Task 7 Step 4 写入 `list_users` 返回，Step 6 契约测试与 Step 8 前端标识均按此名读取；
- 前端 `fetchBindings` 使用完整路径 `/api/portal/management/wechat-bindings`——与后端挂载链一致（`app/main.py:425` 的 `/api/portal` + `app/api/portal/api.py:43` 的 `/management`），漏掉 `/api/portal` 会在运行时报 404 而测试抓不住。

---

## 执行交接

计划已保存到 `docs/superpowers/plans/2026-10-15-miniprogram-platform-side.md`。小程序工程侧（仓库外）请另见 `2026-10-15-miniprogram-miniapp-side.md`。

**两种执行方式：**

1. **Subagent 驱动（推荐）** —— 每个任务派一个全新 subagent，任务之间我来审查，迭代快；
2. **本会话内联执行** —— 用 executing-plans 在本会话按批次执行，带检查点供你复核。

**选哪种？**
