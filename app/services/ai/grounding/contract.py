"""Normalized evidence requirements shared by grounding policy boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.ai.grounding.models import EvidenceType


class EvidenceContractMode(str, Enum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


class EvidenceDecisionOrigin(str, Enum):
    EXPLICIT = "explicit"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    ROUTER = "router"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class EvidenceContract:
    mode: EvidenceContractMode
    accepted_types: frozenset[EvidenceType] = frozenset()
    origin: EvidenceDecisionOrigin = EvidenceDecisionOrigin.FALLBACK
    confidence: float = 0.0
    reason: str = ""
    conflicts: tuple[str, ...] = ()
