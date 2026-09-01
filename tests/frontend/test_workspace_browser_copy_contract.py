from pathlib import Path


ROOT = Path(__file__).parents[2]
WORKSPACE_DRAWER = ROOT / "frontend/src/components/embed/WorkspaceBrowserDrawer.vue"


def test_upload_directory_entry_uses_user_facing_label():
    source = WORKSPACE_DRAWER.read_text(encoding="utf-8")

    assert "key: 'uploads', label: '上传目录'" in source
    assert "key: 'uploads', label: 'uploads'" not in source
