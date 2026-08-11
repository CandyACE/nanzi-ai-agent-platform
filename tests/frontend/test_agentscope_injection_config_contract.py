"""Contract: AgentScope runtime injection toggles appear in System Config."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_CONFIG = (ROOT / "frontend/src/views/SystemConfig.vue").read_text(encoding="utf-8")
MYSQL_MIG = ROOT / "db-prod/V119-add_agentscope_injection_config.sql"
PG_MIG = ROOT / "db-prod-pg/V19-add_agentscope_injection_config.sql"


def test_system_config_exposes_agentscope_injection_toggles():
    assert "agentscope_inject_runtime_state" in SYSTEM_CONFIG
    assert "agentscope_inject_time_interval_hours" in SYSTEM_CONFIG
    assert "agentscope_inject_runtime_state'].includes" in SYSTEM_CONFIG
    # 时间间隔用数字控件
    assert "item.key === 'agentscope_inject_time_interval_hours'" in SYSTEM_CONFIG
    assert 'type="number"' in SYSTEM_CONFIG
    assert 'inputmode="decimal"' in SYSTEM_CONFIG
    # 左侧简短说明 + 右侧详细备注
    assert "configShortDescriptions" in SYSTEM_CONFIG
    assert "是否向 Agent 上下文注入运行时状态" in SYSTEM_CONFIG
    assert "运行时时间字段重复注入的最小间隔" in SYSTEM_CONFIG
    assert "configShortDescriptions[item.key] || item.description" in SYSTEM_CONFIG
    assert "mt-1.5 text-[11px] text-gray-500 leading-relaxed" in SYSTEM_CONFIG
    # general 栏与 platform_timezone 同组排序
    assert "'platform_timezone',\n      'agentscope_inject_runtime_state'" in SYSTEM_CONFIG or (
        "platform_timezone" in SYSTEM_CONFIG
        and "agentscope_inject_runtime_state" in SYSTEM_CONFIG
        and "category === 'general'" in SYSTEM_CONFIG
    )


def test_injection_config_migrations_seed_general_category():
    mysql = MYSQL_MIG.read_text(encoding="utf-8")
    pg = PG_MIG.read_text(encoding="utf-8")
    for text in (mysql, pg):
        assert "agentscope_inject_runtime_state" in text
        assert "agentscope_inject_time_interval_hours" in text
        assert "'general'" in text or '"general"' in text
        assert "'agent'" not in text.split("agentscope_inject_runtime_state", 1)[1][:200]
