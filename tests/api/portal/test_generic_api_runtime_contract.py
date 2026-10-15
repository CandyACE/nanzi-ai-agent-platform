"""``GenericApiToolFactory._execute_request`` 的对外输出契约（端到端）。

为什么需要它：为了让「保存前试跑」与智能体运行时**走同一段请求代码**（否则会出现
「试跑通过、运行时失败」的口径分裂），本次把请求内核抽成了 ``_perform_request``。
抽取是纯重构，**运行时对外的返回值必须逐字节不变**——这些用例就是那道闸门。

守卫的层次很关键：**这里把 ``httpx.AsyncClient`` 换掉，而不是把 ``_perform_request``
换掉**。mock 内核只能证明「格式化分支没改」，证明不了「路径替换 / 参数落位 / headers /
非 2xx 抛错 / 方法分支」这条链路的整体行为；mock 传输层则让新旧实现必须走完同一条路
才可能返回同样的字符串。抽取前后用同一组 httpx 场景逐字节对比过（10 个场景全一致，
含 ``[Error] Unsupported method: HEAD`` 这个易失文案）。
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from app.models.tool import SysApiTool
from app.services.ai.tools.generic_api import GenericApiToolFactory


def _tool(**overrides) -> SysApiTool:
    payload = {
        "id": "t1",
        "name": "demo_tool",
        "method": "GET",
        "url_template": "https://api.test/v1/items",
        "headers": "{}",
        "parameter_schema": "{}",
        "is_active": True,
    }
    payload.update(overrides)
    return SysApiTool(**payload)


def _response(status_code: int, *, json_body=None, text: str | None = None, content: bytes | None = None):
    return httpx.Response(
        status_code=status_code,
        json=json_body,
        text=None if json_body is not None else text,
        content=content,
        request=httpx.Request("GET", "https://api.test/v1/items"),
    )


def _transport(response=None, error=None, capture=None):
    """把传输层换成假实现，让被测代码走完整真实链路。"""

    def _respond(verb, url, payload, headers):
        if capture is not None:
            capture.update(
                verb=verb,
                url=url,
                payload=payload,
                headers=dict(headers or {}),
            )
        if error is not None:
            raise error
        return response

    class FakeClient:
        def __init__(self, *args, **kwargs):
            if capture is not None:
                capture["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, params=None, headers=None):
            return _respond("GET", url, params, headers)

        async def request(self, method, url, json=None, headers=None):
            return _respond(method, url, json, headers)

    return patch("app.services.ai.tools.generic_api.httpx.AsyncClient", FakeClient)


# --------------------------------------------------------------------------- #
# 返回值形态：五种情形必须与抽取前逐字节一致
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_2xx_json_is_dumped_without_ascii_escape():
    with _transport(response=_response(200, json_body={"城市": "北京"})):
        result = await GenericApiToolFactory._execute_request(_tool(), {})
    assert result == json.dumps({"城市": "北京"}, ensure_ascii=False)


@pytest.mark.asyncio
async def test_2xx_plain_text_is_returned_as_is():
    with _transport(response=_response(200, text="hello")):
        result = await GenericApiToolFactory._execute_request(_tool(), {})
    assert result == "hello"


@pytest.mark.asyncio
async def test_204_returns_success_envelope():
    with _transport(response=_response(204, content=b"")):
        result = await GenericApiToolFactory._execute_request(_tool(), {})
    assert result == {"success": True, "content": ""}


@pytest.mark.asyncio
async def test_non_2xx_becomes_execution_error_with_status_and_truncated_body():
    """非 2xx 的文案格式是既有契约（日志与排障都按它认），不能变。"""
    long_text = "x" * 800
    with _transport(response=_response(404, text=long_text)):
        result = await GenericApiToolFactory._execute_request(_tool(), {})
    assert result == f"[Execution Error] HTTP 404: {long_text[:500]}"


@pytest.mark.asyncio
async def test_connection_failure_becomes_execution_error():
    with _transport(error=httpx.ConnectError("boom")):
        result = await GenericApiToolFactory._execute_request(_tool(), {})
    assert result == "[Execution Error] boom"


@pytest.mark.asyncio
async def test_timeout_becomes_execution_error():
    with _transport(error=httpx.TimeoutException("timed out")):
        result = await GenericApiToolFactory._execute_request(_tool(), {})
    assert result == "[Execution Error] timed out"


@pytest.mark.asyncio
async def test_unsupported_method_keeps_original_wording():
    """历史文案是 ``[Error] Unsupported method: XXX``（不是 ``[Execution Error]``）。"""
    capture: dict = {}
    with _transport(response=_response(200, text="never"), capture=capture):
        result = await GenericApiToolFactory._execute_request(_tool(method="HEAD"), {})
    assert result == "[Error] Unsupported method: HEAD"
    assert "url" not in capture, "不支持的方法不该真的发出请求"


# --------------------------------------------------------------------------- #
# 请求形态：路径替换 / 参数落位 / headers —— 试跑与运行时同源的实质
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_path_params_are_substituted_and_excluded_from_query():
    capture: dict = {}
    with _transport(response=_response(200, json_body={"ok": True}), capture=capture):
        await GenericApiToolFactory._execute_request(
            _tool(url_template="https://api.test/v1/items/{id}/detail"),
            {"id": "7", "q": "x"},
        )
    assert capture["url"] == "https://api.test/v1/items/7/detail"
    # 已用于路径替换的参数不该再出现在 query 里
    assert capture["payload"] == {"q": "x"}


@pytest.mark.asyncio
async def test_non_get_sends_remaining_params_as_json_body():
    capture: dict = {}
    with _transport(response=_response(200, json_body={"ok": True}), capture=capture):
        await GenericApiToolFactory._execute_request(
            _tool(method="POST", url_template="https://api.test/v1/orders/{id}"),
            {"id": "9", "amount": 100},
        )
    assert capture["verb"] == "POST"
    assert capture["url"] == "https://api.test/v1/orders/9"
    assert capture["payload"] == {"amount": 100}


@pytest.mark.asyncio
async def test_configured_headers_are_forwarded():
    capture: dict = {}
    with _transport(response=_response(200, json_body={"ok": True}), capture=capture):
        await GenericApiToolFactory._execute_request(
            _tool(headers=json.dumps({"Authorization": "Bearer sk-x", "X-Base": "1"})), {},
        )
    assert capture["headers"] == {"Authorization": "Bearer sk-x", "X-Base": "1"}


@pytest.mark.asyncio
async def test_transport_disables_env_proxy_and_keeps_30s_timeout():
    """既有行为：不走环境代理（避免缺少 SOCKS 依赖时报错），超时 30 秒。"""
    capture: dict = {}
    with _transport(response=_response(200, json_body={"ok": True}), capture=capture):
        await GenericApiToolFactory._execute_request(_tool(), {})
    assert capture["client_kwargs"].get("trust_env") is False
    assert capture["client_kwargs"].get("timeout") == 30.0


# --------------------------------------------------------------------------- #
# 内核 API：试跑需要「非 2xx 也拿到原始响应」
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_perform_request_raises_on_http_error_only_when_asked():
    with _transport(response=_response(404, text="nope")):
        response, elapsed, _url = await GenericApiToolFactory._perform_request(
            _tool(), {}, raise_on_http_error=False,
        )
        assert response.status_code == 404
        assert isinstance(elapsed, int)

        with pytest.raises(RuntimeError) as excinfo:
            await GenericApiToolFactory._perform_request(_tool(), {})
        assert str(excinfo.value) == "HTTP 404: nope"
