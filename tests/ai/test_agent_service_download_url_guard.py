import pytest

from app.core.context import AgentContext, set_agent_context


pytestmark = pytest.mark.no_infrastructure


def test_final_download_url_guard_keeps_tool_issued_url_and_removes_fake_url():
    from app.services.ai.agent_service import _filter_current_turn_download_urls

    trusted = "/api/v1/chat/generated-files/0123456789abcdef0123456789abcdef?token=trusted"
    fake = "/api/v1/chat/generated-files/abcdef0123456789abcdef0123456789?token=fake"
    set_agent_context(
        AgentContext(
            agent_id="agent",
            agent_name="Agent",
            published_download_urls=[trusted],
        )
    )

    filtered = _filter_current_turn_download_urls(
        f"真实文件：{trusted}\n假文件：{fake}\n普通链接：https://example.com/report.docx"
    )

    assert trusted in filtered
    assert fake not in filtered
    assert "下载地址未通过文件工具确认" in filtered
    assert "https://example.com/report.docx" in filtered
