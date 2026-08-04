from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_skill_platform_endpoints_use_dedicated_element_permission():
    source = (ROOT / "app/api/portal/endpoints/skills.py").read_text(encoding="utf-8")

    assert 'element", "element:skills:admin"' in source
    assert "skill_platform_admin" in source
    assert "skill_publication_reviewer = skill_platform_admin" in source


def test_skill_workbench_exposes_dedicated_element_permission():
    permissions = (ROOT / "frontend/src/constants/permissions.ts").read_text(encoding="utf-8")
    view = (ROOT / "frontend/src/views/SkillsManagement.vue").read_text(encoding="utf-8")

    assert "element:skills:admin" in permissions
    assert "element:skills:admin" in view


def test_skill_admin_permission_is_seeded_for_both_database_dialects():
    mysql = (ROOT / "db-prod/V113-register_skill_admin_permission.sql").read_text(encoding="utf-8")
    postgres = (ROOT / "db-prod-pg/V12-register_skill_admin_permission.sql").read_text(encoding="utf-8")

    assert "element" in mysql and "element:skills:admin" in mysql
    assert "element" in postgres and "element:skills:admin" in postgres


def test_publication_notifications_target_the_dedicated_element_permission():
    source = (ROOT / "app/services/skill_publication_service.py").read_text(encoding="utf-8")

    assert source.count('ResourcePermission.resource_type == "element"') == 2
    assert source.count('ResourcePermission.resource_id == "element:skills:admin"') == 2


def test_skill_publication_service_parses_with_python311():
    python311 = shutil.which("python3.11")
    if not python311:
        pytest.skip("python3.11 is not installed in this environment")

    service_path = ROOT / "app/services/skill_publication_service.py"
    result = subprocess.run(
        [
            python311,
            "-c",
            "from pathlib import Path; import sys; compile(Path(sys.argv[1]).read_text(), sys.argv[1], 'exec')",
            str(service_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
