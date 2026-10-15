"""契约：孤儿沙箱对账开关的键名、默认值、迁移与前端可见性保持一致。

本次审计发现沙箱销毁只有「进程内注册表」这一个真相来源：进程重启或技能集合令牌变化
后遗留的容器/Pod 永远不会被空闲回收（历史命名 ``as_ws_<user>`` 更是连"同名替换"都
蹭不到）。补上的对账需要一个可关闭的开关，因此这里钉住：
    * 代码常量、迁移 SQL、前端沙箱页三处键名一致；
    * 默认开启（单副本部署）；描述里必须写明多副本部署需关闭。
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[1]

MYSQL_MIGRATION = "db-prod/V169-add-sandbox-orphan-reconcile-config.sql"
PG_MIGRATION = "db-prod-pg/V70-add-sandbox-orphan-reconcile-config.sql"
CONFIG_KEY = "sandbox_orphan_reconcile"


def test_workspace_defines_the_reconcile_switch():
    source = (
        ROOT / "app/services/ai/runtime/agentscope/workspace.py"
    ).read_text(encoding="utf-8")

    assert f'SANDBOX_ORPHAN_RECONCILE_KEY = "{CONFIG_KEY}"' in source
    assert "reconcile_orphan_docker_workspaces" in source
    assert "reconcile_orphan_k8s_workspaces" in source
    # 对账必须挂在 reaper 循环上（否则没人调用）
    assert "await reconcile_orphan_docker_workspaces()" in source
    assert "await reconcile_orphan_k8s_workspaces()" in source
    # 执行期心跳：长命令不被空闲回收打断
    assert "_sandbox_activity_heartbeat" in source


def test_mysql_migration_seeds_reconcile_switch_idempotently():
    source = (ROOT / MYSQL_MIGRATION).read_text(encoding="utf-8")

    assert CONFIG_KEY in source
    assert "'true'" in source
    assert "'sandbox'" in source
    assert "ON DUPLICATE KEY UPDATE" in source.upper()
    assert "多副本" in source, "必须在管理台描述里写明多副本部署需关闭"


def test_postgres_migration_seeds_reconcile_switch_idempotently():
    source = (ROOT / PG_MIGRATION).read_text(encoding="utf-8")

    assert CONFIG_KEY in source
    assert "'true'" in source
    assert "'sandbox'" in source
    assert "ON CONFLICT" in source.upper()
    assert "多副本" in source, "必须在管理台描述里写明多副本部署需关闭"


def test_frontend_exposes_the_reconcile_switch_for_container_policies():
    source = (ROOT / "frontend/src/views/SystemConfig.vue").read_text(
        encoding="utf-8"
    )

    assert f"'{CONFIG_KEY}'" in source
    assert "containerCommonKeys" in source
