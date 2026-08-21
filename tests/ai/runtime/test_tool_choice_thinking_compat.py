from types import SimpleNamespace

import pytest
from agentscope.tool import ToolChoice

from app.services.ai.runners.chatbi.forced_tool_choice import (
    ForcedFirstToolChoiceModel,
)


pytestmark = pytest.mark.no_infrastructure


class RecordingModel:
    def __init__(self, *, thinking_enable: bool):
        self.parameters = SimpleNamespace(thinking_enable=thinking_enable)
        self.received_kwargs = None

    async def __call__(self, *args, **kwargs):
        self.received_kwargs = kwargs
        return "ok"


@pytest.mark.asyncio
async def test_thinking_model_does_not_receive_forced_tool_choice():
    model = RecordingModel(thinking_enable=True)
    choice = ToolChoice(mode="execute_sql_query")

    await ForcedFirstToolChoiceModel(model, choice)([])

    assert model.received_kwargs.get("tool_choice") is None


@pytest.mark.asyncio
async def test_non_thinking_model_keeps_forced_tool_choice():
    model = RecordingModel(thinking_enable=False)
    choice = ToolChoice(mode="execute_sql_query")

    await ForcedFirstToolChoiceModel(model, choice)([])

    assert model.received_kwargs["tool_choice"] is choice
