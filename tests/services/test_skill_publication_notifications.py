from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.skill_publication_service import notify_skill_publication_reviewers


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_notify_skill_publication_reviewers_creates_inbox_messages_for_reviewers():
    create_notification = AsyncMock()
    publication = SimpleNamespace(id="publication-1", name="日志分析")
    version = SimpleNamespace(id="version-1", version_number=2)

    with patch(
        "app.services.skill_publication_service._skill_publication_reviewer_ids",
        new=AsyncMock(return_value=[1, 2]),
    ), patch(
        "app.services.skill_publication_service.PortalNotificationService.create",
        new=create_notification,
    ):
        await notify_skill_publication_reviewers(
            AsyncMock(),
            publication=publication,
            version=version,
            submitted_by={"user_id": 7, "user_name": "alice"},
        )

    assert create_notification.await_count == 2
    first_call = create_notification.await_args_list[0].kwargs
    assert first_call["user_id"] == 1
    assert first_call["title"] == "技能发布待审核：日志分析"
    assert "alice" in first_call["content"]
    assert "v2" in first_call["content"]
    assert first_call["category"] == "skill_publication"
    assert first_call["resource_type"] == "skill_publication"
    assert first_call["resource_id"] == "version-1"
    assert first_call["metadata"] == {
        "action": "open_skill_publication_review",
        "publication_id": "publication-1",
        "version_id": "version-1",
        "version_number": 2,
    }
