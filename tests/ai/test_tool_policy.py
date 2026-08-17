import pytest
from types import SimpleNamespace

from app.services.ai.tool_policy import ToolMetadata, resolve_tool_metadata


pytestmark = pytest.mark.no_infrastructure


def test_known_tool_metadata_describes_capability_without_granting_permission():
    metadata = resolve_tool_metadata(SimpleNamespace(name="execute_sql_query"))

    assert metadata.capability == "data_query"
    assert metadata.source == "internal_structured_data"
    assert metadata.confirmation == "policy"
    assert metadata.to_dict()["nudge_mode"] == "evidence"


def test_unknown_tool_metadata_is_neutral():
    metadata = resolve_tool_metadata(SimpleNamespace(name="new_tool"))

    assert metadata == ToolMetadata()
    assert metadata.to_dict()["capability"] == "unknown"
