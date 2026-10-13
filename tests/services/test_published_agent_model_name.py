"""按智能体取「已发布版本」的编排模型名：查不到/异常一律返回空串。"""

import pytest


pytestmark = pytest.mark.no_infrastructure


class _Result:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _Session:
    def __init__(self, row):
        self._row = row

    async def execute(self, _stmt):
        return _Result(self._row)


async def test_returns_published_version_model_name():
    from app.services.ai.agent_manager import AgentManagerService

    assert await AgentManagerService.published_agent_model_name(
        _Session(("gpt-4o",)), "agent-1"
    ) == "gpt-4o"


async def test_returns_empty_when_no_version():
    from app.services.ai.agent_manager import AgentManagerService

    assert await AgentManagerService.published_agent_model_name(_Session(None), "agent-1") == ""


async def test_returns_empty_without_agent_id():
    from app.services.ai.agent_manager import AgentManagerService

    assert await AgentManagerService.published_agent_model_name(_Session(("gpt-4o",)), None) == ""


async def test_degrades_to_empty_on_failure():
    from app.services.ai.agent_manager import AgentManagerService

    class _Broken:
        async def execute(self, _stmt):
            raise RuntimeError("boom")

    assert await AgentManagerService.published_agent_model_name(_Broken(), "agent-1") == ""
