import pytest

from app.services.ai import agent_service


pytestmark = pytest.mark.no_infrastructure


def test_client_prefix_history_length_ignores_ui_system_messages():
    messages = [
        {"role": "user", "content": "旧问题"},
        {"role": "assistant", "content": "旧回答"},
        {"role": "system", "content": "以上是历史会话，可以重置会话清除"},
        {"role": "user", "content": "新问题"},
    ]

    assert hasattr(agent_service, "_client_prefix_history_len")
    assert agent_service._client_prefix_history_len(messages) == 2
