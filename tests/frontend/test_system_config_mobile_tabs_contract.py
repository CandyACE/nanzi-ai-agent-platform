"""Contract: SystemConfig tabs remain readable on mobile (no vertical character wrap)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_CONFIG = ROOT / "frontend" / "src" / "views" / "SystemConfig.vue"


def test_system_config_tabs_are_horizontally_scrollable_on_mobile():
    text = SYSTEM_CONFIG.read_text(encoding="utf-8")
    assert "系统配置与诊断" in text
    assert "overflow-x-auto" in text
    assert "whitespace-nowrap" in text
    assert "shrink-0" in text
    assert "flex-col gap-3" in text
    # 不再把标题与全部 Tab 挤在同一行导致窄屏竖排字
    assert "flex justify-between items-center flex-shrink-0" not in text
    for label in ("模型管理", "工具管理", "参数配置", "品牌个性化", "系统诊断", "日志管理"):
        assert label in text
