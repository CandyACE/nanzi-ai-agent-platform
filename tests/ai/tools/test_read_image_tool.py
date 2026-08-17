"""Tests for read_image tool."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.tools.registry import ToolRegistry
from app.services.ai.tools.system_executive_tools import read_image

pytestmark = pytest.mark.no_infrastructure


def test_read_image_tool_registered_and_read_only():
    from app.services.ai.grounding.models import EvidenceType
    from app.services.ai.runtime.agentscope.tools import (
        READ_ONLY_TOOL_NAMES,
        infer_runtime_permission_scope,
    )
    from app.services.ai.tools.registry import TOOL_EVIDENCE_TYPES

    assert "read_image" in ToolRegistry._registry
    assert "read_image" in READ_ONLY_TOOL_NAMES
    assert infer_runtime_permission_scope("read_image", "static") == "read"
    assert TOOL_EVIDENCE_TYPES.get("read_image") == frozenset({EvidenceType.USER_FILE})
    assert getattr(read_image, "name", "") == "read_image"


@pytest.mark.asyncio
async def test_read_image_blocks_path_traversal():
    result = await read_image.ainvoke({"path": "../../etc/passwd"})
    assert "安全拦截" in result or "路径越界" in result


@pytest.mark.asyncio
async def test_read_image_handles_nonexistent_file(tmp_path):
    fake_path = os.path.join("data", "non_existent_chart_9999.png")
    result = await read_image.ainvoke({"path": fake_path})
    assert "不存在" in result


@pytest.mark.asyncio
async def test_read_image_rejects_non_image_extension(tmp_path):
    data_dir = os.path.abspath("data")
    os.makedirs(data_dir, exist_ok=True)
    test_txt = os.path.join(data_dir, "test_doc_tmp.txt")
    with open(test_txt, "w", encoding="utf-8") as f:
        f.write("hello world")

    try:
        result = await read_image.ainvoke({"path": "data/test_doc_tmp.txt"})
        assert "不是支持的图片格式" in result
    finally:
        if os.path.exists(test_txt):
            os.remove(test_txt)


@pytest.mark.asyncio
async def test_read_image_warns_when_no_multimodal_model(tmp_path):
    data_dir = os.path.abspath("data")
    os.makedirs(data_dir, exist_ok=True)
    test_png = os.path.join(data_dir, "test_chart_tmp.png")
    with open(test_png, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01")

    try:
        with patch(
            "app.services.ai.multimodal_support.resolve_default_multimodal_model_name",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await read_image.ainvoke({"path": "data/test_chart_tmp.png"})
            assert "未配置或未启用默认多模态模型" in result
    finally:
        if os.path.exists(test_png):
            os.remove(test_png)


@pytest.mark.asyncio
async def test_read_image_successful_analysis(tmp_path):
    data_dir = os.path.abspath("data")
    os.makedirs(data_dir, exist_ok=True)
    test_png = os.path.join(data_dir, "test_sales_chart.png")
    with open(test_png, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01")

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=SimpleNamespace(content="该图片是一张柱状图，展示2026年Q1至Q4的营收增长趋势。")
    )

    try:
        with patch(
            "app.services.ai.multimodal_support.resolve_default_multimodal_model_name",
            new_callable=AsyncMock,
            return_value="Qwen-VL-Max",
        ), patch(
            "app.services.ai.config.AgentConfigProvider.get_configured_llm",
            new_callable=AsyncMock,
            return_value=mock_llm,
        ):
            result = await read_image.ainvoke(
                {
                    "path": "data/test_sales_chart.png",
                    "question": "分析图中的季度营收趋势",
                }
            )

            assert "图片解析成功" in result
            assert "Qwen-VL-Max" in result
            assert "柱状图" in result
            assert "营收增长趋势" in result

            # 验证向 LLM 传递的 Prompt 包含了用户的定制指令与 Data URL
            call_args = mock_llm.ainvoke.call_args[0][0]
            human_msg = call_args[0]
            assert "分析图中的季度营收趋势" in human_msg.content[0]["text"]
            assert human_msg.content[1]["type"] == "image_url"
            assert human_msg.content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    finally:
        if os.path.exists(test_png):
            os.remove(test_png)
