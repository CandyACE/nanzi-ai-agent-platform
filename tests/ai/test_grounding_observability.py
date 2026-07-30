import pytest

from app.services.ai.agent_service import _build_route_grounding_metadata


pytestmark = pytest.mark.no_infrastructure


def test_route_grounding_metadata_exposes_normalized_evidence_contract():
    metadata = _build_route_grounding_metadata(
        request_source="general",
        request_capability="answer",
        confidence=0.88,
        semantic_intent=None,
        semantic_confidence=0.0,
        semantic_domain="public_web",
        fact_kind="public_fact",
    )

    assert metadata["decision_origin"] == "router"
    assert metadata["decision_confidence"] == 0.88
    assert metadata["evidence_mode"] == "none"
    assert metadata["accepted_evidence_types"] == []
    assert metadata["decision_conflicts"] == [
        "general_source_with_public_web_evidence"
    ]
