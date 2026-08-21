"""真实 Chromium 端到端集成测试（可选）。

覆盖 A4 要求的「真实浏览器」验证，针对 app/services/ai/browser 三层工具在真实
Playwright Chromium 上跑通完整链路：

* A1 等待目标可交互：真实 locator 含 wait_for，``_ensure_actionable`` 在落实动作前
  等待可见。
* A2 动作失败恢复：真实页面上目标稳定，验证真实 locator 走通无 wait_for 兼容分支。
* A3 拖后生效校验：滑块拖拽后再读回页面状态，确认拟人轨迹真正触发了 DOM 变更。
* B1 非线性拟人轨迹：``slider_drag`` 在真实页面上执行缓入缓出分段拖拽。
* C1 STEALTH 指纹加固：在真实 ``window`` / ``navigator`` 上断言指纹脚本生效。

这些测试会真实启动本机缓存的 Chromium，因此：

* 模块级 ``pytest.importorskip("playwright")`` 保证没有安装 playwright 时直接跳过；
* 运行环境缺少可用浏览器（executable 不存在 / 启动失败）时 ``real_worker`` fixture
  显式 ``pytest.skip``，避免默认 ``run_tests.sh`` 全量套件在无浏览器 CI 上挂掉；
* 模块级 ``no_infrastructure`` 标记隔离，避免 conftest 自动初始化 DB / Redis。

社区常见的真实浏览器测试都需要本机有 Playwright 浏览器缓存，本仓库开发机已有
``~/Library/Caches/ms-playwright``（chromium-1194/1208/1223），这里直接复用。
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright")

pytestmark = pytest.mark.no_infrastructure

from app.schemas.browser import BrowserSnapshot  # noqa: E402
from app.services.ai.browser.browser_worker import BrowserWorker  # noqa: E402

# 一个自带滑块（可从起点拖动）、缺口落点、复选框与按钮的测试页。
#
# 元素与 SNAPSHOT_JS 语义对应（见 browser_worker.py 的 _role_source 规则）：
#   * #knob  cursor:pointer 且无原生/显式 role → 推断为可交互按钮 (inferred)，
#     name 取 aria-label="滑块"；定位走 nth(_node_index)，姓名用于测试里按名找 ref。
#   * #gap   加入 tabindex="0" + aria-label="缺口"，让无原生 role 的它有显式
#     tabindex → 推断为可交互，从而进入快照候选（否则根本不出现）。
#   * #agree 原生 input 会被 nativeRoles 记为 role=textbox；这里显式声明
#     role="checkbox" + aria-label="同意协议" → _role_source=explicit、role=checkbox，
#     可被 get_by_role('checkbox', name=...) 定位。
# 滑块把手用原生 mouse 事件跟踪位移，写入 window.__moved（供 A3 拖后校验）。
_INTEGRATION_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  body { font-family: sans-serif; margin: 24px; }
  #track { position: relative; width: 400px; height: 40px; background: #e2e8f0;
           border-radius: 6px; }
  #knob { position: absolute; left: 0; top: 0; width: 40px; height: 40px;
          background: #2563eb; border-radius: 6px; cursor: pointer; }
  #gap { position: absolute; left: 260px; top: 0; width: 24px; height: 40px;
         background: #ef4444; border-radius: 4px; }
  label { display: inline-block; margin-top: 16px; }
  #submit { margin-top: 16px; padding: 6px 14px; }
</style>
</head>
<body>
  <h1 id="title">浏览器集成测试页</h1>
  <div id="track">
    <div id="knob" aria-label="滑块"></div>
    <div id="gap" aria-label="缺口" tabindex="0"></div>
  </div>
  <p id="moved">0</p>
  <label><input type="checkbox" id="agree" role="checkbox" aria-label="同意协议">
    同意协议</label><br>
  <button id="submit">提交</button>
  <script>
    (function () {
      var knob = document.getElementById('knob');
      var movedText = document.getElementById('moved');
      var dragging = false, startClientX = 0, originLeft = 0;
      window.__movedRawEvents = 0;
      knob.addEventListener('mousedown', function (e) {
        dragging = true; startClientX = e.clientX; originLeft = knob.offsetLeft;
        e.preventDefault();
      });
      document.addEventListener('mousemove', function (e) {
        if (!dragging) return;
        window.__movedRawEvents += 1;
        var dx = e.clientX - startClientX + originLeft;
        var maxLeft = document.getElementById('track').clientWidth - knob.offsetWidth;
        if (dx < 0) dx = 0;
        if (dx > maxLeft) dx = maxLeft;
        knob.style.left = dx + 'px';
        movedText.textContent = String(dx);
      });
      document.addEventListener('mouseup', function () { dragging = false; });
    })();
  </script>
</body>
</html>
"""


def _integration_url() -> str:
    """把测试页编码为 data: URL。"""
    from urllib.parse import quote
    return "data:text/html;charset=utf-8," + quote(_INTEGRATION_HTML)


@pytest.fixture(scope="module")
async def real_worker(tmp_path_factory):
    """启动一个真实持久化 Chromium 上下文并交给测试使用。

    浏览器不可用时显式跳过（skip），不影响默认全量套件执行。
    """
    worker = BrowserWorker(url_validator=lambda url: url, screenshot_dir=None)
    profile = str(tmp_path_factory.mktemp("bs-it-profile"))
    try:
        await worker.open(
            session_id="it",
            profile_path=profile,
            url=_integration_url(),
        )
    except (RuntimeError, OSError) as exc:
        try:
            await worker.shutdown()
        except Exception:
            pass
        pytest.skip(f"真实浏览器不可用，跳过浏览器集成测试：{exc}")

    yield worker

    try:
        await worker.shutdown()
    except Exception:
        pass


def _element_ref_by_name(snapshot: BrowserSnapshot, name: str) -> str:
    """按可访问名在快照里查元素 ref（先 aria-label，没有则取可见文本）。"""
    for el in snapshot.elements:
        if el.name and el.name == name:
            return el.ref
    raise AssertionError(f"快照里没有 name={name!r} 的元素")


async def test_real_browser_stealth_fingerprint(real_worker):
    """C1：STEALTH 初始化脚本在真实 Chromium 的 window/navigator 上生效。"""
    page = real_worker._handles["it"].page
    result = await page.evaluate(
        """() => ({
          webdriver: (navigator.webdriver === undefined || navigator.webdriver === false)
            ? undefined : navigator.webdriver,
          plugins: navigator.plugins.length,
          hasChrome: (window.chrome && window.chrome.runtime) ? true : false,
          getManifestType: typeof (window.chrome && window.chrome.runtime &&
            window.chrome.runtime.getManifest),
          appIsInstalled: window.chrome && window.chrome.app
            ? window.chrome.app.isInstalled : null,
          languages: navigator.languages,
          uaDataBrands: navigator.userAgentData ? navigator.userAgentData.brands.length : 0,
        })"""
    )

    # C1 指纹目标：webdriver 不可见；插件列表非空；chrome.runtime 结构完整且可调用。
    assert result["webdriver"] is None, f"webdriver 应被隐藏，got {result['webdriver']!r}"
    assert result["plugins"] > 0, "navigator.plugins 应为非空"
    assert result["hasChrome"] is True, "window.chrome.runtime 应存在"
    assert result["getManifestType"] == "function", "chrome.runtime.getManifest 应为函数"
    assert result["appIsInstalled"] is False, "chrome.app.isInstalled 应为 false"
    assert "zh-CN" in result["languages"], "languages 应含 zh-CN"
    assert result["uaDataBrands"] > 0, "userAgentData.brands 应为非空"

    # STEALTH 脚本里的 CDP 标记清理：这些是会被 bot 检测到的全局函数名。
    markers = await page.evaluate(
        """() => ['cdc_adoQpoasnfa76pfcZLmcfl_Array',
                 'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
                 'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
                 '__injected', '__selenium_evaluate']
                 .map((m) => [m, m in window])"""
    )
    cleaned = {m: present for m, present in markers}
    assert not any(cleaned.values()), f"CDP 标记应被清理：{cleaned}"


async def test_real_browser_slider_drag_with_measured_gap(real_worker):
    """B1+A3：真实页面上拟人轨迹滑块拖拽，并用 gap_target_ref 自动测距后校验落点。"""
    snapshot = await real_worker.snapshot("it")
    assert snapshot.elements, "真实页面快照应抓到至少一个元素"
    knob_ref = _element_ref_by_name(snapshot, "滑块")
    gap_ref = _element_ref_by_name(snapshot, "缺口")

    result = await real_worker.slider_drag(
        "it",
        source_ref=knob_ref,
        snapshot=snapshot,
        gap_target_ref=gap_ref,
    )
    assert result.data["distance_px"] > 0, "测量距离应为正数"
    assert result.data["measured_gap_px"] is not None, "应返回测量到的缺口距离"
    assert result.data["steps"] >= 1, "拟人轨迹应至少有一次分段移动"

    # A3 拖后生效校验：读回页面状态确认把手真的被拖到了缺口附近。
    page = real_worker._handles["it"].page
    left = await page.locator("#knob").evaluate("(el) => el.offsetLeft")
    raw_events = await page.evaluate("() => window.__movedRawEvents")
    moved_text = await page.locator("#moved").text_content()
    assert int(moved_text or "0") > 0, "页面应记录到滑块位移"
    assert raw_events and raw_events >= 3, f"拟人轨迹应产生多次 mousemove，got {raw_events}"
    # 缺口 left=260、宽 24，把手宽 40 → 起点 0；拖到缺口中心 272，把手左缘≈232。
    assert 180 <= left <= 280, f"把手应被拖到缺口附近，left={left}px"


async def test_real_browser_click_toggles_checkbox(real_worker):
    """A2+A3：真实页面上坐标级点击复选框并校验点击生效。"""
    snapshot = await real_worker.snapshot("it")
    agree_ref = _element_ref_by_name(snapshot, "同意协议")
    assert (
        next(el for el in snapshot.elements if el.ref == agree_ref).role == "checkbox"
    ), "复选框在快照里应为显式 checkbox 角色"

    result = await real_worker.click("it", target_ref=agree_ref, snapshot=snapshot)
    assert result.url.startswith("data:"), result.url

    page = real_worker._handles["it"].page
    checked = await page.locator("#agree").is_checked()
    assert checked is True, "点击后复选框应被勾选"