from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_theme_composable_persists_and_applies_document_theme():
    source = _read("frontend/src/composables/useAppTheme.ts")

    assert '"nanzi_app_theme"' in source
    assert '"light"' in source
    assert '"dark"' in source
    assert 'ref<AppTheme>("dark")' in source
    assert 'storedTheme === "light" ? "light" : "dark"' in source
    assert "document.documentElement.dataset.theme" in source
    assert "document.documentElement.classList.toggle" not in source
    assert "localStorage.setItem" in source
    assert "setTheme" in source


def test_dashboard_exposes_light_dark_sidebar_switcher():
    source = _read("frontend/src/views/Dashboard.vue")

    assert "useAppTheme" in source
    assert "theme" in source
    assert "亮色" in source
    assert "暗色" in source
    assert 'aria-label="切换界面主题"' in source
    assert "theme === 'light'" in source
    assert "toggleTheme" in source
    assert "border-gray-700 bg-gray-900 text-blue-300" not in source
    assert "inline-flex h-9 w-9 items-center justify-center rounded-lg border transition-colors" not in source
    assert "relative p-2 rounded-lg text-gray-500 hover:bg-gray-100" in source
    assert '<svg v-else class="h-4 w-4" fill="none" stroke="currentColor"' in source
    assert "<!-- Theme Switcher -->" not in source
    assert source.index("<!-- Top Header -->") < source.index('aria-label="切换界面主题"')
    assert "flex-shrink-0 dark:bg-gray-900 dark:border-gray-800" not in source
    assert "bg-gray-100 dark:bg-gray-950 custom-scrollbar" not in source
    assert "bg-sidebar" in source
