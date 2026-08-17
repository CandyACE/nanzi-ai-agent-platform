from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure


def test_production_runtime_has_no_legacy_outer_route_protocol():
    production_root = Path(__file__).parents[2] / "app" / "services" / "ai"
    forbidden = (
        "RouteResult",
        "shared_turn",
        "resolve_turn_for_session",
        "route_hints",
    )

    violations = []
    for path in production_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for symbol in forbidden:
            if symbol in text:
                violations.append(f"{path.relative_to(production_root)}: {symbol}")

    assert violations == []
