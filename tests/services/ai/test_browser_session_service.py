import asyncio

import pytest

from app.models.browser import BrowserProfile, BrowserSession
from app.services.ai.browser.browser_session_service import (
    BrowserAccessDenied,
    BrowserSessionService,
)


pytestmark = pytest.mark.no_infrastructure


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class InMemorySession:
    def __init__(self):
        self.rows = []
        self.commit_count = 0

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        rows = [row for row in self.rows if isinstance(row, entity)]
        for criterion in statement._where_criteria:
            rows = [row for row in rows if self._matches(row, criterion)]
        return FakeResult(rows)

    @staticmethod
    def _matches(row, criterion):
        if hasattr(criterion, "clauses"):
            return all(InMemorySession._matches(row, item) for item in criterion.clauses)
        key = getattr(criterion.left, "key", None)
        value = getattr(criterion.right, "value", None)
        if getattr(criterion.operator, "__name__", "") == "in_op":
            return getattr(row, key, object()) in value
        return getattr(row, key, object()) == value

    def add(self, row):
        self.rows.append(row)

    async def flush(self):
        return None

    async def commit(self):
        self.commit_count += 1


class RacingSession(InMemorySession):
    def __init__(self):
        super().__init__()
        self._browser_query_count = 0
        self._second_browser_query = asyncio.Event()

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        result = await super().execute(statement)
        if entity is BrowserSession:
            self._browser_query_count += 1
            if self._browser_query_count == 1:
                try:
                    await asyncio.wait_for(self._second_browser_query.wait(), timeout=0.05)
                except asyncio.TimeoutError:
                    pass
            elif self._browser_query_count == 2:
                self._second_browser_query.set()
        return result


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_session():
    db = InMemorySession()
    service = BrowserSessionService(
        db,
        profile_root="/tmp/nanzi-browser-test",
        url_validator=lambda url: url,
    )

    owned = await service.open_or_resume(
        user_id=1001,
        conversation_id="conv-a",
        url="https://www.baidu.com/",
        profile_id=None,
    )

    with pytest.raises(BrowserAccessDenied):
        await service.get_owned_session(user_id=2002, session_id=owned.id)


@pytest.mark.asyncio
async def test_open_new_session_defaults_to_autopilot_and_reuse_preserves_mode():
    db = InMemorySession()
    service = BrowserSessionService(
        db,
        profile_root="/tmp/nanzi-browser-test",
        url_validator=lambda url: url,
    )

    first = await service.open_or_resume(
        user_id=1001,
        conversation_id="conv-a",
        url="https://www.baidu.com/",
        profile_id=None,
    )
    assert first.approval_mode == "autopilot"
    first.approval_mode = "guarded"
    second = await service.open_or_resume(
        user_id=1001,
        conversation_id="conv-b",
        url="https://www.baidu.com/",
        profile_id=None,
    )

    assert second.profile_id == first.profile_id
    assert second.id == first.id
    assert second.attached_conversation_id == "conv-b"
    assert second.approval_mode == "guarded"


@pytest.mark.asyncio
async def test_concurrent_open_reuses_one_active_session_for_a_profile():
    db = RacingSession()
    profile = BrowserProfile(
        id="profile-1",
        user_id=1001,
        display_name="默认浏览器",
        encrypted_storage_ref="browser://profiles/profile-1",
        status="active",
    )
    db.add(profile)
    service = BrowserSessionService(
        db,
        profile_root="/tmp/nanzi-browser-test",
        url_validator=lambda url: url,
    )

    sessions = await asyncio.gather(
        service.open_or_resume(
            user_id=1001,
            conversation_id="conv-a",
            url="https://www.baidu.com/",
            profile_id="profile-1",
        ),
        service.open_or_resume(
            user_id=1001,
            conversation_id="conv-b",
            url="https://www.baidu.com/",
            profile_id="profile-1",
        ),
    )

    assert sessions[0].id == sessions[1].id
    assert len([row for row in db.rows if isinstance(row, BrowserSession)]) == 1


@pytest.mark.asyncio
async def test_viewer_token_is_opaque_and_resolves_to_owned_session():
    db = InMemorySession()
    service = BrowserSessionService(
        db,
        profile_root="/tmp/nanzi-browser-test",
        url_validator=lambda url: url,
    )
    session = await service.open_or_resume(
        user_id=1001,
        conversation_id="conv-a",
        url="https://www.baidu.com/",
        profile_id=None,
    )

    token, expires_at = await service.issue_viewer_token(user_id=1001, session_id=session.id)
    resolved = await service.resolve_viewer_token(token)

    assert token
    assert expires_at > session.created_at
    assert resolved.id == session.id
    assert token != session.viewer_token_hash


@pytest.mark.asyncio
async def test_update_state_persists_latest_page_information_for_owned_session():
    db = InMemorySession()
    service = BrowserSessionService(
        db,
        profile_root="/tmp/nanzi-browser-test",
        url_validator=lambda url: url,
    )
    session = await service.open_or_resume(
        user_id=1001,
        conversation_id="conv-a",
        url="https://www.baidu.com/",
        profile_id=None,
    )
    old_last_seen = session.last_seen_at

    updated = await service.update_state(
        user_id=1001,
        session_id=session.id,
        url="https://www.baidu.com/s?wd=test",
        title="百度一下",
    )

    assert updated is session
    assert session.current_url == "https://www.baidu.com/s?wd=test"
    assert session.page_title == "百度一下"
    assert session.last_seen_at >= old_last_seen
    assert session.updated_at >= old_last_seen


@pytest.mark.asyncio
async def test_update_state_rejects_session_owned_by_another_user():
    db = InMemorySession()
    service = BrowserSessionService(
        db,
        profile_root="/tmp/nanzi-browser-test",
        url_validator=lambda url: url,
    )
    session = await service.open_or_resume(
        user_id=1001,
        conversation_id="conv-a",
        url="https://www.baidu.com/",
        profile_id=None,
    )

    with pytest.raises(BrowserAccessDenied):
        await service.update_state(
            user_id=2002,
            session_id=session.id,
            url="https://evil.example/",
            title="不应写入",
        )
