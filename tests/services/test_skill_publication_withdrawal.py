from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.skill_publication_service import withdraw_personal_skill_publication


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_withdraw_personal_skill_publication_marks_pending_version_withdrawn():
    publication = SimpleNamespace(
        id="publication-1",
        source_user_id=7,
        source_personal_skill_id="demo",
        platform_skill_id=None,
        name="演示技能",
        description="desc",
        status="PENDING",
        current_version=None,
        updated_at=None,
    )
    version = SimpleNamespace(
        id="version-1",
        publication_id="publication-1",
        version_number=1,
        status="PENDING",
        content_sha256="abc",
        review_comment=None,
        withdrawn_by=None,
        withdrawn_at=None,
    )
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(first=lambda: (version, publication))

    result = await withdraw_personal_skill_publication(
        session,
        user={"user_id": 7},
        skill_id="demo",
    )

    assert version.status == "WITHDRAWN"
    assert version.withdrawn_by == 7
    assert isinstance(version.withdrawn_at, datetime)
    assert publication.status == "UNPUBLISHED"
    assert result["publication_status"] == "WITHDRAWN"
    assert result["version_status"] == "WITHDRAWN"
    session.flush.assert_awaited_once()
