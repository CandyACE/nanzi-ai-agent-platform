"""Unified tool capability resolution for AgentScope runtimes.

The module separates registry lookup from runtime-tool consumption while
keeping the existing tool configuration and invocation contracts intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Protocol, Sequence
from uuid import uuid4

from app.services.ai.runtime.agentscope.tools import (
    RuntimePermissionScope,
    RuntimeToolSpec,
    ToolSourceType,
    apply_delegation_tool_filter,
    build_toolkit,
    runtime_tool_spec_from_legacy_tool,
)
from app.services.ai.tool_policy import ToolMetadata, resolve_tool_metadata
from app.services.ai.tools.registry import ToolRegistry


@dataclass(frozen=True)
class ToolCapabilityDefinition:
    """Describe one resolved tool without changing its execution policy."""

    name: str
    description: str
    source_type: ToolSourceType
    permission_scope: RuntimePermissionScope
    execution_policy: Literal["runtime_checked"]
    capability: str
    source: str
    side_effect: str
    confirmation: str
    freshness: str
    idempotent: str
    nudge_mode: str


@dataclass(frozen=True)
class ResolvedToolBinding:
    """Pair the model-visible definition with its executable runtime spec."""

    definition: ToolCapabilityDefinition
    spec: RuntimeToolSpec


ToolResolutionStatus = Literal["disabled", "missing", "filtered"]


@dataclass(frozen=True)
class ToolResolutionDiagnostic:
    """Explain why a requested tool did not enter the resolved tool set."""

    name: str
    status: ToolResolutionStatus
    reason: str


@dataclass(frozen=True)
class ResolvedToolSet:
    """The single ordered tool set shared by model and runtime consumers."""

    bindings: tuple[ResolvedToolBinding, ...]
    missing_required: tuple[str, ...] = ()
    diagnostics: tuple[ToolResolutionDiagnostic, ...] = ()

    @property
    def specs(self) -> tuple[RuntimeToolSpec, ...]:
        """Return executable specs in the model-visible order."""
        return tuple(binding.spec for binding in self.bindings)

    @property
    def names(self) -> tuple[str, ...]:
        """Return the names exposed to the model and runtime."""
        return tuple(binding.definition.name for binding in self.bindings)


def build_tool_resolution_log_events(
    resolved: ResolvedToolSet,
) -> list[dict[str, Any]]:
    """Convert safe tool-resolution diagnostics into frontend log events.

    The events contain only the configured tool name and resolver reason. They
    never include a runtime callable, tool arguments, credentials, or the
    resolved tool implementation.
    """
    titles = {
        "disabled": "工具未启用",
        "filtered": "工具已被当前权限范围过滤",
        "missing": "必需工具缺失",
    }
    events: list[dict[str, Any]] = []
    for index, diagnostic in enumerate(resolved.diagnostics):
        events.append(
            {
                "type": "log",
                "id": f"tool_resolution_{index}_{diagnostic.status}_{uuid4().hex[:12]}",
                "title": f"{titles[diagnostic.status]}：{diagnostic.name}",
                "details": diagnostic.reason,
                "status": "error" if diagnostic.status == "missing" else "warning",
                "category": "tool_resolution",
                "tool_name": diagnostic.name,
                "resolution_status": diagnostic.status,
            }
        )
    return events


class ToolProvider(Protocol):
    """Resolve configured and implicit tools from a platform source."""

    async def resolve_configured(self, items: Sequence[Any]) -> list[RuntimeToolSpec]:
        """Resolve configured items in their requested order."""

    def resolve_implicit(self, tool: Any) -> RuntimeToolSpec:
        """Convert an already selected implicit tool to a runtime spec."""


class RegistryToolProvider:
    """Adapt the existing ToolRegistry to the capability resolver."""

    def __init__(
        self,
        *,
        registry: type[ToolRegistry] = ToolRegistry,
        legacy_converter: Callable[..., RuntimeToolSpec] = runtime_tool_spec_from_legacy_tool,
        evidence_attacher: Callable[[str, RuntimeToolSpec], RuntimeToolSpec]
        | None = None,
    ) -> None:
        self._registry = registry
        self._legacy_converter = legacy_converter
        self._evidence_attacher = evidence_attacher or registry._attach_evidence_metadata

    async def resolve_configured(self, items: Sequence[Any]) -> list[RuntimeToolSpec]:
        """Reuse ToolRegistry lookup and per-tool runtime configuration."""
        return list(await self._registry.get_runtime_tools(list(items)))

    def resolve_implicit(self, tool: Any) -> RuntimeToolSpec:
        """Convert a system implicit legacy tool and attach grounding metadata."""
        spec = self._legacy_converter(tool, source_type="system")
        return self._evidence_attacher(spec.name, spec)

    async def get_implicit_tool(self, name: str) -> Any | None:
        """Look up a named implicit tool without exposing Registry to runners."""
        return await self._registry.get_tool(name)


class AgentScopeToolConsumer:
    """Build an AgentScope Toolkit from a previously resolved tool set."""

    def __init__(self, builder: Callable[..., Any] = build_toolkit) -> None:
        self._builder = builder

    def consume(self, resolved: ResolvedToolSet, **kwargs: Any) -> Any:
        """Pass the Resolver's specs to the model-tool consumer unchanged."""
        return self.consume_specs(resolved.specs, **kwargs)

    def consume_specs(
        self,
        specs: Sequence[RuntimeToolSpec],
        **kwargs: Any,
    ) -> Any:
        """Consume an ordered spec sequence when the binding is already held by a runner."""
        return self._builder(list(specs), **kwargs)


def _is_enabled(item: Any) -> bool:
    if isinstance(item, dict):
        return item.get("enabled", True) is not False
    return getattr(item, "enabled", True) is not False


def _tool_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("name", "") or "").strip()
    return str(getattr(item, "name", "") or "").strip()


def _active_allowed_names(allowed_names: Sequence[str] | None) -> list[str] | None:
    if allowed_names is not None:
        return [str(name) for name in allowed_names]
    from app.core.context import get_current_agent_context

    context = get_current_agent_context()
    context_names = getattr(context, "delegation_tool_filter", None)
    if context_names is None:
        return None
    return [str(name) for name in context_names]


def _definition_from_spec(spec: RuntimeToolSpec) -> ToolCapabilityDefinition:
    metadata: ToolMetadata = resolve_tool_metadata(spec)
    return ToolCapabilityDefinition(
        name=spec.name,
        description=spec.description,
        source_type=spec.source_type,
        permission_scope=spec.permission_scope,
        execution_policy="runtime_checked",
        capability=metadata.capability,
        source=metadata.source,
        side_effect=metadata.side_effect,
        confirmation=metadata.confirmation,
        freshness=metadata.freshness,
        idempotent=metadata.idempotent,
        nudge_mode=metadata.nudge_mode,
    )


async def resolve_tool_capabilities(
    configured_tools: Iterable[Any] | None,
    *,
    implicit_tools: Iterable[Any] | None = None,
    required_names: Iterable[str] = (),
    allowed_names: Sequence[str] | None = None,
    provider: ToolProvider | None = None,
) -> ResolvedToolSet:
    """Resolve one ordered, deduplicated set for model and runtime use.

    Configured items keep their order. Required names are appended when they
    are not configured, and implicit tools are appended last. Disabled config
    items never reach the provider. The final allowlist applies to both model
    visibility and executable specs.
    """
    resolver = provider or RegistryToolProvider()
    diagnostics: list[ToolResolutionDiagnostic] = []
    configured_items = []
    for item in configured_tools or ():
        name = _tool_name(item)
        if not name:
            continue
        if not _is_enabled(item):
            diagnostics.append(
                ToolResolutionDiagnostic(
                    name=name,
                    status="disabled",
                    reason="tool configuration disabled",
                )
            )
            continue
        configured_items.append(item)
    configured_names = {_tool_name(item) for item in configured_items}
    required = []
    required_seen: set[str] = set()
    for name in required_names:
        normalized = str(name or "").strip()
        if normalized and normalized not in required_seen:
            required.append(normalized)
            required_seen.add(normalized)

    required_items = [name for name in required if name not in configured_names]
    provider_items = [*configured_items, *required_items]
    configured_specs = (
        await resolver.resolve_configured(provider_items)
        if provider_items
        else []
    )

    ordered_specs: list[RuntimeToolSpec] = []
    seen: set[str] = set()
    for spec in configured_specs:
        if spec.name in seen:
            continue
        ordered_specs.append(spec)
        seen.add(spec.name)

    for tool in implicit_tools or ():
        spec = resolver.resolve_implicit(tool)
        if spec.name in seen:
            continue
        ordered_specs.append(spec)
        seen.add(spec.name)

    active_allowed_names = _active_allowed_names(allowed_names)
    filtered_specs = apply_delegation_tool_filter(ordered_specs, active_allowed_names)
    filtered_names = {spec.name for spec in filtered_specs}
    if active_allowed_names is not None:
        diagnostics.extend(
            ToolResolutionDiagnostic(
                name=spec.name,
                status="filtered",
                reason="tool excluded by the active allowlist",
            )
            for spec in ordered_specs
            if spec.name not in filtered_names
        )
    visible_names = {spec.name for spec in filtered_specs}
    missing_required = tuple(name for name in required if name not in visible_names)
    ordered_names = {spec.name for spec in ordered_specs}
    diagnostics.extend(
        ToolResolutionDiagnostic(
            name=name,
            status="missing",
            reason="required tool was not available from the provider",
        )
        for name in missing_required
        if name not in ordered_names
    )
    bindings = tuple(
        ResolvedToolBinding(
            definition=_definition_from_spec(spec),
            spec=spec,
        )
        for spec in filtered_specs
    )
    return ResolvedToolSet(
        bindings=bindings,
        missing_required=missing_required,
        diagnostics=tuple(diagnostics),
    )
