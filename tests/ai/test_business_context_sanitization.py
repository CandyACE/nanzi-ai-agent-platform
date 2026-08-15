"""Unit tests for the client business-context trust boundary."""

import pytest

from app.services.ai.business_context import sanitize_injected_context


pytestmark = pytest.mark.no_infrastructure


def test_sanitize_injected_context_keeps_business_fields_and_drops_identity_fields():
    result = sanitize_injected_context(
        {
            "device_type": "桌面端(大屏幕)",
            "business_context": {
                "ticket_id": "INC-1001",
                "current_page": "ticket-detail",
                "user_id": "attacker-user",
                "role": "admin",
                "owner": {
                    "tenant_id": "tenant-secret",
                    "permissions": ["admin"],
                    "display_name": "业务负责人",
                },
                "watchers": [{"user_id": "another-user", "label": "观察者"}],
            },
            "user_info": {"user_id": "attacker-user"},
            "user_name": "attacker",
        }
    )

    assert result == {
        "device_type": "桌面端(大屏幕)",
            "business_context": {
                "ticket_id": "INC-1001",
                "current_page": "ticket-detail",
                "owner": {"display_name": "业务负责人"},
                "watchers": [{"label": "观察者"}],
            },
    }


def test_sanitize_injected_context_handles_non_mapping_input():
    assert sanitize_injected_context(None) == {}
    assert sanitize_injected_context("not-a-context") == {}
