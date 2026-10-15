"""网页预览内嵌决策的行为测试 + 组件契约。

行为部分用 Node 真跑 ``frontend/src/utils/webPreviewEmbed.ts``（纯函数，零依赖），
覆盖「实测优先、名单仅降级」这条本次修复的核心口径；契约部分锁定组件确实接了
实测接口，且不再把经验预判写成「目标网站声明了」这类绝对结论。
"""

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "frontend/src/components/embed/WebPreviewPanel.vue"
UTIL = ROOT / "frontend/src/utils/webPreviewEmbed.ts"
API = ROOT / "frontend/src/api/webPreview.ts"


def _panel_source() -> str:
    return PANEL.read_text(encoding="utf-8")


def test_embed_decision_behavior_passes_in_node():
    script = ROOT / "tests/frontend/web_preview_embed_decision.mjs"
    assert script.exists(), "行为测试脚本缺失"

    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", str(script)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "网页预览内嵌决策测试全部通过" in proc.stdout


def test_decision_helper_is_dependency_free():
    """纯函数模块必须零运行时依赖，否则 Node 无法直接加载。

    只检查真正的 ``import`` 语句：注释里出现 ``axios`` 不算依赖，
    粗暴的子串断言会把文档说明误判成违规。
    """
    source = UTIL.read_text(encoding="utf-8")
    runtime_imports = [
        line.strip()
        for line in source.splitlines()
        if re.match(r"\s*import\s", line) and not line.lstrip().startswith("import type")
    ]

    assert runtime_imports == [], f"纯函数模块不允许运行时导入：{runtime_imports}"
    assert not re.search(r"""from\s+['"]@/""", source), "不允许别名导入"
    assert "window." not in source


def test_panel_probes_backend_instead_of_trusting_a_static_denylist():
    source = _panel_source()

    assert "checkWebPreviewEmbed" in source, "组件必须调用后端实测接口"
    assert "resolveEmbedDecision" in source
    assert "probeEmbeddable" in source
    assert "watch(" in source


def test_panel_renders_optimistically_while_probe_is_pending():
    """探测未出结论时必须先渲染 iframe —— 避免再次出现「先弹提示、点了才加载」。"""
    source = _panel_source()

    assert "restrictedDecision" in source
    assert re.search(r"shouldShowRestrictedCard\s*=\s*computed", source)
    assert "blocked" in source
    assert "pending" in source, "探测中必须走乐观分支"


def test_copy_distinguishes_measured_from_predicted():
    """实测受限与名单预判必须是两种文案，且不再谎称已声明策略。

    文案本体在纯函数模块里（决策即文案来源），组件只负责渲染并标注结论依据。
    """
    panel = _panel_source()
    helper = UTIL.read_text(encoding="utf-8")

    assert "目标网站声明了安全防嵌套策略" not in panel, "绝对化文案必须移除"
    assert "该站点禁止内嵌预览" in helper
    assert "该站点可能禁止内嵌预览" in helper
    assert "实测" in helper
    assert "预判" in helper

    assert "重新检测" in panel
    assert "仍尝试在内嵌框架中加载" in panel, "兜底入口必须保留"
    assert "实测" in panel and "预判" in panel, "卡片必须标注结论依据"


def test_panel_keeps_existing_external_open_and_zoom_contracts():
    source = _panel_source()

    for marker in (
        "在新标签页打开网页",
        "在新窗口打开",
        "sandbox=",
        'referrerpolicy="no-referrer"',
        "PREVIEW_ZOOM_OPTIONS",
        "effectiveZoom",
        "frameScaleStyle",
        "handleOpenInNewTab",
    ):
        assert marker in source, f"既有契约被破坏：{marker}"

    assert source.count("handleOpenInNewTab") >= 3


def test_api_module_targets_the_portal_embed_check_endpoint():
    source = API.read_text(encoding="utf-8")

    assert "/portal/web-preview/embed-check" in source
    assert "embeddable" in source
    assert "axios" in source
