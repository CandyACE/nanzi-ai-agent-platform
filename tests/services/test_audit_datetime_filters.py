from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.sqltypes import DateTime

from app.api.portal.endpoints.audit import _normalize_audit_datetime
from app.models.audit import AccessLog


pytestmark = pytest.mark.no_infrastructure


def test_normalize_audit_datetime_returns_naive_database_datetime():
    value = datetime(2026, 4, 28, 17, 26, 49, tzinfo=timezone.utc)

    normalized = _normalize_audit_datetime(value)

    assert normalized is not None
    assert normalized.tzinfo is None


def test_audit_datetime_filter_binds_as_timestamp_for_postgresql():
    value = _normalize_audit_datetime(datetime(2026, 4, 28, 17, 26, 49))
    statement = select(AccessLog).where(AccessLog.created_at >= value)

    compiled = statement.compile(dialect=postgresql.dialect())

    assert any(isinstance(bind.type, DateTime) for bind in compiled.binds.values())
