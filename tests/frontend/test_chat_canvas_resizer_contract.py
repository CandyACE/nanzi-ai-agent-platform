from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_chat_canvas_resizer_contract():
    canvas_file = ROOT / "frontend/src/components/embed/ChatCanvas.vue"
    assert canvas_file.exists(), "ChatCanvas.vue file must exist"

    content = canvas_file.read_text(encoding="utf-8")

    # Verify split-screen resizer storage key and state
    assert "nanzi_canvas_preferred_width" in content
    assert "customWidth" in content
    assert "isResizing" in content

    # Verify drag handlers
    assert "startResize" in content
    assert "handleResizing" in content
    assert "stopResize" in content
    assert "resetWidth" in content

    # Verify style and template handle
    assert "panelStyle" in content
    assert "cursor-col-resize" in content
    assert "@mousedown=\"startResize\"" in content
    assert "@dblclick=\"resetWidth\"" in content

    # Verify pinning support
    assert "defineModel<boolean>('pinned'" in content
    assert "pinned = !pinned" in content
    # 钉住优先于 overlay：工作区打开 auto-pin 后用 fixed，避免被工作区抽屉盖住
    assert "if (pinned.value)" in content
    assert "z-[145]" in content
    assert "adjacentDockWidth" in content
    assert "applyFillAvailableWidth" in content
    assert "max-w-[28rem]" not in content.split("if (pinned.value)")[1].split("if (props.overlay)")[0]

    embed_chat = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    assert "canvasPinnedWidthPx" in embed_chat

    for chat_surface in (
        embed_chat,
        (ROOT / "frontend/src/views/AgentDebug.vue").read_text(encoding="utf-8"),
    ):
        assert "canvasPinned" in chat_surface
        assert 'v-model:pinned="canvasPinned"' in chat_surface
