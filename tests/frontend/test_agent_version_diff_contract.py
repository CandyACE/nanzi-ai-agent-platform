from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def test_version_drawer_compares_non_published_versions_with_current_online_version():
    source = (ROOT / "frontend/src/components/agent/AgentVersionsDrawer.vue").read_text(encoding="utf-8")

    assert "const publishedVersion = computed" in source
    assert "getAgentVersionDiffPair" in source
    assert "status === 'PUBLISHED'" in source
    assert "const openDiff = (version: AIAgentVersion) =>" in source
    assert '@click="openDiff(v)"' in source
    assert "v.status !== 'PUBLISHED'" in source
    assert 'title="与当前线上版本对比"' in source
    assert "Diff" in source
    assert ':source-version="diffVersion"' in source
    assert ':published-version="publishedVersion"' in source


def test_version_diff_modal_is_read_only_and_shows_runtime_config_groups():
    source = (ROOT / "frontend/src/components/agent/AgentVersionDiffModal.vue").read_text(encoding="utf-8")
    helper = (ROOT / "frontend/src/utils/agentVersionDiff.ts").read_text(encoding="utf-8")

    for label in ("版本 Diff", "模型策略", "工具", "Skills", "系统提示词", "欢迎语配置"):
        assert label in source or label in helper
    assert 'v-for="group in visibleGroups"' in source
    assert "只读" in source
    assert "buildAgentVersionDiff" in source
    assert "v-model" not in source
    assert '@click="save"' not in source


def test_version_diff_modal_can_show_only_changed_items():
    source = (ROOT / "frontend/src/components/agent/AgentVersionDiffModal.vue").read_text(encoding="utf-8")
    helper = (ROOT / "frontend/src/utils/agentVersionDiff.ts").read_text(encoding="utf-8")

    assert "showOnlyChanges" in source
    assert "仅显示变化" in source
    assert "visibleGroups" in source
    assert "filterAgentVersionDiffGroups" in source
    assert "items.filter((item) => item.changed)" in helper
    assert "当前版本与线上版本一致" in source
    assert "peer-focus-visible:ring-2" in source
