from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "frontend/src/api/artifact.ts"
DRAWER = ROOT / "frontend/src/components/embed/MyArtifactsDrawer.vue"
LIST = ROOT / "frontend/src/components/embed/ReusableResultList.vue"
STATUS = ROOT / "frontend/src/components/chat/ReusableResultStatus.vue"
NOTICE = ROOT / "frontend/src/components/chat/ReusableResultNotice.vue"
EMBED = ROOT / "frontend/src/views/EmbedChat.vue"


def test_reusable_result_api_exposes_conversation_scoped_safe_list():
    source = API.read_text(encoding="utf-8")

    assert "ReusableResultListItem" in source
    assert "reusableResults" in source
    assert "/api/v1/chat/reusable-results" in source
    assert "conversation_id" in source
    assert "result_id" in source


def test_artifacts_drawer_has_files_and_reusable_result_tabs():
    source = DRAWER.read_text(encoding="utf-8")

    assert "文件产物" in source
    assert "可复用结果" in source
    assert "ReusableResultList" in source
    assert "select-reusable-result" in source
    assert "conversationId" in source


def test_reusable_result_components_expose_selection_and_status_entry():
    list_source = LIST.read_text(encoding="utf-8")
    status_source = STATUS.read_text(encoding="utf-8")

    assert "defineEmits" in list_source
    assert "reusableResults" in list_source
    assert "选择用于下一轮" in list_source
    assert "过期" in list_source
    assert "defineEmits" in status_source
    assert "已保存可复用结果" in status_source
    assert "已复用上一轮结果" in status_source
    assert "查看可复用结果" in status_source


def test_reusable_result_notice_explains_reused_previous_result():
    source = NOTICE.read_text(encoding="utf-8")

    assert 'role="note"' in source
    assert "引用提示" in source
    assert "本次回答基于" in source
    assert "可复用结果" in source
    assert "originName" in source


def test_embed_chat_wires_status_event_selection_and_one_shot_request_id():
    source = EMBED.read_text(encoding="utf-8")

    assert 'import ReusableResultStatus from "@/components/chat/ReusableResultStatus.vue"' in source
    assert 'import ReusableResultNotice from "@/components/chat/ReusableResultNotice.vue"' in source
    assert 'import ReusableResultList from "@/components/embed/ReusableResultList.vue"' not in source
    assert "reusableResultStatus" in source
    assert "selectedReusableResultId" in source
    assert "focusedReusableResultId" in source
    assert "reusable_result_id" in source
    assert "reusable_result_status" in source
    assert "@select-reusable-result" in source
    assert "openReusableResults(" in source
    assert "<ReusableResultNotice" in source
    assert "msg.reusableResultStatus?.status === 'reused'" in source


def test_embed_chat_clears_selection_after_request_snapshot_is_captured():
    source = EMBED.read_text(encoding="utf-8")

    assert "reusableResultId?: string | null" in source
    assert "selectedReusableResultId.value = null" in source
    assert "snapshot.reusableResultId" in source


def test_embed_chat_keeps_reused_notice_when_followup_result_is_saved():
    source = EMBED.read_text(encoding="utf-8")

    assert "data.status === \"saved\"" in source
    assert "msg.reusableResultStatus?.status === \"reused\"" in source
    assert "return true;" in source
