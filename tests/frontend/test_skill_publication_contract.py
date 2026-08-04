from pathlib import Path


SKILLS_VIEW = Path("frontend/src/views/SkillsManagement.vue")


def _source() -> str:
    return SKILLS_VIEW.read_text(encoding="utf-8")


def test_personal_skill_publication_contract_is_visible():
    source = _source()
    assert "/api/portal/skills/personal/" in source
    assert "/publication-requests" in source
    assert "publication-requests/withdraw" in source
    assert "撤销审核" in source
    assert "提交为平台技能" in source
    assert "提交新版本" in source
    assert "publication_status" in source


def test_admin_review_contract_is_scoped_to_platform_workbench():
    source = _source()
    assert 'id="tab-skill-publication-review"' in source
    assert "待审核" in source
    assert "publicationQueue.length" in source
    assert "发布审核" in source
    assert "approve" in source
    assert "reject" in source
    assert "个人" in source
    assert "平台" in source
    assert "!personalOnly" in source
