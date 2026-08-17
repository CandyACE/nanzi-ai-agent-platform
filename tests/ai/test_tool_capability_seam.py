from unittest.mock import AsyncMock

import pytest

from app.schemas.agent import ChatConfig
from app.services.ai.runtime.agentscope.tools import RuntimeToolSpec


pytestmark = pytest.mark.no_infrastructure


def _spec(name: str, *, source_type: str = "static", permission_scope: str = "read"):
    return RuntimeToolSpec(
        name=name,
        description=f"{name} description",
        parameters_schema={"type": "object", "properties": {}},
        source_type=source_type,
        callable=lambda **kwargs: name,
        permission_scope=permission_scope,
    )


class FakeProvider:
    def __init__(self, configured_specs):
        self.configured_specs = configured_specs
        self.configured_items = None
        self.implicit_specs = []

    async def resolve_configured(self, items):
        self.configured_items = list(items)
        return list(self.configured_specs)

    def resolve_implicit(self, tool):
        return tool


@pytest.mark.asyncio
async def test_registry_provider_resolves_named_implicit_tool_for_runner():
    from app.services.ai.tool_capability import RegistryToolProvider

    class LegacyTool:
        name = "sub_agent_call"
        description = "delegate"

    class FakeRegistry:
        @classmethod
        async def get_tool(cls, name):
            assert name == "sub_agent_call"
            return LegacyTool()

        @staticmethod
        def _attach_evidence_metadata(name, spec):
            return spec

    provider = RegistryToolProvider(registry=FakeRegistry)

    tool = await provider.get_implicit_tool("sub_agent_call")

    assert tool.name == "sub_agent_call"


@pytest.mark.asyncio
async def test_registry_provider_resolves_batch_delegation_tool():
    from app.services.ai.tool_capability import RegistryToolProvider

    class LegacyTool:
        name = "sub_agent_batch_call"
        description = "batch delegate"

    class FakeRegistry:
        @classmethod
        async def get_tool(cls, name):
            assert name == "sub_agent_batch_call"
            return LegacyTool()

        @staticmethod
        def _attach_evidence_metadata(name, spec):
            return spec

    provider = RegistryToolProvider(registry=FakeRegistry)

    tool = await provider.get_implicit_tool("sub_agent_batch_call")

    assert tool.name == "sub_agent_batch_call"


@pytest.mark.asyncio
async def test_registry_provider_resolves_todo_tool():
    from app.services.ai.tool_capability import RegistryToolProvider

    class LegacyTool:
        name = "todo_write"
        description = "task list"
        is_read_only = True

    class FakeRegistry:
        @classmethod
        async def get_tool(cls, name):
            assert name == "todo_write"
            return LegacyTool()

        @staticmethod
        def _attach_evidence_metadata(name, spec):
            return spec

    provider = RegistryToolProvider(registry=FakeRegistry)

    tool = await provider.get_implicit_tool("todo_write")

    assert tool.name == "todo_write"


@pytest.mark.asyncio
async def test_assistant_resolves_main_subagent_through_provider(monkeypatch):
    from app.services.ai.runners.assistant_agent_runner import AssistantAgentRunner

    class LegacyTool:
        name = "sub_agent_call"
        description = "delegate"

        async def __call__(self, **kwargs):
            return "delegated"

    runner = AssistantAgentRunner(
        config=ChatConfig(
            agent_id="general-agent-id",
            agent_name="GeneralAgent",
            model_name="test",
            temperature=0.0,
            system_prompt="general",
            tools=[],
        ),
        trace_id="trace-capability-provider",
        trace_buffer=[],
    )
    class BatchLegacyTool(LegacyTool):
        name = "sub_agent_batch_call"

    class TodoLegacyTool(LegacyTool):
        name = "todo_write"

    async def lookup(name):
        if name == "sub_agent_call":
            return LegacyTool()
        if name == "sub_agent_batch_call":
            return BatchLegacyTool()
        return TodoLegacyTool()

    provider_lookup = AsyncMock(side_effect=lookup)

    registry_lookup = AsyncMock(side_effect=AssertionError("runner called ToolRegistry directly"))
    monkeypatch.setattr(
        "app.services.ai.runners.assistant_agent_runner.RegistryToolProvider.get_implicit_tool",
        provider_lookup,
    )
    monkeypatch.setattr(
        "app.services.ai.runners.assistant_agent_runner.ToolRegistry.get_tool",
        registry_lookup,
    )
    monkeypatch.setattr(
        "app.services.ai.runners.assistant_agent_runner.ToolRegistry.get_system_implicit_tools",
        lambda: [],
    )
    monkeypatch.setattr(
        "app.services.ai.runners.assistant_agent_runner.is_main_general_agent",
        lambda config: True,
    )

    tools = await runner._resolve_runtime_tools_from_config()

    assert [call.args[0] for call in provider_lookup.await_args_list] == [
        "sub_agent_call",
        "sub_agent_batch_call",
        "todo_write",
    ]
    assert [tool.name for tool in tools] == [
        "sub_agent_call",
        "sub_agent_batch_call",
        "todo_write",
    ]


@pytest.mark.asyncio
async def test_resolver_skips_disabled_items_preserves_order_and_deduplicates_implicit_tools():
    from app.services.ai.tool_capability import resolve_tool_capabilities

    provider = FakeProvider([_spec("first"), _spec("second")])
    implicit = [_spec("second", source_type="system"), _spec("implicit", source_type="system")]

    resolved = await resolve_tool_capabilities(
        [{"name": "first", "enabled": True}, {"name": "disabled", "enabled": False}],
        implicit_tools=implicit,
        provider=provider,
    )

    assert provider.configured_items == [{"name": "first", "enabled": True}]
    assert list(resolved.names) == ["first", "second", "implicit"]
    assert list(resolved.specs) == provider.configured_specs + [implicit[1]]
    assert resolved.diagnostics[0].status == "disabled"
    assert resolved.diagnostics[0].name == "disabled"


@pytest.mark.asyncio
async def test_resolver_applies_one_allowlist_to_visible_and_executable_specs():
    from app.services.ai.tool_capability import resolve_tool_capabilities

    resolved = await resolve_tool_capabilities(
        ["allowed", "hidden"],
        provider=FakeProvider([_spec("allowed"), _spec("hidden")]),
        allowed_names=["allowed"],
    )

    assert list(resolved.names) == ["allowed"]
    assert [spec.name for spec in resolved.specs] == ["allowed"]
    assert [(item.name, item.status) for item in resolved.diagnostics] == [("hidden", "filtered")]


@pytest.mark.asyncio
async def test_resolver_reports_context_allowlist_filtering(monkeypatch):
    from app.services.ai.tool_capability import resolve_tool_capabilities

    class Context:
        delegation_tool_filter = ["allowed"]

    monkeypatch.setattr(
        "app.core.context.get_current_agent_context",
        lambda: Context(),
    )

    resolved = await resolve_tool_capabilities(
        ["allowed", "hidden"],
        provider=FakeProvider([_spec("allowed"), _spec("hidden")]),
    )

    assert list(resolved.names) == ["allowed"]
    assert [(item.name, item.status) for item in resolved.diagnostics] == [
        ("hidden", "filtered")
    ]


@pytest.mark.asyncio
async def test_resolver_reports_missing_required_tools_without_silent_fallback():
    from app.services.ai.tool_capability import resolve_tool_capabilities

    resolved = await resolve_tool_capabilities(
        ["available"],
        required_names=["available", "required_but_missing"],
        provider=FakeProvider([_spec("available")]),
    )

    assert resolved.missing_required == ("required_but_missing",)
    assert list(resolved.names) == ["available"]
    assert [(item.name, item.status) for item in resolved.diagnostics] == [
        ("required_but_missing", "missing")
    ]


@pytest.mark.asyncio
async def test_definition_and_consumer_use_resolved_runtime_spec():
    from app.services.ai.tool_capability import AgentScopeToolConsumer, resolve_tool_capabilities

    resolved = await resolve_tool_capabilities(
        ["search_knowledge_base"],
        provider=FakeProvider([_spec("search_knowledge_base")]),
    )
    captured = {}

    def fake_builder(specs, **kwargs):
        captured["specs"] = specs
        captured["kwargs"] = kwargs
        return "toolkit"

    toolkit = AgentScopeToolConsumer(fake_builder).consume(
        resolved,
        approval_mode="allow",
        user_id=7,
    )

    assert toolkit == "toolkit"
    assert captured["specs"] == list(resolved.specs)
    assert resolved.bindings[0].definition.name == "search_knowledge_base"
    assert resolved.bindings[0].definition.source_type == "static"
    assert resolved.bindings[0].definition.permission_scope == "read"
    assert resolved.bindings[0].definition.capability == "knowledge_search"
    assert resolved.bindings[0].definition.execution_policy == "runtime_checked"


@pytest.mark.asyncio
async def test_tool_resolution_diagnostics_are_safe_timeline_events():
    from app.services.ai.tool_capability import (
        build_tool_resolution_log_events,
        resolve_tool_capabilities,
    )

    resolved = await resolve_tool_capabilities(
        ["available", {"name": "disabled", "enabled": False}],
        required_names=["required_but_missing"],
        allowed_names=["available"],
        provider=FakeProvider([_spec("available")]),
    )

    events = build_tool_resolution_log_events(resolved)

    assert [(event["tool_name"], event["resolution_status"], event["status"]) for event in events] == [
        ("disabled", "disabled", "warning"),
        ("required_but_missing", "missing", "error"),
    ]
    assert all(event["type"] == "log" for event in events)
    assert all(event["category"] == "tool_resolution" for event in events)
    assert all("callable" not in event and "args" not in event for event in events)
