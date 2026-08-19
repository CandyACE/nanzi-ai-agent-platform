from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure


ROOT = Path(__file__).resolve().parents[2]


def test_browser_panel_contains_same_origin_viewer_and_manual_input_contract():
    source = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    assert "WebSocket" in source
    assert "mouse_click" in source
    assert "mouse_down" in source
    assert "mouse_move" in source
    assert "mouse_up" in source
    assert "@pointerdown" in source
    assert "@pointermove" in source
    assert "@pointerup" in source
    assert "screenshot_ref" in source
    assert "autopilot" in source
    assert "defineModel<boolean>('pinned'" in source
    assert "panelWidth" in source
    assert "startResize" in source
    assert "左右拖拽调整浏览器宽度" in source


def test_browser_panel_exposes_clear_guarded_status_and_dismissible_notice():
    source = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    assert "showSafetyNotice" in source
    assert "安全确认已开启" in source
    assert "关闭安全提示" in source
    assert "approvalMode === 'guarded'" in source
    assert "watch(() => props.approvalMode" in source
    assert "approvalStatusLabel" not in source
    assert "approvalStatusClass" not in source


def test_browser_panel_explains_screenshot_surface_and_hides_internal_targets():
    source = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    assert "远程页面截图" in source
    assert "不是网页本体" in source
    assert "点击、滚轮、键盘会转发到远程浏览器" in source
    assert "每 5 秒自动刷新" in source
    assert 'v-for="element in snapshot.elements"' not in source
    assert 'ref="viewportRef"' in source
    assert "viewportRef.value?.focus" in source


def test_browser_panel_exposes_remote_focus_feedback_plain_manual_input_and_session_close():
    source = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    assert "remoteFocusMessage" in source
    assert "已聚焦远程页面" in source
    assert "lastClickStyle" not in source
    assert "naturalWidth" in source
    assert "naturalHeight" in source
    assert 'type="text"' in source
    assert 'type="password"' not in source
    assert "showManualInput" in source
    assert 'v-if="showManualInput"' in source
    assert "focused_input" in source
    assert "人工输入" in source
    assert "close-session" in source


def test_browser_panel_cache_busts_screenshot_when_snapshot_changes():
    source = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    assert "const screenshotUrl = computed" in source
    assert "snapshot_id=" in source
    assert ':src="screenshotUrl"' in source


def test_browser_panel_refresh_pause_is_manual_not_pointer_triggered():
    source = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    assert '@click="autoRefreshPaused ? resumeAutoRefresh() : pauseAutoRefresh()"' in source
    assert '@mouseenter="pauseAutoRefresh"' not in source
    assert '@focus="pauseAutoRefresh"' not in source


def test_browser_panel_exposes_human_handoff_refresh_and_captcha_state():
    source = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    assert "controlOwner" in source
    assert "当前由人工操作" in source
    assert "交还 AI" in source
    assert "interactionInProgress" in source
    assert "captchaDetected" in source
    assert "release_control" in source
    assert "controlOwner.value === 'human'" in source


def test_embed_chat_contains_browser_panel_toggle_and_session_binding():
    source = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    assert "BrowserPanel" in source
    assert "/api/v1/chat/browser/sessions/open" in source
    assert "browser_session_id" in source
    assert "browserViewerToken" in source
    assert "browser_session" in source
    assert "v-model:pinned=\"browserPinned\"" in source
    assert "v-model:panel-width=\"browserPanelWidthReactive\"" in source
    assert 'const browserApprovalMode = ref<BrowserApprovalMode>("autopilot")' in source
    assert '@close-session="closeBrowserSession"' in source
    assert "const closeBrowserSession = async" in source
    assert "axios.delete" in source


def test_browser_panel_opens_immediately_with_loading_stages_and_reuses_viewer_session():
    panel = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert "loading" in panel
    assert "正在准备服务端浏览器" in panel
    assert "正在连接实时画面" in panel
    assert "snapshotRequestInFlight" in panel
    assert "if (snapshotRequestInFlight.value) return" in panel
    assert "browserPanelOpening" in embed
    assert "browserPanelVisible.value = true" in embed
    assert "browserSessionId.value && browserViewerToken.value" in embed


def test_browser_panel_does_not_request_duplicate_initial_snapshot_and_reports_disconnect():
    source = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    on_open = source.split("client.onopen", 1)[1].split("client.onmessage", 1)[0]

    assert "client.send(JSON.stringify({ type: 'snapshot' }));" not in on_open
    assert "if (socket.value !== client) return;" in on_open
    assert "BROWSER_PANEL_REFRESH_INTERVAL_MS = 5000" in source
    assert "setInterval(requestSnapshot, BROWSER_PANEL_REFRESH_INTERVAL_MS)" in source
    assert "浏览器连接已断开" in source


def test_browser_panel_ignores_stale_socket_events_and_token_attachment_respects_open_generation():
    panel = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert "if (socket.value !== client) return" in panel
    assert "openingGeneration?: number" in embed
    assert "openingGeneration !== undefined && openingGeneration !== browserOpenGeneration" in embed
    assert "const openingGeneration = browserOpenGeneration;" in embed
    assert "String(data.session_id || \"\")," in embed
    assert "data.approval_mode," in embed
    assert "openingGeneration," in embed


def test_browser_panel_refreshes_after_ai_browser_action_without_short_polling():
    panel = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert "refreshSignal?: number" in panel
    assert "watch(() => props.refreshSignal" in panel
    assert ":refresh-signal=\"browserRefreshSignal\"" in embed
    assert "data.type === \"browser_refresh\"" in embed


def test_browser_panel_normalizes_protocol_less_navigation_addresses():
    source = (ROOT / "frontend/src/components/embed/BrowserPanel.vue").read_text(encoding="utf-8")

    assert "const normalizeNavigationUrl" in source
    assert "https://${value}" in source
    assert "if (/^https?:\\/\\//i.test(value)) return value;" in source
    assert "const value = normalizeNavigationUrl(address.value);" in source
    assert "address.value = value;" in source
