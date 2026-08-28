import pytest


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.parametrize("value", ["1", "120", "3600"])
def test_agent_tool_timeout_accepts_integer_seconds(value):
    from app.services.config_service import validate_config_update

    validate_config_update("agent_max_toolcall_timeout", value)


@pytest.mark.parametrize("value", ["", "0", "3601", "1.5", "abc", " 120", "120 "])
def test_agent_tool_timeout_rejects_non_integer_or_out_of_range_values(value):
    from app.services.config_service import validate_config_update

    with pytest.raises(ValueError, match="agent_max_toolcall_timeout"):
        validate_config_update("agent_max_toolcall_timeout", value)
