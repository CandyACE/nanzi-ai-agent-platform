import pytest
from pydantic import ValidationError


pytestmark = pytest.mark.no_infrastructure


def test_agent_version_toolcall_timeout_accepts_nullable_integer_seconds():
    from app.schemas.agent import AIAgentVersionBase

    assert AIAgentVersionBase(system_prompt="x", toolcall_timeout_seconds=None).toolcall_timeout_seconds is None
    assert AIAgentVersionBase(system_prompt="x", toolcall_timeout_seconds=1).toolcall_timeout_seconds == 1
    assert AIAgentVersionBase(system_prompt="x", toolcall_timeout_seconds=86400).toolcall_timeout_seconds == 86400


@pytest.mark.parametrize("value", [0, 86401, 1.5, True, "abc"])
def test_agent_version_toolcall_timeout_rejects_invalid_values(value):
    from app.schemas.agent import AIAgentVersionBase

    with pytest.raises(ValidationError):
        AIAgentVersionBase(system_prompt="x", toolcall_timeout_seconds=value)


def test_agent_version_manager_and_chat_config_carry_timeout_field():
    model_source = open("app/models/agent.py", encoding="utf-8").read()
    schema_source = open("app/schemas/agent.py", encoding="utf-8").read()
    manager_source = open("app/services/ai/agent_manager.py", encoding="utf-8").read()

    assert "toolcall_timeout_seconds = Column(Integer, nullable=True)" in model_source
    assert "toolcall_timeout_seconds" in schema_source
    assert '"toolcall_timeout_seconds" in data.model_fields_set' in manager_source
    assert "version.toolcall_timeout_seconds = data.toolcall_timeout_seconds" in manager_source
    assert "toolcall_timeout_seconds=getattr(version, \"toolcall_timeout_seconds\", None)" in manager_source


def test_agent_management_exposes_read_only_global_timeout_value():
    route_source = open("app/api/portal/endpoints/agents.py", encoding="utf-8").read()

    assert '@router.get("/toolcall-timeout")' in route_source
    assert 'require_permission("menu", "menu:agent_management")' in route_source
    assert "load_agent_max_toolcall_timeout" in route_source
