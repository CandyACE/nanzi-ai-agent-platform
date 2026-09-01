from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure


def test_business_mcp_guide_contains_python_and_java_verification_examples():
    guide = Path("docs/md/mcp_user_context_integration_guide.md").read_text(encoding="utf-8")

    assert "### 6.1 Python 版本" in guide
    assert "PyJWKClient" in guide
    assert "hmac.compare_digest" in guide
    assert "### 6.2 Java 版本" in guide
    assert "nimbus-jose-jwt" in guide
    assert "Ed25519Verifier" in guide
    assert "JWSAlgorithm.EdDSA" in guide
    assert "assertJtiIsNotReplayed" in guide


def test_business_mcp_guide_keeps_identity_out_of_tool_arguments():
    guide = Path("docs/md/mcp_user_context_integration_guide.md").read_text(encoding="utf-8")

    assert "不要从参数中的 `user_id` 判断当前操作人" in guide
    assert "claims.get(\"user_context\")" in guide
