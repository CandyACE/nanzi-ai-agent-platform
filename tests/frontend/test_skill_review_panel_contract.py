"""审核面板必须能看到技能包内的全部文件。

回归背景：文案（SkillsManagement.vue 帮助弹窗）承诺「管理员在『待审核』Tab 下
审查文件 Diff 与代码合规性」，而后端 ``GET /skills/publication-requests/{id}``
早已从**提交快照**下发 ``file_tree``，前端却只渲染了 ``skill_md_content``——
``scripts/`` 里的可执行代码在无人查看的情况下就能被批准进入公共技能库。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANAGEMENT = ROOT / "frontend" / "src" / "views" / "SkillsManagement.vue"
ENDPOINT = ROOT / "app" / "api" / "portal" / "endpoints" / "skills.py"
SERVICE = ROOT / "app" / "services" / "skill_publication_service.py"


def test_review_panel_renders_file_tree_from_snapshot():
    text = MANAGEMENT.read_text(encoding="utf-8")
    assert "activePublicationReview.file_tree" in text
    assert 'SkillFileTree' in text
    # 选中文件后必须能打开内容，而不只是列个名字
    assert "@select-file=\"openPublicationReviewFile\"" in text
    assert "const openPublicationReviewFile" in text


def test_review_panel_file_preview_hits_snapshot_endpoint():
    text = MANAGEMENT.read_text(encoding="utf-8")
    assert "/publication-requests/${review.version_id}/file" in text


def test_backend_exposes_snapshot_file_endpoint_with_guard():
    text = ENDPOINT.read_text(encoding="utf-8")
    # 路由必须在 `/{skill_id}` 之前注册，否则会被通配路由吃掉
    assert '@router.get("/publication-requests/{version_id}/file"' in text
    assert "skill_publication_reviewer" in text
    assert "read_snapshot_text_file" in text
    assert text.index('"/publication-requests/{version_id}/file"') < text.index('@router.get("/{skill_id}"')


def test_snapshot_reader_rejects_escape_and_binary():
    text = SERVICE.read_text(encoding="utf-8")
    assert "def resolve_snapshot_file" in text
    assert "os.path.realpath" in text
    assert "SNAPSHOT_PREVIEW_EXTENSIONS" in text
    assert "SNAPSHOT_PREVIEW_MAX_BYTES" in text
    # 可执行脚本必须在允许预览的扩展名里，否则「审查代码」依旧做不到
    assert '".py"' in text and '".sh"' in text
