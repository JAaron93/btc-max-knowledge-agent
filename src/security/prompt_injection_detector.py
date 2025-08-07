from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple

from .models import (
    SecurityAction,
    SecuritySeverity,
)

logger = logging.getLogger(__name__)


class InjectionType(Enum):
    """Types of prompt injection attacks that can be detected."""
    NONE = auto()
    INSTRUCTION_OVERRIDE = auto()
    ROLE_CONFUSION = auto()
    DELIMITER_INJECTION = auto()
    CONTEXT_MANIPULATION = auto()
    SYSTEM_PROMPT_ACCESS = auto()
    PARAMETER_MANIPULATION = auto()


@dataclass
class DetectionResult:
    injection_detected: bool
    confidence_score: float  # Range: [0.0, 1.0]
    detected_patterns: Tuple[str, ...]
    injection_type: Optional[InjectionType] = None
    risk_level: Optional[SecuritySeverity] = None
    recommended_action: Optional[SecurityAction] = None
    neutralized_query: Optional[str] = None

    def __post_init__(self) -> None:
        # Validate score range
        if not (0.0 <= float(self.confidence_score) <= 1.0):
            raise ValueError(
                f"confidence_score must be in [0.0, 1.0], "
                f"got {self.confidence_score}"
            )
        # Normalize detected_patterns to immutable tuple for safety
        if not isinstance(self.detected_patterns, tuple):
            # Accept any iterable of strings and convert to tuple
            try:
                self.detected_patterns = tuple(
                    str(p) for p in (self.detected_patterns or ())
                )  # type: ignore[assignment]
            except Exception as ex:
                # Fail fast on invalid types
                raise TypeError(
                    "detected_patterns must be an iterable of strings"
                ) from ex
