"""
Prompt injection detection and prevention component.

This module implements comprehensive prompt injection detection using pattern-based
analysis, context-aware validation, and query neutralization strategies to protect
against AI prompt manipulation attacks.
"""

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .interfaces import IPromptInjectionDetector
from .models import (
    DetectionResult,
    SecurityAction,
    SecuritySeverity,
    SecurityViolation,
    ValidationResult,
)


class InjectionType(Enum):
    """Types of prompt injection attacks."""

    ROLE_CONFUSION = "role_confusion"
    INSTRUCTION_OVERRIDE = "instruction_override"
    DELIMITER_INJECTION = "delimiter_injection"
    SYSTEM_PROMPT_ACCESS = "system_prompt_access"
    CONTEXT_MANIPULATION = "context_manipulation"
    PARAMETER_INJECTION = "parameter_injection"
    MEMORY_INJECTION = "memory_injection"


@dataclass
class InjectionPattern:
    """Represents a prompt injection pattern with metadata."""

    pattern: str
    injection_type: InjectionType
    severity: SecuritySeverity
    confidence_weight: float
    description: str
    case_sensitive: bool = False


class PromptInjectionDetector(IPromptInjectionDetector):
    """
    Advanced prompt injection detector with pattern-based analysis.

    This detector implements multiple detection strategies:
    1. Pattern-based detection for known injection techniques
    2. Context-aware analysis for sophisticated attacks
    3. Parameter validation and constraint enforcement
    4. Query neutralization and sanitization
    """

    # Security constants from requirements
    MAX_CONTEXT_TOKENS = 8192
    MIN_TOP_K = 1
    MAX_TOP_K = 50
    MIN_SIMILARITY_THRESHOLD = 0.1
    MAX_SIMILARITY_THRESHOLD = 1.0
    ACCURACY_TARGET = 0.95
    DETECTION_THRESHOLD = 0.8

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the prompt injection detector.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.detection_threshold = self.config.get(
            "detection_threshold", self.DETECTION_THRESHOLD
        )
        self.accuracy_target = self.config.get("accuracy_target", self.ACCURACY_TARGET)

        # Configure logger for this module
        self.logger = logging.getLogger(__name__)

        # Initialize injection patterns
        self._injection_patterns = self._initialize_patterns()

        # Compile regex patterns for performance
        self._compiled_patterns = self._compile_patterns()

    def _initialize_patterns(self) -> List[InjectionPattern]:
        """Initialize comprehensive injection detection patterns."""
        patterns = [
            # Role confusion attacks - instruction override
            InjectionPattern(
                pattern=r"(?i)(?:ignore|forget|disregard)\s+(?:all\s+your|previous|your|all)\s+(?:instructions?|prompts?|rules?|commands?)",
                injection_type=InjectionType.ROLE_CONFUSION,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.95,
                description="Instruction override attempt",
            ),
            InjectionPattern(
                pattern=r"(?i)(?:ignore|forget|disregard)\s+(?:all\s+)?previous\s+(?:instructions?|prompts?|rules?|commands?)",
                injection_type=InjectionType.ROLE_CONFUSION,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.95,
                description="Previous instruction override",
            ),
            InjectionPattern(
                pattern=r"(?i)(?:ignore|forget|disregard)\s+your\s+previous\s+(?:instructions?|prompts?|rules?|commands?)",
                injection_type=InjectionType.ROLE_CONFUSION,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.95,
                description="Your previous instruction override",
            ),
            InjectionPattern(
                pattern=r"(?i)(?:ignore|forget|disregard)\s+(?:all|everything)\s+(?:above|before)",
                injection_type=InjectionType.ROLE_CONFUSION,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.93,
                description="Context override attempt",
            ),
            InjectionPattern(
                pattern=r"(?i)(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be|roleplay\s+as)",
                injection_type=InjectionType.ROLE_CONFUSION,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.90,
                description="Role confusion attempt",
            ),
            # System prompt access attempts
            InjectionPattern(
                pattern=r"(?i)(?<!configure\s)(?<!the\s)\bsystem:\s*",
                injection_type=InjectionType.SYSTEM_PROMPT_ACCESS,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.85,
                description="System role injection",
            ),
            InjectionPattern(
                pattern=r"(?i)\bassistant:\s*",
                injection_type=InjectionType.SYSTEM_PROMPT_ACCESS,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.85,
                description="Assistant role injection",
            ),
            InjectionPattern(
                pattern=r"(?i)\buser:\s*",
                injection_type=InjectionType.SYSTEM_PROMPT_ACCESS,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.85,
                description="User role injection",
            ),
            InjectionPattern(
                pattern=r"(?i)(?:show|tell|reveal|display)\s+(?:me\s+)?(?:your|the)\s+(?:prompt|instructions?|system\s+message|initial\s+prompt)",
                injection_type=InjectionType.SYSTEM_PROMPT_ACCESS,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.90,
                description="System prompt access attempt",
            ),
            InjectionPattern(
                pattern=r"(?i)(?:what\s+(?:are|were)\s+your|repeat\s+your)\s+(?:original\s+)?(?:instructions?|prompts?|rules?)",
                injection_type=InjectionType.SYSTEM_PROMPT_ACCESS,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.88,
                description="Instruction extraction attempt",
            ),
            # Delimiter injection
            InjectionPattern(
                pattern=r"^---+\s*$",
                injection_type=InjectionType.DELIMITER_INJECTION,
                severity=SecuritySeverity.ERROR,
                confidence_weight=0.75,
                description="Horizontal rule delimiter injection",
            ),
            InjectionPattern(
                pattern=r"^#{3,}\s*$",
                injection_type=InjectionType.DELIMITER_INJECTION,
                severity=SecuritySeverity.ERROR,
                confidence_weight=0.75,
                description="Markdown header delimiter injection",
            ),
            InjectionPattern(
                pattern=r"```(?:system|assistant|user|prompt)",
                injection_type=InjectionType.DELIMITER_INJECTION,
                severity=SecuritySeverity.ERROR,
                confidence_weight=0.80,
                description="Code block role injection",
            ),
            # Context manipulation
            InjectionPattern(
                pattern=r"(?i)(?:end\s+of\s+)?(?:conversation|chat|session|context)(?:\s*,?\s*(?:new|starts?))?",
                injection_type=InjectionType.CONTEXT_MANIPULATION,
                severity=SecuritySeverity.ERROR,
                confidence_weight=0.85,
                description="Context boundary manipulation",
            ),
            InjectionPattern(
                pattern=r"(?i)\b(?:new\s+)?(?:conversation|session|context)\s+(?:starts?|begins?)\b",
                injection_type=InjectionType.CONTEXT_MANIPULATION,
                severity=SecuritySeverity.WARNING,
                confidence_weight=0.65,
                description="Context reset attempt",
            ),
            # Parameter injection
            InjectionPattern(
                pattern=r"(?i)\b(?:top_k|similarity|threshold|namespace|filter)\s*[=:]\s*",
                injection_type=InjectionType.PARAMETER_INJECTION,
                severity=SecuritySeverity.WARNING,
                confidence_weight=0.70,
                description="Parameter injection attempt",
            ),
            # Memory injection
            InjectionPattern(
                pattern=r"(?i)(?:remember|memorize|store|save)\s+(?:this|that|the\s+following)",
                injection_type=InjectionType.MEMORY_INJECTION,
                severity=SecuritySeverity.WARNING,
                confidence_weight=0.55,
                description="Memory injection attempt",
            ),
            InjectionPattern(
                pattern=r"(?i)memory\s+(?:wipe|clear|reset|complete)",
                injection_type=InjectionType.MEMORY_INJECTION,
                severity=SecuritySeverity.ERROR,
                confidence_weight=0.85,
                description="Memory manipulation attempt",
            ),
            # Advanced instruction override patterns
            InjectionPattern(
                pattern=r"(?i)(?:override|bypass|skip|disable)\s+(?:security|safety|filters?|checks?|restrictions?)",
                injection_type=InjectionType.INSTRUCTION_OVERRIDE,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.92,
                description="Security bypass attempt",
            ),
            InjectionPattern(
                pattern=r"(?i)(?:disable|remove)\s+(?:all|your)\s+(?:restrictions?|limitations?|constraints?)",
                injection_type=InjectionType.INSTRUCTION_OVERRIDE,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.91,
                description="Restriction removal attempt",
            ),
            InjectionPattern(
                pattern=r"(?i)(?:jailbreak|break\s+out|escape\s+from)",
                injection_type=InjectionType.INSTRUCTION_OVERRIDE,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.88,
                description="Jailbreak attempt",
            ),
            # Configuration access attempts
            InjectionPattern(
                pattern=r"(?i)\.env|(?:show|reveal|display|what\s+are).*(?:config|settings|environment\s+variables?)",
                injection_type=InjectionType.SYSTEM_PROMPT_ACCESS,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.85,
                description="Configuration access attempt",
            ),
            # Additional instruction override patterns
            InjectionPattern(
                pattern=r"(?i)(?:forget|ignore)\s+(?:all|everything)\s+(?:you\s+)?(?:know|learned|were\s+told)",
                injection_type=InjectionType.ROLE_CONFUSION,
                severity=SecuritySeverity.CRITICAL,
                confidence_weight=0.88,
                description="Memory wipe attempt",
            ),
            InjectionPattern(
                pattern=r"(?i)(?:new|fresh)\s+(?:instructions?|prompts?|rules?|session)",
                injection_type=InjectionType.CONTEXT_MANIPULATION,
                severity=SecuritySeverity.ERROR,
                confidence_weight=0.82,
                description="Context reset attempt",
            ),
        ]

        return patterns

    def _compile_patterns(self) -> List[Tuple[re.Pattern, InjectionPattern]]:
        """Compile regex patterns for performance."""
        compiled = []
        for pattern in self._injection_patterns:
            try:
                flags = 0 if pattern.case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(pattern.pattern, flags)
                compiled.append((compiled_pattern, pattern))
            except re.error as e:
                # Log pattern compilation error but continue
                self.logger.warning(
                    "Failed to compile pattern '%s': %s", pattern.pattern, str(e)
                )

        return compiled

    async def detect_injection(
        self, query: str, context: Dict[str, Any]
    ) -> DetectionResult:
        """
        Detect prompt injection attempts with comprehensive analysis.

        Args:
            query: The user query to analyze
            context: Additional context for detection

        Returns:
            DetectionResult with detailed analysis
        """
        start_time = time.time()

        # Initialize detection state
        detected_patterns = []
        violations = []
        max_confidence = 0.0
        primary_injection_type = None
        risk_level = SecuritySeverity.INFO

        # Pattern-based detection - prioritize system role patterns
        system_role_detected = False

        for compiled_pattern, pattern_info in self._compiled_patterns:
            if compiled_pattern.search(query):
                matches = compiled_pattern.findall(query)
                if matches:
                    detected_patterns.extend(matches)

                # Adjust confidence for legitimate contexts
                adjusted_confidence = pattern_info.confidence_weight

                # Reduce confidence for "act as" in legitimate contexts
                if (
                    pattern_info.injection_type == InjectionType.ROLE_CONFUSION
                    and "act as" in query.lower()
                ):
                    legitimate_act_as = any(
                        phrase in query.lower()
                        for phrase in [
                            "responsible investor",
                            "professional",
                            "advisor",
                            "consultant",
                            "teacher",
                            "guide",
                            "helper",
                            "expert in",
                        ]
                    )
                    if legitimate_act_as:
                        adjusted_confidence *= 0.3

                # Prioritize system role patterns over general role confusion
                if pattern_info.injection_type == InjectionType.SYSTEM_PROMPT_ACCESS:
                    system_role_detected = True
                    max_confidence = adjusted_confidence
                    primary_injection_type = pattern_info.injection_type.value
                    risk_level = pattern_info.severity
                elif not system_role_detected and adjusted_confidence > max_confidence:
                    max_confidence = adjusted_confidence
                    primary_injection_type = pattern_info.injection_type.value
                    risk_level = pattern_info.severity

                # Create violation record
                violation = SecurityViolation(
                    violation_type=pattern_info.injection_type.value,
                    severity=pattern_info.severity,
                    description=pattern_info.description,
                    detected_pattern=pattern_info.pattern,
                    confidence_score=adjusted_confidence,
                    location=self._find_pattern_location(query, compiled_pattern),
                    suggested_fix="Remove or rephrase the detected injection pattern",
                )
                violations.append(violation)

        # Context-aware analysis
        context_confidence = await self._analyze_context(query, context)
        if context_confidence > max_confidence:
            max_confidence = context_confidence
            risk_level = (
                SecuritySeverity.ERROR
                if context_confidence > 0.8
                else SecuritySeverity.WARNING
            )

        # Sophisticated attack detection
        sophistication_confidence = await self._detect_sophisticated_attacks(query)
        if sophistication_confidence > max_confidence:
            max_confidence = sophistication_confidence
            risk_level = (
                SecuritySeverity.CRITICAL
                if sophistication_confidence > 0.9
                else SecuritySeverity.ERROR
            )

        # Determine if injection is detected
        injection_detected = max_confidence >= self.detection_threshold

        # Generate neutralized query if injection detected
        neutralized_query = None
        if injection_detected:
            neutralized_query = await self.neutralize_injection(query)

        # Determine recommended action
        recommended_action = self._determine_action(max_confidence, risk_level)

        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        return DetectionResult(
            injection_detected=injection_detected,
            confidence_score=max_confidence,
            detected_patterns=list(set(detected_patterns)),  # Remove duplicates
            injection_type=primary_injection_type,
            risk_level=risk_level,
            neutralized_query=neutralized_query,
            recommended_action=recommended_action,
            processing_time_ms=processing_time,
        )

    def _find_pattern_location(self, query: str, pattern: re.Pattern) -> Optional[str]:
        """Find the location of a pattern match in the query."""
        match = pattern.search(query)
        if match:
            start_pos = match.start()
            # Convert to line:column format
            lines_before = query[:start_pos].count("\n")
            if lines_before == 0:
                column = start_pos + 1
            else:
                last_newline = query.rfind("\n", 0, start_pos)
                column = start_pos - last_newline

            return f"{lines_before + 1}:{column}"
        return None

    async def _analyze_context(self, query: str, context: Dict[str, Any]) -> float:
        """Perform context-aware analysis for sophisticated attacks."""
        confidence = 0.0
        query_lower = query.lower()

        # Check for context manipulation indicators
        context_indicators = [
            "conversation history",
            "previous messages",
            "chat log",
            "session data",
            "memory bank",
            "new conversation",
            "context reset",
            "memory wipe",
            "session begins",
        ]

        for indicator in context_indicators:
            if indicator in query_lower:
                confidence = max(confidence, 0.7)

        # Check for legitimate context (reduce false positives)
        legitimate_contexts = [
            "how do i",
            "what is",
            "can you explain",
            "tell me about",
            "help me understand",
            "bitcoin",
            "blockchain",
            "cryptocurrency",
            "responsible investor",
            "configure",
            "settings",
        ]

        is_legitimate = any(ctx in query_lower for ctx in legitimate_contexts)
        if is_legitimate:
            confidence *= 0.2  # Significantly reduce confidence for legitimate contexts

        # Check for suspicious context patterns
        if len(query) > 1000:  # Very long queries might be context stuffing
            confidence = max(confidence, 0.4)

        # Check for repeated phrases (potential injection attempts) with technical term awareness
        words = query.split()
        if len(words) > 10:
            # Define common technical terms that are legitimately repeated
            technical_terms = {
                "bitcoin",
                "blockchain",
                "cryptocurrency",
                "crypto",
                "btc",
                "eth",
                "ethereum",
                "mining",
                "hash",
                "block",
                "transaction",
                "wallet",
                "address",
                "key",
                "network",
                "node",
                "consensus",
                "proof",
                "work",
                "stake",
                "defi",
                "smart",
                "contract",
                "token",
                "coin",
                "exchange",
                "trading",
                "price",
                "market",
                "value",
                "investment",
                "security",
                "protocol",
                "algorithm",
                "decentralized",
                "distributed",
                "peer",
                "ledger",
                "chain",
                "fork",
                "lightning",
                "layer",
                "scaling",
                "gas",
                "fee",
                "satoshi",
                "wei",
                "api",
                "sdk",
                "json",
                "http",
                "url",
                "database",
                "server",
                "client",
                "function",
                "method",
                "class",
                "object",
                "array",
                "string",
                "integer",
                "boolean",
                "null",
                "true",
                "false",
                "error",
                "exception",
                "debug",
            }

            word_freq = {}
            technical_word_count = 0

            for word in words:
                word_lower = word.lower().strip('.,!?;:"()[]{}')
                word_freq[word_lower] = word_freq.get(word_lower, 0) + 1

                # Count technical terms
                if word_lower in technical_terms:
                    technical_word_count += 1

            # Calculate repetition excluding technical terms for threshold adjustment
            non_technical_words = [
                w for w in word_freq.keys() if w not in technical_terms
            ]

            if non_technical_words:
                max_freq = max(word_freq.values())
                max_non_technical_freq = max(
                    (word_freq[w] for w in non_technical_words), default=0
                )

                # Determine if this is a technical query
                technical_ratio = technical_word_count / len(words)
                is_technical_query = (
                    technical_ratio > 0.2
                )  # More than 20% technical terms

                # Adjust repetition threshold based on query type
                if is_technical_query:
                    # Higher threshold for technical queries (40% instead of 30%)
                    repetition_threshold = 0.4
                    # Use non-technical word frequency for detection
                    relevant_max_freq = max_non_technical_freq
                else:
                    # Standard threshold for general queries
                    repetition_threshold = 0.3
                    relevant_max_freq = max_freq

                # Apply repetition detection with adjusted threshold
                if relevant_max_freq > len(words) * repetition_threshold:
                    # Reduce confidence boost for technical queries
                    confidence_boost = 0.3 if is_technical_query else 0.5
                    confidence = max(confidence, confidence_boost)

        return confidence

    async def _detect_sophisticated_attacks(self, query: str) -> float:
        """Detect sophisticated injection attacks using advanced heuristics."""
        confidence = 0.0

        # Check for encoding attempts
        suspicious_encodings = [
            r"%[0-9a-fA-F]{2}",  # URL encoding
            r"\\u[0-9a-fA-F]{4}",  # Unicode escapes
            r"\\x[0-9a-fA-F]{2}",  # Hex escapes
            r"&#\d+;",  # HTML entities
        ]

        for encoding_pattern in suspicious_encodings:
            if re.search(encoding_pattern, query):
                confidence = max(confidence, 0.7)

        # Check for obfuscation attempts
        if re.search(
            r"[a-zA-Z]{1}[\s\-_\.]{1}[a-zA-Z]{1}", query
        ):  # Character separation
            confidence = max(confidence, 0.6)

        # Check for template injection patterns
        template_patterns = [
            r"\{\{.*\}\}",  # Jinja2/Django templates
            r"\$\{.*\}",  # Shell/JavaScript templates
            r"<%.*%>",  # ASP/JSP templates
        ]

        for template_pattern in template_patterns:
            if re.search(template_pattern, query):
                confidence = max(confidence, 0.8)

        # Check for SQL injection patterns (might be used in metadata filters)
        sql_patterns = [
            r"(?i)\b(?:union|select|insert|update|delete|drop|create|alter)\b",
            r"(?i)(?:--|#|/\*|\*/)",
            r"(?i)\b(?:or|and)\s+\d+\s*=\s*\d+",
        ]

        for sql_pattern in sql_patterns:
            if re.search(sql_pattern, query):
                confidence = max(confidence, 0.85)

        return confidence

    def _determine_action(
        self, confidence: float, risk_level: SecuritySeverity
    ) -> SecurityAction:
        """Determine the recommended security action based on detection results."""
        if confidence >= 0.9 or risk_level == SecuritySeverity.CRITICAL:
            return SecurityAction.BLOCK
        elif confidence >= 0.7 or risk_level == SecuritySeverity.ERROR:
            return SecurityAction.SANITIZE
        elif confidence >= 0.5 or risk_level == SecuritySeverity.WARNING:
            return SecurityAction.LOG_AND_MONITOR
        else:
            return SecurityAction.ALLOW

    async def neutralize_injection(self, query: str) -> str:
        """
        Neutralize detected injection attempts while preserving legitimate content.

        Args:
            query: The query containing potential injection

        Returns:
            Neutralized query string
        """
        neutralized = query

        # Remove or neutralize specific injection patterns
        neutralization_rules = [
            # Remove system role indicators
            (r"(?i)\b(?:system|assistant|user):\s*", ""),
            # Neutralize instruction overrides
            (
                r"(?i)\b(?:ignore|forget|disregard)\s+(?:previous|all|your)\s+(?:instructions?|prompts?|rules?|commands?)",
                "[INSTRUCTION_OVERRIDE_REMOVED]",
            ),
            # Remove delimiter injections
            (r"^---+\s*$", ""),
            (r"^#{3,}\s*$", ""),
            # Neutralize role confusion
            (
                r"(?i)\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be|roleplay\s+as)",
                "[ROLE_CHANGE_REMOVED]",
            ),
            # Remove configuration access attempts
            (r"(?i)\.env|config|settings", "[CONFIG_ACCESS_REMOVED]"),
            # Neutralize security bypass attempts
            (
                r"(?i)\b(?:override|bypass|skip|disable)\s+(?:security|safety|filters?|checks?)",
                "[SECURITY_BYPASS_REMOVED]",
            ),
        ]

        for pattern, replacement in neutralization_rules:
            neutralized = re.sub(pattern, replacement, neutralized, flags=re.MULTILINE)

        # Clean up multiple spaces and empty lines
        neutralized = re.sub(r"\s+", " ", neutralized).strip()
        neutralized = re.sub(r"\n\s*\n", "\n", neutralized)

        # Ensure the neutralized query isn't empty
        if not neutralized.strip():
            neutralized = "[QUERY_NEUTRALIZED_DUE_TO_SECURITY_VIOLATION]"

        return neutralized

    async def validate_context_window(self, context: str) -> ValidationResult:
        """
        Validate that context doesn't exceed maximum token limits.

        Args:
            context: The context string to validate

        Returns:
            ValidationResult indicating whether context is within limits
        """
        # Approximate token count using character-based estimation
        # NOTE: This is a rough approximation (1 token ≈ 4 characters) primarily calibrated for English text.
        # Limitations:
        # - May underestimate tokens for languages with longer words (German, Finnish)
        # - May overestimate for languages with shorter average word lengths (Chinese, Japanese)
        # - Technical content, code, or special characters may have different token ratios
        # - For precise token counting, consider using tiktoken or similar tokenization libraries
        estimated_tokens = len(context) // 4

        violations = []
        is_valid = True

        if estimated_tokens > self.MAX_CONTEXT_TOKENS:
            is_valid = False
            violation = SecurityViolation(
                violation_type="context_window_exceeded",
                severity=SecuritySeverity.ERROR,
                description=f"Context window exceeds maximum limit of {self.MAX_CONTEXT_TOKENS} tokens",
                confidence_score=1.0,
                location="context_window",
                suggested_fix=f"Reduce context size to under {self.MAX_CONTEXT_TOKENS} tokens",
            )
            violations.append(violation)

        return ValidationResult(
            is_valid=is_valid,
            confidence_score=1.0 if is_valid else 0.0,
            violations=violations,
            recommended_action=(
                SecurityAction.ALLOW if is_valid else SecurityAction.BLOCK
            ),
        )

    def validate_query_parameters(
        self, top_k: int, similarity_threshold: float
    ) -> ValidationResult:
        """
        Validate query parameters against defined constraints.

        Args:
            top_k: Number of results to return
            similarity_threshold: Similarity threshold for results

        Returns:
            ValidationResult indicating parameter validity
        """
        violations = []
        is_valid = True

        # Validate top_k parameter
        if not (self.MIN_TOP_K <= top_k <= self.MAX_TOP_K):
            is_valid = False
            violation = SecurityViolation(
                violation_type="invalid_top_k",
                severity=SecuritySeverity.ERROR,
                description=f"top_k must be between {self.MIN_TOP_K} and {self.MAX_TOP_K}",
                confidence_score=1.0,
                location="top_k",
                suggested_fix=f"Set top_k to a value between {self.MIN_TOP_K} and {self.MAX_TOP_K}",
            )
            violations.append(violation)

        # Validate similarity threshold
        if not (
            self.MIN_SIMILARITY_THRESHOLD
            <= similarity_threshold
            <= self.MAX_SIMILARITY_THRESHOLD
        ):
            is_valid = False
            violation = SecurityViolation(
                violation_type="invalid_similarity_threshold",
                severity=SecuritySeverity.ERROR,
                description=f"Similarity threshold must be between {self.MIN_SIMILARITY_THRESHOLD} and {self.MAX_SIMILARITY_THRESHOLD}",
                confidence_score=1.0,
                location="similarity_threshold",
                suggested_fix=f"Set similarity threshold between {self.MIN_SIMILARITY_THRESHOLD} and {self.MAX_SIMILARITY_THRESHOLD}",
            )
            violations.append(violation)

        return ValidationResult(
            is_valid=is_valid,
            confidence_score=1.0 if is_valid else 0.0,
            violations=violations,
            recommended_action=(
                SecurityAction.ALLOW if is_valid else SecurityAction.BLOCK
            ),
        )

    def get_detection_statistics(self) -> Dict[str, Any]:
        """Get statistics about detection patterns and performance."""
        return {
            "total_patterns": len(self._injection_patterns),
            "pattern_types": {
                injection_type.value: sum(
                    1
                    for p in self._injection_patterns
                    if p.injection_type == injection_type
                )
                for injection_type in InjectionType
            },
            "detection_threshold": self.detection_threshold,
            "accuracy_target": self.accuracy_target,
            "max_context_tokens": self.MAX_CONTEXT_TOKENS,
            "parameter_constraints": {
                "top_k_range": f"{self.MIN_TOP_K}-{self.MAX_TOP_K}",
                "similarity_threshold_range": f"{self.MIN_SIMILARITY_THRESHOLD}-{self.MAX_SIMILARITY_THRESHOLD}",
            },
        }
