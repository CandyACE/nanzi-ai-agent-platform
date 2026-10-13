import pytest
from pydantic import ValidationError


pytestmark = pytest.mark.no_infrastructure


def test_permission_update_normalizes_forbidden_policy_entries():
    from app.schemas.permission import PermissionUpdate

    update = PermissionUpdate(
        forbidden_tools=[" exec_command ", "exec_command", "Bash"],
        forbidden_commands=[" rm ", "RM", "shutdown"],
    )

    assert update.forbidden_tools == ["exec_command", "Bash"]
    assert update.forbidden_commands == ["rm", "shutdown"]


def test_permission_update_rejects_policy_entries_longer_than_storage_limit():
    from app.schemas.permission import PermissionUpdate

    # 上限 255，与 SysApiTool.name / 外部 MCP 工具名的列宽对齐（此前是 100：
    # 一个超长工具名被勾中会让整页权限保存 422，且永远禁不掉）。
    PermissionUpdate(forbidden_commands=["x" * 255])  # 边界值必须放行

    with pytest.raises(ValidationError):
        PermissionUpdate(forbidden_commands=["x" * 256])
