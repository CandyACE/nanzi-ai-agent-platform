"""Contract: 检索测试页展示知识库名称，但请求仍提交 Dataset ID。"""

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]


def retrieval_test_source() -> str:
    return (ROOT / "frontend/src/views/KnowledgeRetrievalTest.vue").read_text(encoding="utf-8")


def selector_source() -> str:
    return (ROOT / "frontend/src/components/RagFlowResourceSelector.vue").read_text(encoding="utf-8")


def test_retrieval_test_renders_dataset_names_and_keeps_ids_for_payload():
    source = retrieval_test_source()

    assert "datasetNameById" in source
    assert "datasetIds" in source
    assert "还有" in source
    assert "dataset_ids: datasetIds.value" in source


def test_selector_emits_selected_dataset_details_for_name_mapping():
    source = selector_source()

    assert "selectedDetails" in source
    assert "platform_name" in source
    assert '@select-details="handleDatasetDetailsSelect"' in retrieval_test_source()
