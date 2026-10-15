"""API 工具「HTTP 方法」清单一致性契约（静态源码断言）。

背景：同一条方法清单在仓库里曾经各说各话——
  * 表单创建/编辑下拉：GET/POST/PUT/DELETE（**少了 PATCH**）；
  * 列表筛选器：再加 PATCH/HEAD/OPTIONS（**多了运行时根本不支持的两个**）；
  * 运行时 ``GenericApiToolFactory._execute_request``：GET 特判 + POST/PUT/PATCH/DELETE，
    HEAD/OPTIONS 会直接返回 ``[Error] Unsupported method``。

后果：接口文档里极常见的 ``curl -X PATCH`` 在表单里**无处安放**；而筛选器里的
HEAD/OPTIONS 是永远筛不出结果的死选项。本契约把静态清单收敛到 ``utils/toolMethods.ts``
单一来源，并钉住它与运行时一致。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

METHODS_UTIL = Path("frontend/src/utils/toolMethods.ts")
REGISTRY = Path("frontend/src/components/system/ToolRegistry.vue")
GENERIC_API = Path("app/services/ai/tools/generic_api.py")


def _source(path: Path) -> str:
    if not path.exists():
        pytest.fail(f"缺少文件：{path}")
    return path.read_text(encoding="utf-8")


def _static_methods() -> list[str]:
    match = re.search(r"SUPPORTED_HTTP_METHODS\s*=\s*\[([^\]]*)\]", _source(METHODS_UTIL))
    assert match, "未找到 SUPPORTED_HTTP_METHODS 数组字面量"
    return [item.strip().strip("'\"").upper() for item in match.group(1).split(",") if item.strip()]


def test_methods_util_is_the_single_source():
    source = _source(METHODS_UTIL)
    assert "SUPPORTED_HTTP_METHODS" in source
    assert "isSupportedMethod" in source


def test_static_list_matches_runtime_support():
    """前端静态清单必须等于运行时真正支持的方法集合。"""
    frontend = _static_methods()

    runtime = _source(GENERIC_API)
    # 运行时把 GET 单独一条分支，其余四个走同一个 request 分支
    body_branch = re.search(r"method in \[([^\]]*)\]", runtime)
    assert body_branch, "未找到运行时的非 GET 方法分支"
    runtime_methods = [
        item.strip().strip("'\"").upper()
        for item in body_branch.group(1).split(",")
        if item.strip()
    ]

    assert frontend == ["GET"] + runtime_methods, (
        f"前端清单 {frontend} 与运行时 {['GET'] + runtime_methods} 不一致"
    )


def test_static_list_excludes_unsupported_methods():
    static = _static_methods()
    # 运行时对这两个方法返回 [Error] Unsupported method，配了也永远失败
    assert "HEAD" not in static
    assert "OPTIONS" not in static
    # curl -X PATCH 是最常见的写法之一，必须可选
    assert "PATCH" in static


def test_registry_form_dropdown_uses_shared_list():
    source = _source(REGISTRY)
    assert "SUPPORTED_HTTP_METHODS" in source
    # 下拉不再各写一份字面量清单
    assert 'v-for="method in SUPPORTED_HTTP_METHODS"' in source


def test_registry_filter_keeps_data_driven_extras():
    """筛选器静态项收敛到共享清单，但必须保留「并上既有数据里出现过的方法」。

    后端 method 是裸 str、无枚举校验，历史库里可能有 HEAD 等异常数据；
    删掉这一段会让那些行再也筛不出来。
    """
    source = _source(REGISTRY)
    body = source[source.index("const toolMethodOptions"):]
    body = body[: body.index("])") + 2]
    assert "SUPPORTED_HTTP_METHODS" in body
    assert "tools.value.map" in body
