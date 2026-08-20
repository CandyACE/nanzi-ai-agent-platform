import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_batch_delete_tables_endpoint():
    from app.services.metadata_service import MetadataService

    mock_db = AsyncMock()

    with patch.object(MetadataService, "batch_delete_table_metadata", AsyncMock(return_value=2)) as mock_delete:
        from app.api.portal.endpoints.metadata import batch_delete_tables
        from app.schemas.metadata import BatchDeleteTablesRequest

        req = BatchDeleteTablesRequest(table_names=["orders", "order_items"])
        user = {"user_id": 1, "user_name": "admin"}

        res = await batch_delete_tables(dataset_id=10, req=req, conn=mock_db, user=user)

        assert res["deleted_count"] == 2
        assert "成功删除 2 张表" in res["message"]
        mock_delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_batch_delete_metrics_endpoint():
    from app.services.metadata_service import MetadataService

    mock_db = AsyncMock()

    with patch.object(MetadataService, "batch_delete_metrics", AsyncMock(return_value=3)) as mock_delete:
        from app.api.portal.endpoints.metadata import batch_delete_metrics
        from app.schemas.metadata import BatchDeleteMetricsRequest

        req = BatchDeleteMetricsRequest(metric_ids=[101, 102, 103])
        user = {"user_id": 1, "user_name": "admin"}

        res = await batch_delete_metrics(req=req, conn=mock_db, user=user)

        assert res["deleted_count"] == 3
        assert "成功删除 3 个指标" in res["message"]
        mock_delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_batch_delete_relationships_endpoint():
    from app.services.metadata_service import MetadataService

    mock_db = AsyncMock()

    with patch.object(MetadataService, "batch_delete_relationships", AsyncMock(return_value=1)) as mock_delete:
        from app.api.portal.endpoints.metadata import batch_delete_relationships
        from app.schemas.metadata import BatchDeleteRelationshipsRequest

        req = BatchDeleteRelationshipsRequest(relationship_ids=[201])
        user = {"user_id": 1, "user_name": "admin"}

        res = await batch_delete_relationships(req=req, conn=mock_db, user=user)

        assert res["deleted_count"] == 1
        assert "成功删除 1 条关联关系" in res["message"]
        mock_delete.assert_awaited_once()
