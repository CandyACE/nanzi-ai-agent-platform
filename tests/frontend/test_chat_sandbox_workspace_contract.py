from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
EMBED = ROOT / "frontend/src/views/EmbedChat.vue"
BANNER = ROOT / "frontend/src/components/chat/DockerWorkspaceBanner.vue"


def test_docker_workspace_banner_has_start_running_and_retry_states():
    source = BANNER.read_text(encoding="utf-8")
    assert "启动我的 Docker 沙箱" in source
    assert "重试启动" in source
    assert "Docker 沙箱容器已运行" in source
    assert "Docker 沙箱容器启动中" in source
    assert "workspaceStatus" in source
    assert "defineEmits" in source
    assert "关闭 Docker 沙箱提示" in source
    assert '(event: "close")' in source


def test_embed_chat_places_workspace_action_in_banner_and_calls_ensure_api():
    source = EMBED.read_text(encoding="utf-8")
    assert 'import DockerWorkspaceBanner from "@/components/chat/DockerWorkspaceBanner.vue"' in source
    assert "/api/v1/sandbox/docker/workspace/ensure" in source
    assert "effectiveSandboxPolicy" in source
    assert 'effectiveSandboxPolicy.value === "docker"' in source
    assert "<DockerWorkspaceBanner" in source
    assert "#banner" in source
    assert "conversation_id" in source
    assert "/api/v1/sandbox/docker/workspace/status" in source
    assert '@close="dismissDockerWorkspaceBanner"' in source


def test_embed_chat_does_not_render_workspace_action_for_non_docker_policy():
    source = EMBED.read_text(encoding="utf-8")
    control_pos = source.find("<DockerWorkspaceBanner")
    assert control_pos != -1
    control_block = source[control_pos : control_pos + 700]
    assert "showDockerWorkspaceControl" in control_block
    assert "effectiveSandboxPolicy.value === \"docker\"" in source


CHAT_INPUT = ROOT / "frontend/src/components/embed/ChatInput.vue"


def test_embed_chat_persists_banner_dismiss_and_auto_hides_when_running():
    source = EMBED.read_text(encoding="utf-8")
    assert "nanzi_dismissed_docker_workspace_banner" in source
    assert "readDockerWorkspaceBannerDismissed" in source
    assert "dockerWorkspaceStatusLoaded" in source
    assert 'dockerWorkspaceStatus.value === "running"' in source
    assert 'dockerWorkspaceStatus.value === "error"' in source
    assert 'name="bash-banner-fade"' in source



def test_chat_input_context_modal_renders_docker_workspace_status_and_actions():
    chat_input_source = CHAT_INPUT.read_text(encoding="utf-8")
    assert "dockerWorkspaceStatus" in chat_input_source
    assert "dockerWorkspaceContainerId" in chat_input_source
    assert "isDockerSandboxPolicy" in chat_input_source
    assert "start-docker-workspace" in chat_input_source
    assert "refresh-docker-workspace" in chat_input_source
    assert "容器已运行" in chat_input_source
    assert "容器未启动" in chat_input_source
    assert "启动容器" in chat_input_source
    assert "重试启动" in chat_input_source

    # 验证在展开详情面板时静默触发 Docker 沙箱状态刷新
    assert "if (isDockerSandboxPolicy.value) {" in chat_input_source
    assert "emit('refresh-docker-workspace', false);" in chat_input_source

    assert "dockerWorkspaceStartedAt" in chat_input_source
    assert "dockerWorkspaceUptimeSeconds" in chat_input_source
    assert "dockerUptimeFormatted" in chat_input_source
    assert "运行时长：" in chat_input_source
    assert "空闲 30m 自动回收" in chat_input_source

    embed_source = EMBED.read_text(encoding="utf-8")
    assert ':docker-workspace-status="dockerWorkspaceStatus"' in embed_source
    assert ':docker-workspace-container-id="dockerWorkspaceContainerId"' in embed_source
    assert ':docker-workspace-started-at="dockerWorkspaceStartedAt"' in embed_source
    assert ':docker-workspace-uptime-seconds="dockerWorkspaceUptimeSeconds"' in embed_source
    assert '@start-docker-workspace="ensureDockerWorkspace"' in embed_source
    assert '@refresh-docker-workspace="refreshDockerWorkspaceStatus"' in embed_source


