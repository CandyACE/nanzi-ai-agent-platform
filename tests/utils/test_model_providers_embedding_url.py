import pytest

from app.utils.model_providers import normalize_embedding_endpoint


@pytest.mark.parametrize(
    ("input_url", "expected_url"),
    [
        # 火山引擎 / 带 v3 版本号
        ("https://ark.cn-beijing.volces.com/api/coding/v3", "https://ark.cn-beijing.volces.com/api/coding/v3/embeddings"),
        ("https://ark.cn-beijing.volces.com/api/coding/v3/", "https://ark.cn-beijing.volces.com/api/coding/v3/embeddings"),
        # v1 结尾
        ("https://ds-api.yovole.com/v1", "https://ds-api.yovole.com/v1/embeddings"),
        ("https://api.openai.com/v1/", "https://api.openai.com/v1/embeddings"),
        # v2 / v4 结尾
        ("https://open.bigmodel.cn/api/paas/v4", "https://open.bigmodel.cn/api/paas/v4/embeddings"),
        ("https://api.example.com/v2", "https://api.example.com/v2/embeddings"),
        # v1beta / v1alpha 等扩展版本号
        ("https://generativelanguage.googleapis.com/v1beta", "https://generativelanguage.googleapis.com/v1beta/embeddings"),
        # 已经包含 /embeddings 完整路径
        ("https://ds-api.yovole.com/v1/embeddings", "https://ds-api.yovole.com/v1/embeddings"),
        ("https://ark.cn-beijing.volces.com/api/coding/v3/embeddings", "https://ark.cn-beijing.volces.com/api/coding/v3/embeddings"),
        # 纯根域名
        ("https://api.openai.com", "https://api.openai.com/v1/embeddings"),
        ("https://api.openai.com/", "https://api.openai.com/v1/embeddings"),
        # 空或 None
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_embedding_endpoint(input_url, expected_url):
    assert normalize_embedding_endpoint(input_url) == expected_url


def test_volcengine_provider_default_url():
    from app.utils.model_providers import default_model_api_base_url, resolve_model_api_base_url

    assert default_model_api_base_url("volcengine") == "https://ark.cn-beijing.volces.com/api/v3"
    assert default_model_api_base_url("volces") == "https://ark.cn-beijing.volces.com/api/v3"
    assert resolve_model_api_base_url("volcengine", None) == "https://ark.cn-beijing.volces.com/api/v3"

