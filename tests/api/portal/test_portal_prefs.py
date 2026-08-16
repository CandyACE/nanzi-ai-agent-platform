"""Portal preference routing fields are persisted per user without overwriting other prefs."""

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.portal.endpoints import portal_prefs


pytestmark = pytest.mark.no_infrastructure


class FakeRedis:
    def __init__(self, value=None):
        self.value = value
        self.saved = None

    async def get(self, _key):
        return self.value

    async def set(self, _key, value):
        self.saved = value
        self.value = value


def user_info(user_id=7, role="user"):
    return {"user_id": user_id, "role": role}


@pytest.mark.asyncio
async def test_get_portal_prefs_defaults_to_auto_routing(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(portal_prefs, "get_redis", lambda: _resolved(redis))

    result = await portal_prefs.get_portal_prefs(user_info())

    assert result["data"]["routing_mode"] == "auto"
    assert result["data"]["expert_agent_id"] == ""
    assert result["data"]["routing_configured"] is False


@pytest.mark.asyncio
async def test_update_routing_prefs_preserves_other_fields(monkeypatch):
    redis = FakeRedis(
        json.dumps(
            {
                "pinned_group_ids": ["group-1"],
                "markdown_theme": "academic",
            }
        )
    )
    monkeypatch.setattr(portal_prefs, "get_redis", lambda: _resolved(redis))
    monkeypatch.setattr(
        portal_prefs.AgentManagerService,
        "resolve_embed_agent_access",
        _resolved_agent,
    )
    monkeypatch.setattr(
        portal_prefs.AgentManagerService,
        "get_active_agent_config",
        _resolved_agent_config,
    )

    result = await portal_prefs.update_routing_prefs(
        portal_prefs.RoutingPreferenceUpdate(
            routing_mode="expert",
            expert_agent_id="agent-1",
        ),
        session=object(),
        user_info=user_info(),
    )

    saved = json.loads(redis.saved)
    assert result["data"] == {
        "routing_mode": "expert",
        "expert_agent_id": "agent-1",
    }
    assert saved["pinned_group_ids"] == ["group-1"]
    assert saved["markdown_theme"] == "academic"
    assert saved["routing_mode"] == "expert"
    assert saved["expert_agent_id"] == "agent-1"
    assert saved["routing_configured"] is True


@pytest.mark.asyncio
async def test_update_auto_routing_clears_expert_agent_id(monkeypatch):
    redis = FakeRedis(json.dumps({"expert_agent_id": "old-agent"}))
    monkeypatch.setattr(portal_prefs, "get_redis", lambda: _resolved(redis))

    result = await portal_prefs.update_routing_prefs(
        portal_prefs.RoutingPreferenceUpdate(routing_mode="auto"),
        session=object(),
        user_info=user_info(),
    )

    saved = json.loads(redis.saved)
    assert result["data"]["routing_mode"] == "auto"
    assert result["data"]["expert_agent_id"] == ""
    assert saved["expert_agent_id"] == ""


@pytest.mark.asyncio
async def test_legacy_full_preference_update_does_not_wipe_routing(monkeypatch):
    redis = FakeRedis(
        json.dumps(
            {
                "routing_mode": "expert",
                "expert_agent_id": "agent-1",
                "markdown_theme": "academic",
            }
        )
    )
    monkeypatch.setattr(portal_prefs, "get_redis", lambda: _resolved(redis))

    await portal_prefs.update_portal_prefs(
        portal_prefs.PortalPrefsUpdate(
            pinned_group_ids=["group-2"],
        ),
        user_info(),
    )

    saved = json.loads(redis.saved)
    assert saved["routing_mode"] == "expert"
    assert saved["expert_agent_id"] == "agent-1"


@pytest.mark.asyncio
async def test_full_preference_update_cannot_bypass_routing_access_check(monkeypatch):
    redis = FakeRedis(json.dumps({"routing_mode": "auto", "expert_agent_id": ""}))
    monkeypatch.setattr(portal_prefs, "get_redis", lambda: _resolved(redis))

    await portal_prefs.update_portal_prefs(
        portal_prefs.PortalPrefsUpdate.model_validate(
            {
                "routing_mode": "expert",
                "expert_agent_id": "private-agent",
            }
        ),
        user_info(),
    )

    saved = json.loads(redis.saved)
    assert saved["routing_mode"] == "auto"
    assert saved["expert_agent_id"] == ""


def test_routing_preference_model_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        portal_prefs.RoutingPreferenceUpdate(routing_mode="invalid")


@pytest.mark.asyncio
async def test_update_expert_routing_requires_agent_id(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(portal_prefs, "get_redis", lambda: _resolved(redis))

    with pytest.raises(HTTPException) as exc_info:
        await portal_prefs.update_routing_prefs(
            portal_prefs.RoutingPreferenceUpdate(
                routing_mode="expert",
                expert_agent_id="",
            ),
            session=object(),
            user_info=user_info(),
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_expert_routing_rejects_forbidden_agent(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(portal_prefs, "get_redis", lambda: _resolved(redis))

    async def forbidden(*_args, **_kwargs):
        raise PermissionError("agent_forbidden")

    monkeypatch.setattr(
        portal_prefs.AgentManagerService,
        "resolve_embed_agent_access",
        forbidden,
    )

    with pytest.raises(HTTPException) as exc_info:
        await portal_prefs.update_routing_prefs(
            portal_prefs.RoutingPreferenceUpdate(
                routing_mode="expert",
                expert_agent_id="private-agent",
            ),
            session=object(),
            user_info=user_info(),
        )

    assert exc_info.value.status_code == 403
    assert redis.saved is None


async def _resolved(value):
    return value


async def _resolved_agent(*_args, **_kwargs):
    return SimpleNamespace(id="agent-1")


async def _resolved_agent_config(*_args, **_kwargs):
    return SimpleNamespace(agent_id="agent-1")
