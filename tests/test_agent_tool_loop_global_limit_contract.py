from pathlib import Path

import pytest

from app.services.ai.runtime.tool_loop_detector import DEFAULT_GLOBAL_LIMIT

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[1]


def test_tool_loop_detector_default_global_limit_is_50():
    assert DEFAULT_GLOBAL_LIMIT == 50


@pytest.mark.parametrize("value", ["1", "50", "3600"])
def test_system_config_accepts_tool_loop_global_limit_in_range(value):
    from app.services.config_service import validate_config_update

    validate_config_update("agent_tool_loop_global_limit", value)


@pytest.mark.parametrize("value", ["", "0", "3601", "1.5", "abc", " 50", "50 "])
def test_system_config_rejects_invalid_tool_loop_global_limit(value):
    from app.services.config_service import validate_config_update

    with pytest.raises(ValueError, match="agent_tool_loop_global_limit"):
        validate_config_update("agent_tool_loop_global_limit", value)


def test_mysql_migration_seeds_agent_tool_loop_global_limit_at_50():
    source = (ROOT / "db-prod/V134-add-agent-tool-loop-global-limit.sql").read_text(
        encoding="utf-8"
    )

    assert "agent_tool_loop_global_limit" in source
    assert "'50'" in source
    assert "'agent'" in source
    assert "INSERT IGNORE" in source.upper()


def test_postgres_migration_seeds_agent_tool_loop_global_limit_idempotently():
    source = (ROOT / "db-prod-pg/V34-add-agent-tool-loop-global-limit.sql").read_text(
        encoding="utf-8"
    )

    assert "agent_tool_loop_global_limit" in source
    assert "'50'" in source
    assert "'agent'" in source
    assert "ON CONFLICT" in source.upper()


def test_system_config_places_tool_loop_limit_after_iterations_with_numeric_stepper():
    source = (ROOT / "frontend/src/views/SystemConfig.vue").read_text(encoding="utf-8")

    assert "agent_tool_loop_global_limit" in source
    order_start = source.index("if (category === 'agent')")
    order_block = source[source.index("const order = [", order_start):]
    assert order_block.index("agent_max_iterations") < order_block.index(
        "agent_tool_loop_global_limit"
    )
    assert "'agent_tool_loop_global_limit': '" in source

    start = source.index("v-else-if=\"item.key === 'agent_tool_loop_global_limit'\"")
    end = source.index("v-else-if=\"['audit_log_retention_days'", start)
    stepper = source[start:end]
    assert 'type="number"' in stepper
    assert 'min="1"' in stepper
    assert 'max="3600"' in stepper
    assert "agent_tool_loop_global_limit" not in source[
        source.index("['audit_log_retention_days'") : source.index(
            "['audit_log_retention_days'"
        )
        + 420
    ]
