"""网页预览「能否内嵌」判定口径测试（响应头 → 结论）。

背景：``X-Frame-Options`` / CSP ``frame-ancestors`` 都是**响应头**，跨域 iframe
里前端既读不到、也无法自证被拦（被拦时 ``onload`` 仍会触发）。所以判定必须由
服务端读取真实响应头完成。本文件用**线上实测抓到的真实头样本**锁定判定口径，
避免再次把「经验预判」当成「实测结论」。

样本来源（2026-10 实测）：
- ``www.baidu.com``：无 XFO、无 CSP          → 可嵌（旧前端名单误报为受限）
- ``github.com``：XFO deny + frame-ancestors 'none' → 不可嵌
- ``www.google.com``：XFO SAMEORIGIN + **report-only** CSP → 不可嵌
"""

import pytest

from app.services.web_preview_embed_service import (
    EmbedPolicyVerdict,
    evaluate_embed_policy,
)

pytestmark = pytest.mark.no_infrastructure

PLATFORM_ORIGIN = "https://portal.example.com"


def _verdict(pairs, *, platform_origins=(PLATFORM_ORIGIN,)) -> EmbedPolicyVerdict:
    return evaluate_embed_policy(pairs, platform_origins=platform_origins)


# --- 无任何防嵌套声明：必须判定为可嵌（这正是 baidu.com 被误报的场景） ---


def test_plain_response_without_headers_is_embeddable():
    verdict = _verdict([("server", "bfe"), ("content-type", "text/html")])

    assert verdict.embeddable is True
    assert verdict.signals == {}


# --- X-Frame-Options ---


@pytest.mark.parametrize("value", ["DENY", "deny", "Deny", " sameorigin ", "SAMEORIGIN"])
def test_xfo_deny_and_sameorigin_block_embedding(value):
    verdict = _verdict([("X-Frame-Options", value)])

    assert verdict.embeddable is False
    assert "X-Frame-Options" in verdict.reason
    assert verdict.signals["x-frame-options"] == value.strip()


def test_xfo_allow_from_is_treated_as_blocking():
    """ALLOW-FROM 已被现代浏览器废弃，不可能命中平台自身，按拦截处理。"""
    verdict = _verdict([("x-frame-options", "ALLOW-FROM https://other.example.com")])

    assert verdict.embeddable is False


def test_xfo_unknown_token_does_not_block():
    """浏览器会忽略无法识别的取值，判定侧不应凭空判定受限。"""
    verdict = _verdict([("x-frame-options", "ALLOWALL")])

    assert verdict.embeddable is True


# --- CSP frame-ancestors ---


@pytest.mark.parametrize(
    "policy",
    [
        "frame-ancestors 'none'",
        "frame-ancestors 'self'",
        "default-src 'none'; frame-ancestors 'none'",
        "frame-ancestors;",  # 空源列表等价于全部拒绝
    ],
)
def test_csp_frame_ancestors_blocks_when_platform_not_allowed(policy):
    verdict = _verdict([("content-security-policy", policy)])

    assert verdict.embeddable is False
    assert "frame-ancestors" in verdict.reason


def test_csp_frame_ancestors_wildcard_allows_embedding():
    verdict = _verdict([("content-security-policy", "frame-ancestors *")])

    assert verdict.embeddable is True


def test_csp_frame_ancestors_explicit_platform_origin_allows_embedding():
    verdict = _verdict(
        [("content-security-policy", f"frame-ancestors 'self' {PLATFORM_ORIGIN}")]
    )

    assert verdict.embeddable is True


def test_csp_frame_ancestors_other_origin_blocks_embedding():
    verdict = _verdict(
        [("content-security-policy", "frame-ancestors https://other.example.com")]
    )

    assert verdict.embeddable is False


def test_csp_frame_ancestors_subdomain_wildcard_matches_platform_origin():
    verdict = _verdict(
        [("content-security-policy", "frame-ancestors https://*.example.com")]
    )

    assert verdict.embeddable is True


def test_csp_without_frame_ancestors_directive_is_embeddable():
    """``default-src 'none'`` 不会限制嵌入；只有显式 frame-ancestors 才会。"""
    verdict = _verdict(
        [
            (
                "content-security-policy",
                "default-src 'none'; script-src 'self'; img-src 'self'",
            )
        ]
    )

    assert verdict.embeddable is True


def test_report_only_csp_never_blocks():
    """report-only 只上报不拦截 —— google.com 样本里就是它，不能当拦截依据。"""
    verdict = _verdict(
        [
            ("content-security-policy-report-only", "frame-ancestors 'none'"),
            ("x-frame-options", "SAMEORIGIN"),
        ]
    )

    assert verdict.embeddable is False  # 由 XFO 拦，而非 report-only
    assert "report-only" not in verdict.signals


# --- 多策略叠加：任一条拦截即不可嵌 ---


def test_every_enforced_csp_policy_must_allow_embedding():
    verdict = _verdict(
        [
            ("content-security-policy", "frame-ancestors *"),
            ("content-security-policy", "frame-ancestors 'none'"),
        ]
    )

    assert verdict.embeddable is False


def test_multiple_allowing_policies_stay_embeddable():
    verdict = _verdict(
        [
            ("content-security-policy", "frame-ancestors *"),
            ("content-security-policy", "default-src 'self'"),
        ]
    )

    assert verdict.embeddable is True


# --- 线上真实样本回归 ---


def test_real_baidu_sample_is_embeddable_regression():
    """回归：这份响应头曾被硬编码名单误判为「禁止内嵌」。"""
    verdict = _verdict([("server", "bfe"), ("content-type", "text/html;charset=utf-8")])

    assert verdict.embeddable is True


def test_real_github_sample_is_blocked():
    verdict = _verdict(
        [
            ("x-frame-options", "deny"),
            ("content-security-policy", "default-src 'none'; frame-ancestors 'none'"),
        ]
    )

    assert verdict.embeddable is False
    assert verdict.signals["x-frame-options"] == "deny"
    assert "frame-ancestors" in verdict.signals["content-security-policy"]


def test_verdict_is_frozen_dataclass_with_reason():
    verdict = _verdict([("x-frame-options", "DENY")])

    assert isinstance(verdict, EmbedPolicyVerdict)
    assert verdict.reason
    with pytest.raises(Exception):
        verdict.embeddable = True  # type: ignore[misc]
