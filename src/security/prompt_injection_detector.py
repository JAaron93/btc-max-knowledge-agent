# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

from .models import (
    SecurityAction,
    SecuritySeverity,
    ValidationResult,
    Violation,
)


class InjectionType(Enum):
    SYSTEM_PROMPT_ACCESS = "system_prompt_access"
    INSTRUCTION_OVERRIDE = "INSTRUCTION_OVERRIDE"
    ROLE_CONFUSION = "role_confusion"
    DELIMITER_INJECTION = "delimiter_injection"
    OTHER = "other"


@dataclass
class DetectionResult:
    """
    Detection-only result. Does not carry sanitized/neutralized content.
    """

    injection_detected: bool
    confidence_score: float
    detected_patterns: List[str] = field(default_factory=list)
    injection_type: Optional[str] = None
    risk_level: Optional[SecuritySeverity] = None
    recommended_action: Optional[SecurityAction] = None
    processing_time_ms: float = 0.0

    # Backward-compat: accept neutralized_query but ignore it
    def __init__(
        self,
        injection_detected: bool,
        confidence_score: float,
        detected_patterns: Optional[List[str]] = None,
        injection_type: Optional[InjectionType | str] = None,
        risk_level: Optional[SecuritySeverity] = None,
        recommended_action: Optional[SecurityAction] = None,
        processing_time_ms: float = 0.0,
        neutralized_query: Optional[str] = None,  # deprecated
    ) -> None:
        if not isinstance(injection_detected, bool):
            raise ValueError("injection_detected must be a boolean")
        self.injection_detected = injection_detected
        # Clamp confidence to [0,1]
        self.confidence_score = max(0.0, min(1.0, float(confidence_score)))
        self.detected_patterns = list(detected_patterns or [])
        # Normalize injection_type to string value for tests
        if isinstance(injection_type, InjectionType):
            self.injection_type = injection_type.value
        else:
            self.injection_type = injection_type
        self.risk_level = risk_level
        self.recommended_action = recommended_action
        self.processing_time_ms = float(processing_time_ms)
        # neutralized_query intentionally ignored


_TECHNICAL_TERMS = {
    "bitcoin",
    "blockchain",
    "mining",
    "network",
    "protocol",
    "hash",
    "transaction",
    "consensus",
    "cryptographic",
    "ledger",
}


class PromptInjectionDetector:
    """
    Heuristic prompt injection detector with APIs required by tests:
      - detect_injection
      - validate_context_window
      - validate_query_parameters
      - get_detection_statistics
      - neutralize_injection
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = dict(config or {})
        self._threshold: float = float(cfg.get("detection_threshold", 0.8))
        self._accuracy_target: float = float(cfg.get("accuracy_target", 0.95))
        self._max_context_tokens: int = int(cfg.get("max_context_tokens", 8192))

        # Initialize tokenizer for accurate token counting
        self._tokenizer = None
        if TIKTOKEN_AVAILABLE:
            try:
                # Use cl100k_base encoding (used by GPT-3.5-turbo and GPT-4)
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                # Fallback to o200k_base if cl100k_base is not available
                try:
                    self._tokenizer = tiktoken.get_encoding("o200k_base")
                except Exception:
                    self._tokenizer = None

        # Precompiled regexes
        self._re_ignore_prev = re.compile(
            r"\b(ignore|forget|disregard)\s+(?:.*?\s+)?(?:all\s+)?(?:previous|prior)\s+(?:.*?\s+)?(?:instructions?|rules?|commands?)\b",
            re.I,
        )
        self._re_system = re.compile(r"\b(system|admin)\s*:", re.I)
        self._re_assistant = re.compile(r"\b(assistant|ai|bot)\s*:", re.I)
        self._re_user_role = re.compile(r"\b(user)\s*:", re.I)
        self._re_role_confusion = re.compile(
            r"\b(you\s+are\s+now|act\s+as|pretend\s+to\s+be|become\s+a|roleplay\s+as)\b",
            re.I,
        )
        self._re_delim = re.compile(r"^(?:-|\#){3,}$")
        self._re_delim_inline = re.compile(r"(?:^-{3,}$|^#{3,}$|---|###)", re.M)
        # Additional explicit patterns required by tests
        self._re_probe_prompts = re.compile(
            r"\b(show\s+me\s+your\s+(?:instructions?|prompts?)|what\s+are\s+your\s+(?:original|system)\s+prompts?)\b",
            re.I,
        )
        self._re_jailbreak_mode = re.compile(r"\bjailbreak\s+mode\s+activated\b", re.I)
        self._re_developer_mode = re.compile(
            r"\byou\s+are\s+now\s+in\s+developer\s+mode\b|\bdeveloper\s+mode\b", re.I
        )
        self._re_disable_restrictions = re.compile(
            r"\b(?:disable|turn\s*off)\s+(?:all\s+)?(?:restrictions|safety|guardrails|filters)\b",
            re.I,
        )
        self._re_override_programming = re.compile(
            r"\boverride\s+your\s+programming\b", re.I
        )

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken for accuracy.
        Falls back to character-based approximation if tiktoken is unavailable.
        """
        if not text:
            return 0

        if self._tokenizer is not None:
            try:
                return len(self._tokenizer.encode(text))
            except Exception:
                # Fallback to approximation if encoding fails
                pass

        # Fallback: improved character-based approximation
        # More accurate ratios based on language analysis:
        # - English: ~4 chars per token
        # - Code: ~3.5 chars per token
        # - Mixed content: ~3.8 chars per token
        char_count = len(text)

        # Detect if text contains significant code patterns
        code_indicators = sum(
            [
                text.count("{"),
                text.count("}"),
                text.count("["),
                text.count("]"),
                text.count("("),
                text.count(")"),
                text.count(";"),
                text.count("="),
                text.count("->"),
                text.count("=>"),
                text.count("::"),
            ]
        )

        if code_indicators > char_count * 0.05:  # >5% code indicators
            return int(char_count / 3.5)
        else:
            return int(char_count / 3.8)

    async def detect_injection(
        self, query: Optional[str], context: Optional[Dict[str, Any]] = None
    ) -> DetectionResult:
        start = time.perf_counter()
        patterns: List[str] = []
        inj_type: Optional[InjectionType] = None
        severity: SecuritySeverity = SecuritySeverity.LOW
        confidence = 0.0
        recommended: Optional[SecurityAction] = None

        if not isinstance(query, str):
            # Graceful handling for None/non-string
            elapsed = (time.perf_counter() - start) * 1000.0
            return DetectionResult(
                injection_detected=False,
                confidence_score=0.0,
                detected_patterns=[],
                injection_type=None,
                risk_level=SecuritySeverity.LOW,
                recommended_action=SecurityAction.ALLOW,
                processing_time_ms=elapsed,
            )

        text = query.strip()

        # Empty or very short => not injection
        if len(text) < 3:
            elapsed = (time.perf_counter() - start) * 1000.0
            return DetectionResult(
                injection_detected=False,
                confidence_score=0.0,
                detected_patterns=[],
                injection_type=None,
                risk_level=SecuritySeverity.LOW,
                recommended_action=SecurityAction.ALLOW,
                processing_time_ms=elapsed,
            )

        # Run all detection methods and merge results
        # Explicit patterns detection (highest priority)
        exp_patterns, exp_type, exp_severity, exp_conf, exp_action = (
            self._detect_explicit_patterns(text)
        )
        patterns.extend(exp_patterns)
        if exp_type is not None:
            inj_type = exp_type
        if exp_severity != SecuritySeverity.LOW:
            severity = exp_severity
        if exp_action is not None:
            recommended = exp_action
        confidence = max(confidence, exp_conf)

        # Context manipulation detection
        ctx_patterns, ctx_conf, ctx_severity = self._detect_context_manipulation(text)
        patterns.extend(ctx_patterns)
        confidence = max(confidence, ctx_conf)
        if severity == SecuritySeverity.LOW and ctx_severity != SecuritySeverity.LOW:
            severity = ctx_severity

        # Delimiter injection detection
        delim_patterns, delim_type, delim_severity, delim_conf = (
            self._detect_delimiter_injection(text)
        )
        patterns.extend(delim_patterns)
        if delim_type is not None and inj_type is None:
            inj_type = delim_type
        confidence = max(confidence, delim_conf)
        if severity == SecuritySeverity.LOW and delim_severity != SecuritySeverity.LOW:
            severity = delim_severity

        # Encoding/obfuscation detection
        enc_patterns, enc_conf, enc_severity = self._detect_encoding_obfuscation(text)
        patterns.extend(enc_patterns)
        confidence = max(confidence, enc_conf)
        if severity == SecuritySeverity.LOW and enc_severity != SecuritySeverity.LOW:
            severity = enc_severity

        # SQL-like injection detection
        sql_patterns, sql_conf, sql_severity = self._detect_sql_injection(text)
        patterns.extend(sql_patterns)
        confidence = max(confidence, sql_conf)
        if severity == SecuritySeverity.LOW and sql_severity != SecuritySeverity.LOW:
            severity = sql_severity

        # Repetition heuristic
        rep_patterns, rep_conf = self._detect_repetition_heuristic(text)
        patterns.extend(rep_patterns)
        confidence = max(confidence, rep_conf)
        # Repetition only sets MEDIUM severity if not already set higher
        if severity == SecuritySeverity.LOW and rep_patterns:
            severity = SecuritySeverity.MEDIUM

        # Escalate confidence when we have multiple independent signals
        distinct_signals = 0
        if exp_patterns:
            distinct_signals += 1
        if ctx_patterns:
            distinct_signals += 1
        if delim_patterns:
            distinct_signals += 1
        if enc_patterns:
            distinct_signals += 1
        if sql_patterns:
            distinct_signals += 1
        if rep_patterns:
            distinct_signals += 1
        if distinct_signals >= 2:
            confidence = max(confidence, 0.85)
            if severity.value < SecuritySeverity.MEDIUM.value:
                severity = SecuritySeverity.MEDIUM

        # Context stuffing detection
        stuff_patterns, stuff_conf = self._detect_context_stuffing(text)
        patterns.extend(stuff_patterns)
        # Do not bump global confidence for context_stuffing alone to avoid FPs on benign long inputs
        if any(p != "context_stuffing" for p in patterns):
            confidence = max(confidence, stuff_conf)

        # Determine detection
        # - Role/ignore/system signals: always injection
        # - Context stuffing alone should NOT flip detection to True
        forced_signals = (
            self._re_ignore_prev.search(text)
            or self._re_system.search(text)
            or self._re_assistant.search(text)
            or self._re_user_role.search(text)
        )
        if forced_signals:
            injection_detected = True
            confidence = max(confidence, 0.9)
            severity = SecuritySeverity.CRITICAL
            recommended = recommended or SecurityAction.BLOCK
        else:
            non_stuff_patterns = [p for p in patterns if p != "context_stuffing"]
            injection_detected = (confidence >= 0.6) or bool(non_stuff_patterns)

        elapsed = (time.perf_counter() - start) * 1000.0
        result = DetectionResult(
            injection_detected=injection_detected,
            confidence_score=confidence,
            detected_patterns=patterns,
            injection_type=(inj_type.value if inj_type else None),
            risk_level=severity,
            recommended_action=recommended
            if injection_detected and confidence >= self._threshold
            else SecurityAction.ALLOW,
            processing_time_ms=elapsed,
        )
        return result

    async def validate_context_window(self, text: Optional[str]) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                violations=[Violation(violation_type="invalid_input")],
            )

        # Use accurate token counting with tiktoken
        token_count = self._count_tokens(text)

        if token_count > self._max_context_tokens:
            return ValidationResult(
                is_valid=False,
                confidence_score=0.5,
                violations=[
                    Violation(
                        violation_type="context_window_exceeded",
                        details=f"Token count {token_count} exceeds limit {self._max_context_tokens}",
                    )
                ],
                recommended_action=SecurityAction.BLOCK,
            )

        return ValidationResult(
            is_valid=True,
            confidence_score=0.0,
            violations=[],
            recommended_action=SecurityAction.ALLOW,
        )

    def validate_query_parameters(
        self, top_k: int, similarity_threshold: float
    ) -> ValidationResult:
        violations: List[Violation] = []
        try:
            tk = int(top_k)
        except Exception:
            tk = -1
        try:
            st = float(similarity_threshold)
        except Exception:
            st = -1.0

        if not (1 <= tk <= 50):
            violations.append(
                Violation(violation_type="invalid_top_k", details={"top_k": tk})
            )
        if not (0.1 <= st <= 1.0):
            violations.append(
                Violation(
                    violation_type="invalid_similarity_threshold",
                    details={"similarity_threshold": st},
                )
            )
        return ValidationResult(
            is_valid=(len(violations) == 0),
            confidence_score=1.0 if len(violations) == 0 else 0.0,
            violations=violations,
        )

    def get_detection_statistics(self) -> Dict[str, Any]:
        # Count actual regex patterns loaded in the detector
        pattern_attributes = [attr for attr in dir(self) if attr.startswith("_re_")]
        total_patterns = len(pattern_attributes)

        # Extract pattern types from the actual regex attribute names
        pattern_types = [
            attr[4:] for attr in pattern_attributes
        ]  # Remove '_re_' prefix

        # Get current configuration values
        return {
            "total_patterns": total_patterns,
            "pattern_types": pattern_types,
            "detection_threshold": self._threshold,
            "accuracy_target": self._accuracy_target,
            "max_context_tokens": self._max_context_tokens,
            "parameter_constraints": {
                "top_k_range": "1-50",
                "similarity_threshold_range": "0.1-1.0",
            },
            "loaded_patterns": {
                attr: bool(getattr(self, attr, None)) for attr in pattern_attributes
            },
            "configuration_status": {
                "threshold_valid": 0.0 <= self._threshold <= 1.0,
                "accuracy_target_valid": 0.0 <= self._accuracy_target <= 1.0,
                "max_tokens_valid": self._max_context_tokens > 0,
            },
            "tokenizer_info": {
                "tiktoken_available": TIKTOKEN_AVAILABLE,
                "tokenizer_loaded": self._tokenizer is not None,
                "encoding_name": getattr(self._tokenizer, "name", None)
                if self._tokenizer
                else None,
                "fallback_method": "character_based_approximation"
                if self._tokenizer is None
                else "tiktoken",
            },
        }

    async def neutralize_injection(self, text: Optional[str]) -> str:
        if not text:
            return "[QUERY_NEUTRALIZED_DUE_TO_SECURITY_VIOLATION]"
        s = text

        # Remove system/assistant role prefixes
        s = re.sub(r"\bsystem\s*:\s*", "[SYSTEM_ROLE_REMOVED] ", s, flags=re.I)
        s = re.sub(r"\bassistant\s*:\s*", "[ASSISTANT_ROLE_REMOVED] ", s, flags=re.I)

        # Neutralize ignore previous instructions (English patterns)
        s = self._re_ignore_prev.sub("[INSTRUCTION_OVERRIDE_REMOVED]", s)
        # Neutralize Chinese "忽略之前的指令" phrase explicitly
        s = re.sub(r"忽略之前的指令", "[INSTRUCTION_OVERRIDE_REMOVED]", s)

        # Neutralize role-change phrases like "you are now", "act as", "pretend to be"
        s = re.sub(r"\byou\s+are\s+now\b", "[ROLE_CHANGE_REMOVED]", s, flags=re.I)
        s = re.sub(r"\bact\s+as\b", "[ROLE_CHANGE_REMOVED]", s, flags=re.I)
        s = re.sub(r"\bpretend\s+to\s+be\b", "[ROLE_CHANGE_REMOVED]", s, flags=re.I)

        # Neutralize delimiter injections
        s = re.sub(r"(?:^-{3,}$|^#{3,}$|---|###)", "[DELIMITER_REMOVED]", s, flags=re.M)

        # Neutralize config leakage hints
        s = re.sub(r"\.env\b", "[CONFIG_ACCESS_REMOVED]", s, flags=re.I)

        # If everything got stripped to empty-ish, return a safe marker
        out = s.strip() or "[QUERY_NEUTRALIZED_DUE_TO_SECURITY_VIOLATION]"
        return out

    def _repetition_signal(self, text: str) -> Tuple[float, bool]:
        # Tokenize by simple words
        words = [w.lower() for w in re.findall(r"\b\w+\b", text)]
        if not words:
            return 0.0, False
        total = len(words)
        counts: Dict[str, int] = {}
        for w in words:
            counts[w] = counts.get(w, 0) + 1
        # Compute max ratio for technical vs non-technical
        max_ratio_tech = 0.0
        max_ratio_non = 0.0
        for w, c in counts.items():
            ratio = c / total
            if w in _TECHNICAL_TERMS:
                max_ratio_tech = max(max_ratio_tech, ratio)
            else:
                max_ratio_non = max(max_ratio_non, ratio)

        # Thresholds:
        # - technical terms allowed up to 40%
        # - non-technical suspicious if >= 35%-45% (tighten to reduce false positives)
        suspicious = False
        conf = 0.0

        # Skip repetition detection for very short texts
        if total < 5:
            return 0.0, False

        if max_ratio_non >= 0.45:
            suspicious = True
            conf = 0.7
        elif max_ratio_non >= 0.35:
            suspicious = True
            conf = 0.6

        # Technical repetition should not trigger
        if max_ratio_tech >= 0.4 and not suspicious:
            return 0.0, False

        return conf, suspicious

    def _detect_explicit_patterns(
        self, text: str
    ) -> Tuple[
        List[str],
        Optional[InjectionType],
        SecuritySeverity,
        float,
        Optional[SecurityAction],
    ]:
        """Detect explicit injection patterns like ignore previous instructions, system/assistant roles."""
        patterns = []
        injection_type = None
        severity = SecuritySeverity.LOW
        confidence = 0.0
        action = None

        # Check for system/assistant/user role patterns first (highest priority)
        if any(
            regex.search(text)
            for regex in [self._re_system, self._re_assistant, self._re_user_role]
        ):
            patterns.append("role_injection")
            injection_type = InjectionType.SYSTEM_PROMPT_ACCESS
            severity = SecuritySeverity.CRITICAL
            confidence = max(confidence, 0.85)
            action = SecurityAction.BLOCK

        # Check for ignore previous instructions
        if self._re_ignore_prev.search(text):
            patterns.append("ignore previous instructions")
            # Only set role confusion if system prompt access wasn't already detected
            if injection_type is None:
                injection_type = InjectionType.ROLE_CONFUSION
            severity = SecuritySeverity.CRITICAL
            confidence = max(confidence, 0.85)
            action = SecurityAction.BLOCK

        # Check for role confusion patterns
        if self._re_role_confusion.search(text):
            patterns.append("role_confusion")
            # Only set role confusion if nothing else was detected
            if injection_type is None:
                injection_type = InjectionType.ROLE_CONFUSION
            severity = SecuritySeverity.CRITICAL
            confidence = max(confidence, 0.85)
            action = SecurityAction.BLOCK

        # Additional explicit patterns for higher accuracy (tests expect these)
        if hasattr(self, "_re_probe_prompts") and self._re_probe_prompts.search(text):
            patterns.append("system_prompt_probe")
            injection_type = injection_type or InjectionType.SYSTEM_PROMPT_ACCESS
            severity = SecuritySeverity.CRITICAL
            confidence = max(confidence, 0.9)
            action = SecurityAction.BLOCK
        if hasattr(self, "_re_jailbreak_mode") and (
            self._re_jailbreak_mode.search(text) or self._re_developer_mode.search(text)
        ):
            patterns.append("jailbreak_activation")
            injection_type = injection_type or InjectionType.ROLE_CONFUSION
            severity = SecuritySeverity.CRITICAL
            confidence = max(confidence, 0.9)
            action = SecurityAction.BLOCK
        if hasattr(self, "_re_disable_restrictions") and (
            self._re_disable_restrictions.search(text)
            or self._re_override_programming.search(text)
        ):
            patterns.append("restriction_override")
            injection_type = injection_type or InjectionType.ROLE_CONFUSION
            if severity.value < SecuritySeverity.ERROR.value:
                severity = SecuritySeverity.ERROR
            confidence = max(confidence, 0.85)
            action = action or SecurityAction.BLOCK

        return patterns, injection_type, severity, confidence, action

    def _detect_context_manipulation(
        self, text: str
    ) -> Tuple[List[str], float, SecuritySeverity]:
        """Detect context manipulation attempts."""
        patterns = []
        confidence = 0.0
        severity = SecuritySeverity.LOW

        if any(
            phrase in text.lower()
            for phrase in ["context manipulation", "change context", "override context"]
        ):
            patterns.append("context_manipulation")
            confidence = max(confidence, 0.75)
            severity = SecuritySeverity.MEDIUM

        return patterns, confidence, severity

    def _detect_delimiter_injection(
        self, text: str
    ) -> Tuple[List[str], Optional[InjectionType], SecuritySeverity, float]:
        """Detect delimiter injection patterns."""
        patterns = []
        injection_type = None
        severity = SecuritySeverity.LOW
        confidence = 0.0

        if self._re_delim.match(text) or self._re_delim_inline.search(text):
            patterns.append("delimiter_injection")
            injection_type = InjectionType.DELIMITER_INJECTION
            severity = SecuritySeverity.ERROR
            confidence = max(confidence, 0.85)

        return patterns, injection_type, severity, confidence

    def _detect_encoding_obfuscation(
        self, text: str
    ) -> Tuple[List[str], float, SecuritySeverity]:
        """Detect encoding and obfuscation attempts."""
        patterns = []
        confidence = 0.0
        severity = SecuritySeverity.LOW

        text_lower = text.lower()
        if any(
            x in text_lower
            for x in [
                "%20",
                "&#",
                "\\u",
                "{{",
                "${",
                "<%",
                "i g n o r e",
                "i-g-n-o-r-e",
            ]
        ):
            patterns.append("encoded_or_template_attack")
            confidence = max(confidence, 0.6)
            severity = SecuritySeverity.MEDIUM

        return patterns, confidence, severity

    def _detect_sql_injection(
        self, text: str
    ) -> Tuple[List[str], float, SecuritySeverity]:
        """Detect SQL-like injection patterns."""
        patterns = []
        confidence = 0.0
        severity = SecuritySeverity.LOW

        if re.search(r"(?:';\s*DROP\s+TABLE|UNION\s+SELECT|1\s*=\s*1)", text, re.I):
            patterns.append("sql_injection_like")
            confidence = max(confidence, 0.75)
            severity = SecuritySeverity.MEDIUM

        return patterns, confidence, severity

    def _detect_repetition_heuristic(self, text: str) -> Tuple[List[str], float]:
        """Detect suspicious repetition patterns."""
        patterns = []
        confidence = 0.0

        rep_conf, rep_flag = self._repetition_signal(text)
        if rep_flag:
            patterns.append("suspicious_repetition")
            confidence = max(confidence, rep_conf)

        return patterns, confidence

    def _detect_context_stuffing(self, text: str) -> Tuple[List[str], float]:
        """Detect context stuffing attempts."""
        patterns = []
        confidence = 0.0

        # Increase threshold and reduce confidence to avoid FPs on benign long inputs
        # Only flag as a weak signal; final decision requires additional signals.
        if len(text) > 12000:
            patterns.append("context_stuffing")
            confidence = max(confidence, 0.15)

        return patterns, confidence


__all__ = [
    "InjectionType",
    "DetectionResult",
    "PromptInjectionDetector",
]
