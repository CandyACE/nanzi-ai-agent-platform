"""Contract: 元数据同步使用当前任务的鉴权 SSE 日志抽屉。"""

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]


def test_metadata_tables_uses_task_id_and_authenticated_sse_fetch():
    source = (ROOT / "frontend/src/views/MetadataDatasets.vue").read_text(encoding="utf-8")

    assert "task_id" in source
    assert "text/event-stream" in source
    assert "getReader()" in source
    assert "同步日志连接已断开" in source
    assert "同步成功" in source
    assert "同步失败" in source
    assert "关闭窗口不会取消后台同步任务" in source
    assert "credentials: 'include'" in source


def test_metadata_api_declares_sync_task_response():
    source = (ROOT / "frontend/src/api/metadata.ts").read_text(encoding="utf-8")

    assert "MetadataSyncStartResponse" in source
    assert "task_id: string" in source


def test_knowledge_base_binding_uses_current_editor_value_after_unbinding():
    source = (ROOT / "frontend/src/views/AgentManagement.vue").read_text(encoding="utf-8")

    assert "const raw = engineConfigUI.value.dataset_ids" in source
    assert "knowledge_base_binding" in source
    assert "if (!isVersionConfigStepComplete('tools'))" in source
    assert "engineConfigUI.value.dataset_ids = newIds.join(\",\")" in source
