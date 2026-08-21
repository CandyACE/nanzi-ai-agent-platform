import pytest
from fastapi import HTTPException


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_update_system_configs_rejects_docker_policy_in_container(monkeypatch):
    from app.api.portal.endpoints.system import (
        ConfigItem,
        ConfigUpdateRequest,
        update_system_configs,
    )

    async def reject_update(*_args, **_kwargs):
        raise ValueError(
            "平台后端运行在 Docker 容器内，不能启用 docker 沙箱策略"
        )

    monkeypatch.setattr(
        "app.api.portal.endpoints.system.ConfigService.bulk_update",
        reject_update,
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_system_configs(
            ConfigUpdateRequest(
                updates=[ConfigItem(key="sandbox_policy", value="docker")]
            ),
            user={"user_name": "admin"},
        )

    assert exc_info.value.status_code == 400
    assert "不能启用 docker 沙箱策略" in str(exc_info.value.detail)
