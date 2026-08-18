import pytest

from app.models.browser import BrowserProfile, BrowserSession
from app.services.ai.browser.browser_profile_service import BrowserProfileService


pytestmark = pytest.mark.no_infrastructure


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class InMemorySession:
    def __init__(self):
        self.rows = []

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
        return getattr(row, key, object()) == value

    def add(self, row):
        self.rows.append(row)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_get_or_create_default_reuses_user_profile():
    db = InMemorySession()
    service = BrowserProfileService(db, profile_root="/tmp/nanzi-browser-test")

    first = await service.get_or_create_default(user_id=1001)
    second = await service.get_or_create_default(user_id=1001)

    assert second.id == first.id
    assert second.user_id == 1001
    assert second.encrypted_storage_ref.startswith("browser://profiles/")
    assert await service.profile_path(second) == f"/tmp/nanzi-browser-test/1001/{first.id}"

