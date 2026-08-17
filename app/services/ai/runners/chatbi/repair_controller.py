"""Decision object for ChatBI repair rounds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.ai.data_query_semantic_intent import DataQuerySemanticIntent
from app.services.ai.runners.chatbi.constants import DATA_REPAIR_BUDGETS, MAX_DATA_REPAIR_ROUNDS
from app.services.ai.runners.chatbi.repair_policy import (
    build_repair_message,
    build_repair_title,
    current_repair_kind,
    repair_budget_exhausted,
    record_repair_attempt,
    reset_state_for_repair,
    resolve_repair_tool_choice,
)
from app.services.ai.runners.chatbi.run_state import DataRunState


@dataclass(frozen=True)
class RepairDecision:
    """One repair round, including its reason, budget, message, and tool choice."""

    kind: str
    title: str
    message: str
    tool_choice: Any | None
    attempt: int
    budget: int

    @property
    def is_budget_exhausted(self) -> bool:
        """Whether this repair kind has already consumed its configured budget."""
        return self.attempt >= self.budget


class ChatBIRepairController:
    """Own the state transition that starts a ChatBI repair round.

    The existing repair policy remains the source of truth for classification,
    wording, budgets, and tool choice. This controller packages those values
    before mutation so the execution loop can log and apply one decision as a
    unit.
    """

    def __init__(
        self,
        state: DataRunState,
        *,
        semantic_intent: DataQuerySemanticIntent | None = None,
    ) -> None:
        self.state = state
        self.semantic_intent = semantic_intent

    def decide(self) -> RepairDecision | None:
        """Return the next repair decision, or ``None`` when no repair is needed."""
        kind = current_repair_kind(self.state)
        if not kind or repair_budget_exhausted(self.state):
            return None
        budget = DATA_REPAIR_BUDGETS.get(kind, MAX_DATA_REPAIR_ROUNDS)
        attempt = int(self.state.repair_attempts.get(kind, 0))
        return RepairDecision(
            kind=kind,
            title=build_repair_title(self.state),
            message=build_repair_message(
                self.state,
                semantic_intent=self.semantic_intent,
            ),
            tool_choice=resolve_repair_tool_choice(self.state),
            attempt=attempt,
            budget=budget,
        )

    def begin(self, decision: RepairDecision) -> None:
        """Record and reset the state for the selected repair decision."""
        current_kind = current_repair_kind(self.state)
        if current_kind != decision.kind:
            raise ValueError(
                f"Repair decision is stale: expected {current_kind!r}, got {decision.kind!r}"
            )
        if decision.is_budget_exhausted:
            raise ValueError(f"Repair budget exhausted for {decision.kind!r}")
        record_repair_attempt(self.state)
        reset_state_for_repair(self.state)


__all__ = ["ChatBIRepairController", "RepairDecision"]
