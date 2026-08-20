"""get_all_tables_with_dataset 单查询合并重构的等价性测试。

重构前：逐数据集循环 select(MetaTable).where(dataset_id==...)
重构后：一次 select(MetaTable).where(dataset_id.in_(...)) + 内存分组
对外返回结构、分组语义、排序确定性保持不变。本测试用 mock 断言：
  - 只发起一次表查询（IN），不再逐数据集循环
  - 无表的数据集仍以空数组出现在结果中
  - columns 嵌套、表/数据集顺序与语义保持
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class _Col:
    def __init__(self, physical_name, term):
        self.physical_name = physical_name
        self.term = term


class _Table:
    def __init__(self, id, dataset_id, physical_name, term, columns=()):
        self.id = id
        self.dataset_id = dataset_id
        self.physical_name = physical_name
        self.term = term
        self.columns = columns


class _Dataset:
    def __init__(self, id, name, display_name):
        self.id = id
        self.name = name
        self.display_name = display_name


@pytest.mark.asyncio
async def test_get_all_tables_with_dataset_groups_single_query():
    from app.services.metadata_service import MetadataService

    ds1 = _Dataset(1, "hr_data", "HR 人员数据")
    ds2 = _Dataset(2, "fin_data", None)  # display_name 为 None -> 用 name 兜底
    ds3 = _Dataset(3, "no_table", "无表数据集")

    table1 = _Table(10, 1, "employees", "员工信息表", [
        _Col("id", "员工ID"),
        _Col("name", "姓名"),
    ])
    table2 = _Table(11, 1, "departments", "部门表", [])
    table3 = _Table(20, 2, "ledger", "总账表", [_Col("amount", "金额")])

    mock_db = AsyncMock()
    # id 顺序打乱，验证 order_by 语义下返回顺序按 (dataset_id, id) 稳定
    mock_db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(
        all=MagicMock(return_value=[table3, table1, table2]),
    )))

    with patch.object(
        MetadataService, "search_datasets",
        AsyncMock(return_value=[ds1, ds2, ds3]),
    ) as mock_search:
        res = await MetadataService.get_all_tables_with_dataset(
            mock_db, user_id=5, is_admin=False,
        )

    # 只执行一次表查询（IN 合并），不再逐数据集循环
    assert mock_db.execute.await_count == 1

    assert len(res) == 3
    assert res[0]["dataset_id"] == 1
    assert res[0]["dataset_name"] == "hr_data"
    assert res[0]["display_name"] == "HR 人员数据"
    assert [t["id"] for t in res[0]["tables"]] == [10, 11]
    assert res[0]["tables"][0]["term"] == "员工信息表"
    assert res[0]["tables"][0]["columns"] == [
        {"physical_name": "id", "term": "员工ID"},
        {"physical_name": "name", "term": "姓名"},
    ]

    # display_name 为空的兜底为 name
    assert res[1]["dataset_id"] == 2
    assert res[1]["display_name"] == "fin_data"
    assert [t["id"] for t in res[1]["tables"]] == [20]

    # 无表的数据集保留空数组
    assert res[2]["dataset_id"] == 3
    assert res[2]["tables"] == []

    # search_datasets 仍以原参数被调用（权限语义不变）
    mock_search.assert_awaited_once_with(
        mock_db,
        query=None,
        user_id=5,
        is_admin=False,
        status=1,
    )


@pytest.mark.asyncio
async def test_get_all_tables_with_dataset_no_datasets():
    """权限内无数据集时直接返回空列表，不触发任何表查询。"""
    from app.services.metadata_service import MetadataService

    mock_db = AsyncMock()
    with patch.object(MetadataService, "search_datasets", AsyncMock(return_value=[])):
        res = await MetadataService.get_all_tables_with_dataset(
            mock_db, user_id=5, is_admin=False,
        )

    assert res == []
    mock_db.execute.assert_not_awaited()