from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.agent_service import _enrich_terminal_error_chunk
from app.services.ai.error_response_service import ErrorPresentation


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_terminal_error_chunk_gets_friendly_content_and_error_detail():
    presentation = ErrorPresentation(
        content="这次处理没有完成，请稍后重试。",
        raw_error="upstream returned 503",
        ai_status="success",
    )

    with patch(
        "app.services.ai.agent_service.build_error_presentation",
        new=AsyncMock(return_value=presentation),
    ) as build_presentation:
        result = await _enrich_terminal_error_chunk(
            {
                "type": "error",
                "status": "error",
                "content": "Authorization: Bearer secret-token; upstream returned 503",
                "trace_id": "trace-1",
            },
            model_name="primary-model",
        )

    assert result == {
        "type": "error",
        "status": "error",
        "content": "这次处理没有完成，请稍后重试。",
        "error_detail": {
            "raw_error": "upstream returned 503",
            "ai_status": "success",
        },
        "trace_id": "trace-1",
    }
    build_presentation.assert_awaited_once()
    assert str(build_presentation.await_args.args[0]).startswith("Authorization:")


@pytest.mark.asyncio
async def test_terminal_error_chunk_preserves_source_exception_group_for_explainer():
    source_error = PermissionError("文件访问被拒绝：当前用户无权读取该路径 /")
    exception_group = ExceptionGroup(
        "One or more tool calls raised an exception",
        [source_error],
    )
    presentation = ErrorPresentation(
        content="文件访问被拒绝，请检查工具搜索路径。",
        raw_error="文件访问被拒绝：当前用户无权读取该路径 [internal path]",
        ai_status="disabled",
    )

    with patch(
        "app.services.ai.agent_service.build_error_presentation",
        new=AsyncMock(return_value=presentation),
    ) as build_presentation:
        result = await _enrich_terminal_error_chunk(
            {
                "type": "error",
                "status": "error",
                "content": str(exception_group),
            },
            source_exception=exception_group,
        )

    assert result["content"] == "文件访问被拒绝，请检查工具搜索路径。"
    assert build_presentation.await_args.args[0] is exception_group


@pytest.mark.asyncio
async def test_step_error_log_is_not_sent_to_error_explainer():
    with patch(
        "app.services.ai.agent_service.build_error_presentation",
        new=AsyncMock(),
    ) as build_presentation:
        chunk = {"type": "log", "status": "error", "title": "工具完成: Glob"}
        result = await _enrich_terminal_error_chunk(chunk)

    assert result is chunk
    build_presentation.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_error_detail_is_not_explained_again():
    chunk = {
        "type": "error",
        "status": "error",
        "content": "已经生成的友好提示",
        "error_detail": {"raw_error": "safe raw error", "ai_status": "fallback"},
    }

    with patch(
        "app.services.ai.agent_service.build_error_presentation",
        new=AsyncMock(),
    ) as build_presentation:
        result = await _enrich_terminal_error_chunk(chunk)

    assert result is chunk
    build_presentation.assert_not_awaited()
