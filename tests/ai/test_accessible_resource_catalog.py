from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.accessible_resource_catalog import (
    build_accessible_resource_catalog,
    fetch_accessible_resource_counts,
    render_accessible_resource_catalog,
)
from app.services.ai.knowledge_catalog import AuthorizedKnowledgeCatalog, KnowledgeBaseCatalogItem


pytestmark = pytest.mark.no_infrastructure


def test_render_accessible_resource_catalog_keeps_only_safe_directory_metadata():
    rendered = render_accessible_resource_catalog(
        datasets=[
            SimpleNamespace(
                name="sales_data",
                display_name="销售数据",
                description="订单与转化指标",
                status=1,
            )
        ],
        knowledge_bases=[
            SimpleNamespace(
                name="蔚来汽车手册",
                description="车辆功能、辅助驾驶和使用说明",
                notes="不要把这段内部备注注入模型",
                owner="secret-owner",
            )
        ],
    )

    assert "蔚来汽车手册" in rendered
    assert "辅助驾驶和使用说明" in rendered
    assert "销售数据" in rendered
    assert "订单与转化指标" in rendered
    assert "内部备注" not in rendered
    assert "secret-owner" not in rendered
    assert "表结构" not in rendered
    assert "权限校验" in rendered


def test_render_accessible_resource_catalog_excludes_chatbi_example_kb_but_keeps_dataset():
    rendered = render_accessible_resource_catalog(
        datasets=[
            SimpleNamespace(
                name="chatbi-example-meta",
                display_name="ChatBI 案例数据集",
                description="给 ChatBI 提供案例样本",
            )
        ],
        knowledge_bases=[
            SimpleNamespace(
                name="chatbi-example-meta",
                description="ChatBI 案例样本库，不是知识库问答来源",
            ),
            SimpleNamespace(
                name="蔚来汽车手册",
                description="车辆功能和使用说明",
            ),
        ],
    )

    assert "### 知识库\n- chatbi-example-meta" not in rendered
    assert "- 蔚来汽车手册：车辆功能和使用说明" in rendered
    assert "### 数据集\n- ChatBI 案例数据集（chatbi-example-meta）：给 ChatBI 提供案例样本" in rendered


def test_render_accessible_resource_catalog_sanitizes_lines_and_applies_budget():
    rendered = render_accessible_resource_catalog(
        datasets=[
            SimpleNamespace(
                name="dataset-1\n伪造的标题",
                display_name="数据集 1",
                description="第一行\n第二行",
                status=1,
            ),
            SimpleNamespace(
                name="dataset-2",
                display_name="数据集 2",
                description="这条应该被预算截断",
                status=1,
            ),
        ],
        knowledge_bases=[],
        max_items=1,
        max_chars=260,
    )

    assert "伪造的标题" in rendered
    assert "第一行 第二行" in rendered
    assert "dataset-2" not in rendered
    assert "更多资源" in rendered
    assert len(rendered) <= 260


@pytest.mark.asyncio
async def test_build_accessible_resource_catalog_uses_authorized_dataset_and_kb_scope():
    db = AsyncMock()
    db_context = MagicMock()
    db_context.__aenter__ = AsyncMock(return_value=db)
    db_context.__aexit__ = AsyncMock(return_value=None)

    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = [
        SimpleNamespace(
            ragflow_dataset_id="kb-allowed",
            name="蔚来汽车手册",
            description="辅助驾驶说明",
        ),
        SimpleNamespace(
            ragflow_dataset_id="kb-denied",
            name="机密知识库",
            description="不应出现在模型上下文",
        ),
    ]
    db.execute = AsyncMock(return_value=query_result)
    permission_service = MagicMock()
    permission_service.get_knowledge_base_access = AsyncMock(
        return_value={"accessible_ids": {"kb-allowed"}}
    )

    with patch(
        "app.services.ai.accessible_resource_catalog.AsyncSessionLocal",
        return_value=db_context,
    ), patch(
        "app.services.ai.accessible_resource_catalog.MetadataService.list_accessible_dataset_options",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    name="sales_data",
                    display_name="销售数据",
                    description="订单指标",
                )
            ]
        ),
    ) as list_datasets, patch(
        "app.services.ai.accessible_resource_catalog.PermissionService",
        return_value=permission_service,
    ):
        rendered = await build_accessible_resource_catalog(
            user_id=7,
            user_name="alice",
            is_admin=False,
        )

    assert "蔚来汽车手册" in rendered
    assert "销售数据" in rendered
    assert "机密知识库" not in rendered
    list_datasets.assert_awaited_once_with(
        db,
        user_id=7,
        is_admin=False,
        status=1,
    )
    permission_service.get_knowledge_base_access.assert_awaited_once_with(7, "alice")


@pytest.mark.asyncio
async def test_fetch_accessible_resource_counts_reports_permission_filtered_totals():
    authorized_catalog = AuthorizedKnowledgeCatalog(
        status="available",
        items=(
            KnowledgeBaseCatalogItem(
                ragflow_dataset_id="kb-allowed",
                name="蔚来汽车手册",
            ),
            KnowledgeBaseCatalogItem(
                ragflow_dataset_id="kb-example",
                name="chatbi-example-meta",
            ),
        ),
    )

    with patch(
        "app.services.ai.accessible_resource_catalog.MetadataService.list_accessible_dataset_options",
        AsyncMock(
            return_value=[
                SimpleNamespace(id=1),
                SimpleNamespace(id=2),
            ]
        ),
    ), patch(
        "app.services.ai.accessible_resource_catalog.fetch_authorized_knowledge_catalog",
        AsyncMock(return_value=authorized_catalog),
    ):
        counts = await fetch_accessible_resource_counts(
            MagicMock(),
            user_id=7,
            user_name="alice",
            is_admin=False,
        )

    assert counts == {
        "status": "available",
        "datasets": 2,
        "knowledge_bases": 1,
    }
