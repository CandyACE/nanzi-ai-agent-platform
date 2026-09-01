from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure


def test_platform_logging_format_is_initialized_before_fastmcp_import_chain():
    source = Path("app/main.py").read_text(encoding="utf-8")

    # portal_router imports the MCP endpoint, which imports FastMCP. The
    # platform formatter must win before that import-time configuration runs.
    assert source.index("logging.basicConfig(") < source.index(
        "from app.api.portal.api import portal_router"
    )
    assert "format='%(levelname)s:     %(message)s'" in source
