"""用户管理页「微信绑定」视图契约测试。

只做源码静态断言（沿用 tests/frontend 既有风格），不启动浏览器。
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/views/Users.vue"


def test_view_exists():
    assert VIEW.exists(), f"缺少视图文件: {VIEW}"


def test_has_wechat_binding_tab():
    view = VIEW.read_text(encoding="utf-8")

    assert "微信绑定" in view
    assert "'wechat'" in view


def test_active_view_type_includes_wechat():
    """类型必须同步扩充：漏改会让 switchView 分支写不进去，vue-tsc 也会报错。"""
    view = VIEW.read_text(encoding="utf-8")

    assert '"list" | "review" | "wechat"' in view


def test_binding_list_renders_only_masked_fields():
    view = VIEW.read_text(encoding="utf-8")

    assert "openid_masked" in view
    assert "unionid_masked" in view
    # 列表页不得直接渲染未脱敏字段。
    # ⚠️ 与计划的偏差：计划原文写的是 `assert "row.openid" not in view`，但
    # `row.openid` 恰好是计划自己的模板 `{{ row.openid_masked }}` 的前缀——两条
    # 要求互相矛盾，照抄必然失败。改用负向前瞻：只拦「后面不接 _masked」的裸字段，
    # 这才是计划注释所述的真实意图（当前文件中 row.openid/row.unionid 仅以
    # row.openid_masked / row.unionid_masked 形式出现）。
    assert not re.search(r"row\.openid(?!_masked)", view)
    assert not re.search(r"row\.unionid(?!_masked)", view)


def test_raw_identity_fetched_lazily_for_copy():
    view = VIEW.read_text(encoding="utf-8")

    assert "/identity" in view
    assert "copyBindingIdentity" in view


def test_user_list_shows_wechat_marker():
    view = VIEW.read_text(encoding="utf-8")

    assert "wechat_bound" in view


def test_switch_view_restores_status_filter_for_wechat_tab():
    """离开用户列表时必须还原 statusFilter，否则会把 status=2 带到绑定视图。"""
    view = VIEW.read_text(encoding="utf-8")

    assert 'view === "wechat"' in view
