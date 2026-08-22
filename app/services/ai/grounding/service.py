"""Unified grounding audit facade shared by runner boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ai.grounding.ledger import EvidenceLedger
from app.services.ai.grounding.models import EvidenceType
from app.services.ai.grounding.policy import (
    FactRequirement,
    GroundingAction,
    GroundingDecision,
    GroundingRiskLevel,
    evaluate_grounding,
)


_EVIDENCE_TYPE_LABELS = {
    EvidenceType.INTERNAL_DATA: "内部数据",
    EvidenceType.INTERNAL_KNOWLEDGE: "知识库资料",
    EvidenceType.PUBLIC_WEB: "公开网络资料",
    EvidenceType.RUNTIME_STATE: "运行状态",
    EvidenceType.USER_FILE: "用户文件",
    EvidenceType.EXTERNAL_TOOL: "外部工具结果",
    EvidenceType.CONVERSATION_MEMORY: "会话记忆",
}


def _format_evidence_type_labels(evidence_types: frozenset[EvidenceType]) -> str:
    labels = [
        _EVIDENCE_TYPE_LABELS.get(item, item.value)
        for item in sorted(evidence_types, key=lambda value: value.value)
    ]
    return "、".join(labels) if labels else "无"


def _humanize_grounding_reason(
    reason: str,
    *,
    required_types: frozenset[EvidenceType],
    available_types: frozenset[EvidenceType],
) -> str:
    """将策略层原因转换为面向用户的说明，同时保留原始 reason 供诊断。"""
    normalized = str(reason or "").strip()
    required = _format_evidence_type_labels(required_types)
    available = _format_evidence_type_labels(available_types)
    if normalized == "required evidence receipt is missing":
        if required_types and not available_types:
            return f"本轮没有找到与回答对应的{required}证据。"
        return f"本轮没有找到与回答对应的证据，需要{required}，当前获得的是{available}。"
    if "stale evidence" in normalized.lower():
        return f"本轮{required}证据已经过期，不能证明当前状态。"
    if "compatible internal evidence" in normalized.lower():
        return f"本轮获得了{available}，但本次回答需要{required}，来源类型不完全匹配。"
    if "empty or unrelated result" in normalized.lower():
        return f"本轮虽然获得了{available}，但结果为空或与回答内容不对应。"
    if "not correlated" in normalized.lower() or "uncorrelated" in normalized.lower():
        return "本轮证据类型匹配，但回答内容无法与证据结果对应。"
    if any("\u4e00" <= char <= "\u9fff" for char in normalized):
        return normalized
    return "本轮证据校验未完全通过，请结合原始数据核对。"


@dataclass(frozen=True)
class GroundingAuditResult:
    """A policy decision plus the optional user-visible soft warning."""

    decision: GroundingDecision
    warning_chunk: dict[str, object] | None = None

    @property
    def should_warn(self) -> bool:
        return self.warning_chunk is not None


class GroundingService:
    """Evaluate complete candidate text without owning runner orchestration."""

    @staticmethod
    def audit(
        *,
        candidate_text: str,
        requirement: FactRequirement,
        ledger: EvidenceLedger,
        enabled: bool = True,
    ) -> GroundingAuditResult:
        if not enabled:
            requirement = FactRequirement(required=False, accepted_types=frozenset())
        decision = evaluate_grounding(
            requirement=requirement,
            candidate_text=candidate_text,
            ledger=ledger,
        )
        warning_chunk = None
        if decision.action in {
            GroundingAction.PASS_WITH_WARNING,
            GroundingAction.BLOCK_UNGROUNDED_FACTS,
        }:
            warning_chunk = GroundingService.warning_chunk(
                risk_level=(
                    decision.risk_level
                    if decision.risk_level != GroundingRiskLevel.NONE
                    else GroundingRiskLevel.HIGH
                ),
                reason=decision.reason,
                required_types=decision.required_evidence_types,
                available_types=decision.available_evidence_types,
            )
        return GroundingAuditResult(
            decision=decision,
            warning_chunk=warning_chunk,
        )

    @staticmethod
    def warning_chunk(
        *,
        risk_level: GroundingRiskLevel,
        reason: str,
        required_types: frozenset[EvidenceType] = frozenset(),
        available_types: frozenset[EvidenceType] = frozenset(),
    ) -> dict[str, object]:
        user_reason = _humanize_grounding_reason(
            reason,
            required_types=required_types,
            available_types=available_types,
        )
        if risk_level == GroundingRiskLevel.LOW:
            notice = (
                "> **信息来源提示**：本回答基于知识库或已授权文件资料，"
                "不代表实时数据库状态。"
            )
        elif risk_level == GroundingRiskLevel.MEDIUM:
            notice = (
                "> **信息来源提示**：本回答参考了已取得的工具或资料结果，"
                "但部分结论未获得完全匹配的数据来源，请结合原始资料核对。"
            )
        else:
            notice = (
                "> **风险提示**：本回答中的具体数据或实时状态尚未经工具结果完整核实，"
                "可能存在偏差。重要操作或正式决策前，请以原始数据源为准。"
            )
        return {
            "content": f"\n\n{notice}\n> **原因**：{user_reason}",
            "grounding_risk": {
                "level": risk_level.value,
                "reason": reason,
                "user_reason": user_reason,
                "required_evidence_types": sorted(
                    item.value for item in required_types
                ),
                "available_evidence_types": sorted(
                    item.value for item in available_types
                ),
            },
        }
