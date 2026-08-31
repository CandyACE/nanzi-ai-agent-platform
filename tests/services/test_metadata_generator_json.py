"""元数据生成器结构化 JSON 输出的独立测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.metadata_generator import (
    MetadataGeneratorService,
    RelationshipRecommendationResult,
)


pytestmark = pytest.mark.no_infrastructure


def test_extract_json_handles_fence_and_braces_inside_string():
    """解析 Markdown JSON 代码块时，不应被字符串中的花括号干扰。"""
    raw = """模型说明：
```json
{"relationships": [{"description": "字段映射 {source_id} -> {target_id}"}]}
```
"""

    result = MetadataGeneratorService._extract_json(raw)

    assert result["relationships"][0]["description"] == (
        "字段映射 {source_id} -> {target_id}"
    )


def test_extract_json_does_not_return_nested_object_after_outer_truncation():
    """外层对象截断时，应报解析错误而不是错误返回内部对象。"""
    with pytest.raises(ValueError):
        MetadataGeneratorService._extract_json(
            '{"relationships": {"nested": "完整但不应被单独返回"}'
        )


@pytest.mark.asyncio
async def test_invoke_json_retries_after_truncated_output():
    """首次输出被截断时，应重试并返回第二次完整结果。"""
    llm = SimpleNamespace(
        model="test-model",
        ainvoke=AsyncMock(
            side_effect=[
                SimpleNamespace(
                    content='{"relationships": [{"description": "未闭合'
                ),
                SimpleNamespace(content='{"relationships": []}'),
            ]
        ),
    )

    result = await MetadataGeneratorService._invoke_json(
        llm,
        RelationshipRecommendationResult,
        "请返回结果。\n{format_instructions}",
        "Schema 定义如下：\n{}",
    )

    assert result == {"relationships": []}
    assert llm.ainvoke.await_count == 2
    retry_system_prompt = llm.ainvoke.await_args_list[1].args[0][0].content
    assert "结构化输出重试要求" in retry_system_prompt
