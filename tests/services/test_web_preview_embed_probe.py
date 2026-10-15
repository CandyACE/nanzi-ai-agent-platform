"""网页预览实测探测的行为测试：重定向、SSRF 防线与失败降级。

探测是本平台唯一「由服务端按用户给的地址主动出站」的新增入口，因此这里用
``httpx.MockTransport`` 真跑 :func:`probe_embed_policy`（不 mock 被测函数本身），
重点锁定：

1. 会跟随重定向并读取**最终**页面的响应头；
2. 重定向到内网/云元数据地址时必须拦截，且**绝不真的发出**那一跳；
3. 任何失败都收敛成 ``embeddable=None``，不能默认判成「受限」（否则又会误拦）。
"""

import socket
from typing import List

import httpx
import pytest

from app.services.ai.browser import browser_policy
from app.services.ai.browser.browser_policy import BrowserUrlBlocked
from app.services.web_preview_embed_service import probe_embed_policy

pytestmark = pytest.mark.no_infrastructure

PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    """任意域名都解析到公网地址：测试不依赖真实 DNS，也不受本机网络影响。"""

    def _fake_getaddrinfo(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 0))]

    monkeypatch.setattr(browser_policy.socket, "getaddrinfo", _fake_getaddrinfo)


def _recording_transport(handler):
    """把每次请求的 URL 记录下来，便于断言「某一跳是否真的发出过」。"""
    requested: List[str] = []

    def _wrapped(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return handler(request)

    return httpx.MockTransport(_wrapped), requested


@pytest.mark.asyncio
async def test_probe_uses_final_response_headers_after_redirect():
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(302, headers={"location": "https://final.example/page"})
        return httpx.Response(200, headers={"x-frame-options": "deny"})

    transport, requested = _recording_transport(_handler)

    result = await probe_embed_policy("https://start.example/", transport=transport)

    assert result.embeddable is False
    assert result.final_url == "https://final.example/page"
    assert result.signals["x-frame-options"] == "deny"
    assert requested == ["https://start.example/", "https://final.example/page"]


@pytest.mark.asyncio
async def test_probe_blocks_redirect_into_cloud_metadata():
    """没有逐跳校验的话，一次 302 就能把 SSRF 防线绕过去。"""

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
        )

    transport, requested = _recording_transport(_handler)

    result = await probe_embed_policy("https://start.example/", transport=transport)

    assert result.embeddable is None
    assert "169.254.169.254" in result.reason
    assert requested == ["https://start.example/"], "内网那一跳绝不能被真正发出"


@pytest.mark.asyncio
async def test_probe_blocks_redirect_into_loopback():
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1:8001/api/portal"})

    transport, requested = _recording_transport(_handler)

    result = await probe_embed_policy("https://start.example/", transport=transport)

    assert result.embeddable is None
    assert requested == ["https://start.example/"]


@pytest.mark.asyncio
async def test_probe_rejects_internal_first_hop_with_exception():
    """首跳非法要显式抛错（接口层转 400），而不是伪装成「未知」。"""
    with pytest.raises(BrowserUrlBlocked):
        await probe_embed_policy("http://127.0.0.1:8001/api/portal")


@pytest.mark.asyncio
async def test_probe_rejects_non_http_scheme():
    with pytest.raises(BrowserUrlBlocked):
        await probe_embed_policy("file:///etc/passwd")


@pytest.mark.asyncio
async def test_probe_gives_up_after_too_many_redirects():
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": f"/hop{len(str(request.url))}"})

    transport, _ = _recording_transport(_handler)

    result = await probe_embed_policy("https://start.example/", transport=transport, max_redirects=2)

    assert result.embeddable is None
    assert "重定向" in result.reason


@pytest.mark.asyncio
async def test_probe_degrades_to_unknown_on_connection_error():
    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport, _ = _recording_transport(_handler)

    result = await probe_embed_policy("https://start.example/", transport=transport)

    assert result.embeddable is None, "探测失败绝不能被当成「受限」"
    assert "无法访问" in result.reason


@pytest.mark.asyncio
async def test_probe_degrades_to_unknown_on_timeout():
    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    transport, _ = _recording_transport(_handler)

    result = await probe_embed_policy("https://start.example/", transport=transport)

    assert result.embeddable is None


@pytest.mark.asyncio
async def test_probe_reports_embeddable_when_no_anti_framing_headers():
    """回归：baidu.com 这类「没有防嵌套头」的站点必须判成可嵌。"""

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"server": "bfe", "content-type": "text/html"})

    transport, _ = _recording_transport(_handler)

    result = await probe_embed_policy("https://www.baidu.com/", transport=transport)

    assert result.embeddable is True
    assert result.signals == {}
