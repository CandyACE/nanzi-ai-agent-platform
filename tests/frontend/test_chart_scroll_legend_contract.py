"""滚动图例（scroll legend）的组件注册契约。

背景：plain 图例在窄容器 + 多系列时会换行，换行后的第一行会重新压到 X 轴刻度上
（实测 300px 宽 + 6 系列：图例首行 y=245 与刻度 240~252 重叠）。默认改用 scroll 后
图例始终单行、且放得下时不显示翻页箭头。

但 scroll 图例是 ECharts **按需注册**的组件：`chartRenderer` 的 option 合并（由
`frontend/scripts/chartRenderer.test.ts` 与 `test_chart_dark_theme_behavior.py` 覆盖）
只产出配置，跑不到组件注册；`vue-tsc` 也看不出来。少注册一处，运行时就会抛
`Component legend.scroll not exists` 并且整张图不渲染。因此这里把两个 AI 图表渲染
入口的注册锁住。

（同一进程内 ECharts 的 `use()` 注册表是全局的，其它页面恰好注册过也不代表安全：
组件是按路由懒加载的，只打开画布时另一处可能根本没被加载过。）
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend/src"
CHART_RENDERER = FRONTEND_SRC / "utils/chartRenderer.ts"

# AI 图表的两条渲染链路：聊天消息与画布 Markdown
RENDERERS = {
    "MessageRenderer": FRONTEND_SRC / "components/MessageRenderer.vue",
    "CanvasMarkdownRenderer": FRONTEND_SRC / "components/embed/CanvasMarkdownRenderer.vue",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _registered_components(source: str) -> str:
    match = re.search(r"use\(\[(.*?)\]\);", source, re.S)
    assert match, "未找到 echarts 的 use([...]) 组件注册块"
    return match.group(1)


@pytest.mark.parametrize("name", sorted(RENDERERS))
def test_ai_chart_renderer_registers_scroll_legend(name: str):
    source = _read(RENDERERS[name])
    # import 了但不进 use([...]) 等于没装
    assert "LegendComponent," in source
    assert "LegendScrollComponent," in source
    registered = _registered_components(source)
    assert "LegendComponent" in registered
    assert "LegendScrollComponent" in registered, f"{name} 未注册 LegendScrollComponent"


def test_scroll_legend_is_the_default():
    """默认必须是 scroll：只有默认值生效，模型没写 legend.type 时才不会再换行压刻度。"""
    source = _read(CHART_RENDERER)
    assert 'type: "scroll"' in source
    # 基础图例默认值（bottom 与 scroll 必须同时存在于同一个 legend 默认块里）
    legend_defaults = re.search(r"legend: \{(.*?)\n    \},", source, re.S)
    assert legend_defaults, "未找到 chartRenderer 的 legend 默认值块"
    block = legend_defaults.group(1)
    assert 'type: "scroll"' in block
    assert "pageTextStyle" in block
