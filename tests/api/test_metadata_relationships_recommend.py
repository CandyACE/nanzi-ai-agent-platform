"""实体关系智能发现路由的契约测试。

路由: POST /datasets/{dataset_id}/relationships/recommend
行为:
  - 校验数据集存在（不存在返回 404）
  - 调用 MetadataService.export_dataset_yaml 生成 schema 上下文
  - 调用 MetadataGeneratorService.recommend_relationships(dataset_id, schema_yaml)
  - 返回 {"code":200,"message":"success","data": result}
不自动入库，仅返回建议 + 置信度供用户人工确认。

本测试不真正调用 LLM，而是 mock export_dataset_yaml 与 recommend_relationships，
断言路由的编排与返回结构。置信度字段由 service 层的 Pydantic 模型保证
（ge=0, le=1），此处单独验证模型约束。
"""
import pytest


class _ResultWrapper:
    """模拟数据集查询返回的 ORM 对象（仅需为真值即可）。"""
    def __init__(self, exists=True):
        self.id = 1
        self.exists = exists

    def __bool__(self):
        return self.exists


@pytest.mark.asyncio
async def test_recommend_relationships_success():
    from unittest.mock import AsyncMock, patch
    from app.api.portal.endpoints import metadata as endpoint_module
    from app.schemas.metadata import RelationshipRecommendRequest

    recommended = {
        "_trace_id": "rel-rec-test",
        "relationships": [
            {
                "source_table": "orders",
                "target_table": "order_items",
                "condition": "t1.order_id = t2.order_id",
                "relation_type": "one_to_many",
                "description": "一个订单包含多个订单明细",
                "confidence": 0.95,
                "source": "AI",
            },
            {
                "source_table": "customers",
                "target_table": "orders",
                "condition": "t1.id = t2.customer_id",
                "relation_type": "one_to_many",
                "description": "一个客户可以下单多次",
                "confidence": 0.88,
                "source": "AI",
            },
        ],
    }

    with patch.object(
        endpoint_module.MetadataService, "get_dataset_by_id",
        AsyncMock(return_value=_ResultWrapper(exists=True)),
    ) as mock_get_dataset, patch.object(
        endpoint_module.MetadataService, "get_relationships_by_dataset",
        AsyncMock(return_value=[]),
    ) as mock_get_relationships, patch.object(
        endpoint_module.MetadataService, "export_dataset_yaml",
        AsyncMock(return_value="schema_yaml_string"),
    ) as mock_export, patch.object(
        endpoint_module.MetadataGeneratorService, "recommend_relationships",
        AsyncMock(return_value=recommended),
    ) as mock_recommend:
        mock_conn = AsyncMock()
        mock_request = AsyncMock()
        mock_request.is_disconnected = AsyncMock(return_value=False)
        resp = await endpoint_module.recommend_relationships(
            dataset_id=1,
            request=mock_request,
            req=RelationshipRecommendRequest(),
            conn=mock_conn,
        )

    assert resp["code"] == 200
    assert resp["message"] == "success"
    assert resp["data"] == recommended
    assert resp["data"]["relationships"][0]["confidence"] == 0.95

    mock_get_dataset.assert_awaited_once()
    mock_get_relationships.assert_awaited_once_with(mock_conn, 1)
    mock_export.assert_awaited_once_with(mock_conn, 1, table_names=None)
    mock_recommend.assert_awaited_once()


@pytest.mark.asyncio
async def test_recommend_relationships_dataset_not_found():
    from unittest.mock import AsyncMock, patch
    from fastapi import HTTPException
    from app.api.portal.endpoints import metadata as endpoint_module
    from app.schemas.metadata import RelationshipRecommendRequest

    with patch.object(
        endpoint_module.MetadataService, "get_dataset_by_id",
        AsyncMock(return_value=None),
    ) as mock_get_dataset, patch.object(
        endpoint_module.MetadataService, "export_dataset_yaml", AsyncMock(),
    ) as mock_export, patch.object(
        endpoint_module.MetadataGeneratorService, "recommend_relationships", AsyncMock(),
    ) as mock_recommend:

        with pytest.raises(HTTPException) as exc:
            await endpoint_module.recommend_relationships(
                dataset_id=999,
                request=AsyncMock(),
                req=RelationshipRecommendRequest(),
                conn=AsyncMock(),
            )

    assert exc.value.status_code == 404
    mock_export.assert_not_awaited()
    mock_recommend.assert_not_awaited()


@pytest.mark.asyncio
async def test_recommend_relationships_cancels_generator_after_client_disconnect():
    """客户端断开后应取消模型生成协程，避免无人接收的后台任务继续消耗资源。"""
    import asyncio
    from unittest.mock import AsyncMock, patch
    from fastapi import HTTPException
    from app.api.portal.endpoints import metadata as endpoint_module
    from app.schemas.metadata import RelationshipRecommendRequest

    generator_cancelled = asyncio.Event()

    async def wait_until_cancelled(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            generator_cancelled.set()
            raise

    mock_request = AsyncMock()
    mock_request.is_disconnected = AsyncMock(return_value=True)

    with patch.object(
        endpoint_module.MetadataService, "get_dataset_by_id",
        AsyncMock(return_value=_ResultWrapper(exists=True)),
    ), patch.object(
        endpoint_module.MetadataService, "get_relationships_by_dataset",
        AsyncMock(return_value=[]),
    ), patch.object(
        endpoint_module.MetadataService, "export_dataset_yaml",
        AsyncMock(return_value="schema_yaml_string"),
    ), patch.object(
        endpoint_module.MetadataGeneratorService, "recommend_relationships",
        side_effect=wait_until_cancelled,
    ):
        with pytest.raises(HTTPException) as exc:
            await endpoint_module.recommend_relationships(
                dataset_id=1,
                request=mock_request,
                req=RelationshipRecommendRequest(),
                conn=AsyncMock(),
            )

    assert exc.value.status_code == 499
    assert generator_cancelled.is_set()


@pytest.mark.asyncio
async def test_metadata_recommendation_sse_emits_progress_and_completed_result():
    """SSE 适配器应按顺序输出 started、progress 和 completed 终态。"""
    from unittest.mock import AsyncMock
    from app.api.portal.endpoints import metadata as endpoint_module

    mock_request = AsyncMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    async def worker(progress_callback):
        await progress_callback({
            "phase": "scanning",
            "message": "正在扫描",
            "percent": 50,
            "remaining_units": 2,
        })
        return {"relationships": [], "_trace_id": "rel-rec-sse-test"}

    response = await endpoint_module._stream_metadata_recommendation(
        mock_request,
        dataset_id=1,
        recommendation_type="relationships",
        worker=worker,
    )
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    body = "".join(chunks)

    assert "event: started" in body
    assert "event: progress" in body
    assert '"remaining_units": 2' in body
    assert "event: completed" in body
    assert "rel-rec-sse-test" in body


@pytest.mark.asyncio
async def test_recommendation_schema_enforces_confidence_bounds():
    """RelationshipRecommendation 的 confidence 字段必须约束在 0~1 之间。"""
    from pydantic import ValidationError
    from app.services.metadata_generator import RelationshipRecommendation

    # 合法值
    ok = RelationshipRecommendation(
        source_table="orders",
        target_table="order_items",
        condition="t1.id = t2.order_id",
        relation_type="one_to_many",
        description="订单明细",
        confidence=0.9,
    )
    assert ok.confidence == 0.9

    # 越界 -> 校验失败
    with pytest.raises(ValidationError):
        RelationshipRecommendation(
            source_table="orders",
            target_table="order_items",
            condition="t1.id = t2.order_id",
            relation_type="one_to_many",
            description="订单明细",
            confidence=1.5,
        )
    with pytest.raises(ValidationError):
        RelationshipRecommendation(
            source_table="orders",
            target_table="order_items",
            condition="t1.id = t2.order_id",
            relation_type="one_to_many",
            description="订单明细",
            confidence=-0.1,
        )
