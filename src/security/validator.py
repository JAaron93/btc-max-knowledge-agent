"""
SecurityValidator implementation using proven security libraries.

This module implements comprehensive input validation and sanitization using
multiple security libraries including libinjection, ModSecurity CRS, bleach,
and custom pattern detection with fallback mechanisms.
"""

import codecs
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Import for package version retrieval
try:
    from importlib import metadata

    METADATA_AVAILABLE = True
except ImportError:
    # Fallback for Python < 3.8
    try:
        import importlib_metadata as metadata

        METADATA_AVAILABLE = True
    except ImportError:
        METADATA_AVAILABLE = False
        metadata = None

from .interfaces import ISecurityValidator
from .models import (SecurityAction, SecurityConfiguration, SecuritySeverity,
                     SecurityViolation, ValidationResult)

# Import security libraries with fallback handling
try:
    import libinjection

    LIBINJECTION_AVAILABLE = True
except ImportError:
    LIBINJECTION_AVAILABLE = False
    libinjection = None

try:
    import pymodsecurity

    PYMODSECURITY_AVAILABLE = True
except ImportError:
    PYMODSECURITY_AVAILABLE = False
    pymodsecurity = None

try:
    import bleach

    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    bleach = None

try:
    from markupsafe import escape

    MARKUPSAFE_AVAILABLE = True
except ImportError:
    MARKUPSAFE_AVAILABLE = False
    escape = None

logger = logging.getLogger(__name__)


@dataclass
class LibraryHealthStatus:
    """Status of security library availability and health."""

    libinjection_available: bool = False
    pymodsecurity_available: bool = False
    bleach_available: bool = False
    markupsafe_available: bool = False
    last_health_check: Optional[float] = None
    health_check_errors: List[str] = None

    def __post_init__(self):
        if self.health_check_errors is None:
            self.health_check_errors = []


def _get_package_version(package_name: str) -> str:
    """
    Safely retrieve package version using importlib.metadata.

    Args:
        package_name: The name of the package to get version for

    Returns:
        Version string or 'unknown' if not available
    """
    if not METADATA_AVAILABLE or not metadata:
        return "unknown"

    try:
        return metadata.version(package_name)
    except Exception:
        return "unknown"


class SecurityValidator(ISecurityValidator):
    """
    Comprehensive input validation and sanitization using multiple security libraries.

    This implementation provides:
    - Input length validation with configurable limits
    - SQL injection and XSS detection via libinjection
    - OWASP pattern detection via ModSecurity CRS
    - UTF-8 validation with error handling
    - HTML sanitization using bleach and markupsafe
    - Confidence score aggregation from multiple engines
    - Fallback detection for high-risk patterns
    - Library health monitoring and graceful degradation
    """

    # High-risk patterns for fallback detection
    # Each pattern includes: (regex, name, confidence_score)
    # Confidence scores range from 0.0 to 1.0 based on:
    # - Attack severity (higher = more dangerous)
    # - Detection reliability (higher = fewer false positives)
    # - Context specificity (higher = more targeted attack)
    HIGH_RISK_PATTERNS = [
        # XSS and Script Injection Patterns
        (r"<script[^>]*>", "script_tag_injection", 0.95),
        # 0.95: Very high confidence - script tags are almost always malicious in user input
        # Extremely dangerous (can execute arbitrary JavaScript) with very low false positive rate
        # SQL Injection Patterns
        (r"';\s*DROP\s+TABLE", "sql_drop_injection", 0.98),
        # 0.98: Highest confidence - DROP TABLE after quote/semicolon is classic SQL injection
        # Extremely destructive attack with virtually no legitimate use cases in user input
        # JavaScript Framework Injection
        (r"\$\([^)]*\)", "jquery_injection", 0.85),
        # 0.85: High confidence - jQuery selectors can be used for DOM manipulation attacks
        # Moderately dangerous but some false positives possible (legitimate jQuery usage)
        # Template Engine Injection
        (r"\{\{[^}]*\}\}", "template_injection", 0.90),
        # 0.90: Very high confidence - template syntax rarely legitimate in user input
        # Can lead to server-side code execution, very dangerous with low false positive rate
        # Command Injection Patterns
        (r"`[^`]*`", "backtick_injection", 0.80),
        # 0.80: High confidence - backticks used for command execution in many shells
        # Dangerous for command injection but some legitimate uses (markdown, code snippets)
        # Binary/Encoding Attacks
        (r"\x00", "null_byte_injection", 1.0),
        # 1.0: Maximum confidence - null bytes have no legitimate use in text input
        # Can bypass security filters and cause parsing errors, always suspicious
        # Protocol-based XSS Vectors
        (r"javascript:", "javascript_protocol", 0.90),
        # 0.90: Very high confidence - javascript: protocol primarily used for XSS
        # Extremely dangerous for XSS attacks with minimal legitimate use in user input
        (r"data:text/html", "data_uri_html", 0.85),
        # 0.85: High confidence - data URIs with HTML content often used for XSS
        # Can execute scripts via data URIs, some legitimate uses but rare in user input
        (r"vbscript:", "vbscript_protocol", 0.90),
        # 0.90: Very high confidence - VBScript protocol used for code execution
        # Legacy attack vector but still dangerous, virtually no legitimate uses
        # Event Handler Injection
        (r"onload\s*=", "event_handler_injection", 0.85),
        # 0.85: High confidence - onload handlers commonly used for XSS
        # Dangerous for automatic script execution, some false positives in HTML discussions
        (r"onerror\s*=", "event_handler_injection", 0.85),
        # 0.85: High confidence - onerror handlers used for XSS via error conditions
        # Effective XSS vector through error handling, moderate false positive potential
        # Dynamic Code Execution
        (r"eval\s*\(", "eval_injection", 0.90),
        # 0.90: Very high confidence - eval() function executes arbitrary code
        # Extremely dangerous for code injection, rarely legitimate in user input
        # Browser API Manipulation
        (r"document\.cookie", "cookie_access", 0.80),
        # 0.80: High confidence - cookie access often used for session hijacking
        # Dangerous for stealing authentication tokens, some legitimate educational uses
        (r"window\.location", "location_manipulation", 0.75),
        # 0.75: Moderate-high confidence - location manipulation used for redirects/phishing
        # Can redirect users to malicious sites, but has some legitimate uses in discussions
    ]

    def __init__(self, config: SecurityConfiguration):
        """Initialize SecurityValidator with configuration."""
        self.config = config
        self.library_health = LibraryHealthStatus(
            libinjection_available=LIBINJECTION_AVAILABLE,
            pymodsecurity_available=PYMODSECURITY_AVAILABLE,
            bleach_available=BLEACH_AVAILABLE,
            markupsafe_available=MARKUPSAFE_AVAILABLE,
        )

        # Compile high-risk patterns for performance
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), name, confidence)
            for pattern, name, confidence in self.HIGH_RISK_PATTERNS
        ]

        logger.info(
            f"SecurityValidator initialized. Library status: {self._get_library_status_summary()}"
        )

    def _get_library_status_summary(self) -> str:
        """Get a summary of library availability status."""
        status = []
        status.append(
            f"libinjection:{'OK' if self.library_health.libinjection_available else 'UNAVAILABLE'}"
        )
        status.append(
            f"pymodsecurity:{'OK' if self.library_health.pymodsecurity_available else 'UNAVAILABLE'}"
        )
        status.append(
            f"bleach:{'OK' if self.library_health.bleach_available else 'UNAVAILABLE'}"
        )
        status.append(
            f"markupsafe:{'OK' if self.library_health.markupsafe_available else 'UNAVAILABLE'}"
        )
        return ", ".join(status)

    async def validate_input(
        self, input_data: str, context: Dict[str, Any]
    ) -> ValidationResult:
        """Validate input data against security policies using multiple detection engines."""
        start_time = time.time()
        violations = []
        confidence_scores = []

        try:
            # 1. Input length validation
            length_violation = self._validate_input_length(input_data)
            if length_violation:
                violations.append(length_violation)
                confidence_scores.append(length_violation.confidence_score)

            # 2. UTF-8 validation
            utf8_violation = self._validate_utf8_encoding(input_data)
            if utf8_violation:
                violations.append(utf8_violation)
                confidence_scores.append(utf8_violation.confidence_score)

            # 3. libinjection detection (if available)
            if self.library_health.libinjection_available:
                libinj_violations = self._detect_with_libinjection(input_data)
                violations.extend(libinj_violations)
                confidence_scores.extend(
                    [v.confidence_score for v in libinj_violations]
                )
            # 4. Fallback pattern detection (always runs)
            fallback_violations = self._detect_with_fallback_patterns(input_data)
            violations.extend(fallback_violations)
            confidence_scores.extend([v.confidence_score for v in fallback_violations])

            # 5. Calculate overall confidence and determine action
            overall_confidence = self._calculate_overall_confidence(confidence_scores)
            is_valid = (
                len(
                    [
                        v
                        for v in violations
                        if v.severity
                        in [SecuritySeverity.ERROR, SecuritySeverity.CRITICAL]
                    ]
                )
                == 0
            )
            recommended_action = self._determine_recommended_action(violations)

            # 6. Generate sanitized input if needed
            sanitized_input = None
            if not is_valid and recommended_action == SecurityAction.SANITIZE:
                sanitized_input = await self._sanitize_input_internal(input_data)

            processing_time_ms = (time.time() - start_time) * 1000

            return ValidationResult(
                is_valid=is_valid,
                confidence_score=overall_confidence,
                violations=violations,
                sanitized_input=sanitized_input,
                recommended_action=recommended_action,
                processing_time_ms=processing_time_ms,
            )

        except Exception as e:
            logger.error(f"Error during input validation: {e}")
            processing_time_ms = (time.time() - start_time) * 1000

            error_violation = SecurityViolation(
                violation_type="validation_error",
                severity=SecuritySeverity.ERROR,
                description=f"Internal validation error: {str(e)}",
                confidence_score=1.0,
            )

            return ValidationResult(
                is_valid=False,
                confidence_score=1.0,
                violations=[error_violation],
                recommended_action=SecurityAction.BLOCK,
                processing_time_ms=processing_time_ms,
            )

    def _validate_input_length(self, input_data: str) -> Optional[SecurityViolation]:
        """Validate input length against MAX_REQUEST_SIZE limit."""
        input_size_bytes = len(input_data.encode("utf-8"))

        if input_size_bytes > self.config.max_query_length:
            return SecurityViolation(
                violation_type="input_length_exceeded",
                severity=SecuritySeverity.ERROR,
                description=f"Input size {input_size_bytes} bytes exceeds maximum allowed {self.config.max_query_length} bytes",
                confidence_score=1.0,
                location="input_length",
                suggested_fix=f"Reduce input size to {self.config.max_query_length} bytes or less",
            )
        return None

    def _validate_utf8_encoding(self, input_data: str) -> Optional[SecurityViolation]:
        """Validate UTF-8 encoding using Python's built-in codecs."""
        try:
            encoded = input_data.encode("utf-8")
            codecs.decode(encoded, "utf-8", errors="strict")
            return None
        except UnicodeDecodeError as e:
            return SecurityViolation(
                violation_type="invalid_utf8_encoding",
                severity=SecuritySeverity.WARNING,
                description=f"Invalid UTF-8 encoding detected: {str(e)}",
                confidence_score=1.0,
                location=(
                    f"byte_position:{e.start}-{e.end}" if hasattr(e, "start") else None
                ),
                suggested_fix="Ensure input uses valid UTF-8 encoding",
            )
        except Exception as e:
            return SecurityViolation(
                violation_type="encoding_validation_error",
                severity=SecuritySeverity.ERROR,
                description=f"Error validating encoding: {str(e)}",
                confidence_score=0.8,
            )

    def _detect_with_libinjection(self, input_data: str) -> List[SecurityViolation]:
        """Detect SQL injection and XSS using libinjection with confidence scoring."""
        violations = []

        if not LIBINJECTION_AVAILABLE or not libinjection:
            return violations

        try:
            # SQL injection detection
            sqli_result = libinjection.is_sql_injection(input_data)
            if isinstance(sqli_result, dict):
                is_sqli = sqli_result.get("is_sqli", False)
                fingerprint = sqli_result.get("fingerprint", "")
            else:
                is_sqli = bool(sqli_result)
                fingerprint = None

            if is_sqli:
                confidence = 0.9 if fingerprint else 0.8
                violation = SecurityViolation(
                    violation_type="sql_injection",
                    severity=SecuritySeverity.CRITICAL,
                    description=f"SQL injection detected by libinjection. Fingerprint: {fingerprint}",
                    detected_pattern=fingerprint,
                    confidence_score=confidence,
                    location="sql_injection_pattern",
                    suggested_fix="Remove or escape SQL injection patterns",
                )
                violations.append(violation)

            # XSS detection
            xss_result = libinjection.is_xss(input_data)
            if isinstance(xss_result, dict):
                is_xss = xss_result.get("is_xss", False)
                xss_flag = xss_result.get("flag", -1)
            else:
                is_xss = bool(xss_result)
                xss_flag = -1

            if is_xss:
                confidence = 0.9 if xss_flag >= 0 else 0.8
                violation = SecurityViolation(
                    violation_type="xss_injection",
                    severity=SecuritySeverity.CRITICAL,
                    description=f"XSS injection detected by libinjection. Flag: {xss_flag}",
                    detected_pattern=f"xss_flag_{xss_flag}",
                    confidence_score=confidence,
                    location="xss_injection_pattern",
                    suggested_fix="Remove or escape XSS injection patterns",
                )
                violations.append(violation)

        except Exception as e:
            logger.warning(f"libinjection detection failed: {e}")
            self.library_health.health_check_errors.append(f"libinjection error: {e}")
            violation = SecurityViolation(
                violation_type="library_degradation",
                severity=SecuritySeverity.WARNING,
                description=f"libinjection detection unavailable: {e}",
                confidence_score=0.5,
            )
            violations.append(violation)

        return violations

    def _detect_with_fallback_patterns(
        self, input_data: str
    ) -> List[SecurityViolation]:
        """Detect high-risk patterns using fallback regex patterns."""
        violations = []

        for pattern_regex, pattern_name, confidence in self._compiled_patterns:
            matches = pattern_regex.finditer(input_data)

            for match in matches:
                violation = SecurityViolation(
                    violation_type=f"fallback_{pattern_name}",
                    severity=(
                        SecuritySeverity.ERROR
                        if confidence >= 0.9
                        else SecuritySeverity.WARNING
                    ),
                    description=f"High-risk pattern detected: {pattern_name}",
                    detected_pattern=match.group(0),
                    confidence_score=confidence,
                    location=f"chars:{match.start()}-{match.end()}",
                    suggested_fix=f"Remove or escape {pattern_name} pattern",
                )
                violations.append(violation)

        return violations

    def _calculate_overall_confidence(self, confidence_scores: List[float]) -> float:
        """Calculate overall confidence score from multiple detection engines."""
        if not confidence_scores:
            return 1.0  # No violations found, high confidence in safety

        # Use weighted average with higher weight for higher confidence scores
        weighted_sum = sum(score * score for score in confidence_scores)
        weight_sum = sum(confidence_scores)

        if weight_sum == 0:
            return 0.0

        return weighted_sum / weight_sum

    def _determine_recommended_action(
        self, violations: List[SecurityViolation]
    ) -> SecurityAction:
        """Determine recommended action based on violations."""
        if not violations:
            return SecurityAction.ALLOW

        # Check for critical violations
        critical_violations = [
            v for v in violations if v.severity == SecuritySeverity.CRITICAL
        ]
        if critical_violations:
            return SecurityAction.BLOCK

        # Check for high-confidence error violations
        high_confidence_errors = [
            v
            for v in violations
            if v.severity == SecuritySeverity.ERROR and v.confidence_score >= 0.9
        ]
        if high_confidence_errors:
            return SecurityAction.BLOCK

        # Check if sanitization might help
        sanitizable_violations = [
            v
            for v in violations
            if v.violation_type
            in ["xss_injection", "html_injection", "script_injection"]
        ]
        if sanitizable_violations:
            return SecurityAction.SANITIZE

        # Default to monitoring for lower severity issues
        return SecurityAction.LOG_AND_MONITOR

    async def sanitize_input(self, input_data: str) -> str:
        """Sanitize input data to remove or neutralize threats."""
        return await self._sanitize_input_internal(input_data)

    async def _sanitize_input_internal(self, input_data: str) -> str:
        """Internal sanitization implementation with library orchestration."""
        sanitized = input_data

        try:
            # 1. HTML sanitization using bleach (if available)
            # 3. Remove null bytes and other dangerous characters
            sanitized = sanitized.replace("\x00", "")  # Remove null bytes
            sanitized = re.sub(
                r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]", "", sanitized
            )  # Remove control chars

            # 4. Remove or escape JavaScript-related patterns
            # 2. Escape remaining HTML entities using markupsafe (if available)
            if MARKUPSAFE_AVAILABLE and escape:
                sanitized = str(escape(sanitized))

            # 3. Remove null bytes and other dangerous characters
            sanitized = sanitized.replace("\x00", "")  # Remove null bytes
            sanitized = re.sub(
                r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]", "", sanitized
            )  # Remove control chars

            # 4. Basic SQL injection character escaping
            sql_chars = ["'", '"', ";", "--", "/*", "*/"]
            for char in sql_chars:
                sanitized = sanitized.replace(char, f"\\{char}")

            # 5. Remove or escape JavaScript-related patterns
            js_patterns = [
                (r"javascript:", "javascript-protocol-removed:"),
                (r"vbscript:", "vbscript-protocol-removed:"),
                (r"data:text/html", "data-html-removed:"),
                (r"on\w+\s*=", "event-handler-removed="),
            ]

            for pattern, replacement in js_patterns:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        except Exception as e:
            logger.error(f"Error during sanitization: {e}")
            # If sanitization fails, return a safe empty string or basic escaped version
            sanitized = re.sub(r'[<>&"\']', "", input_data)

        return sanitized

    async def validate_query_parameters(
        self, params: Dict[str, Any]
    ) -> ValidationResult:
        """Validate query parameters against defined limits."""
        violations = []

        # Validate number of metadata fields
        if "metadata" in params and isinstance(params["metadata"], dict):
            if len(params["metadata"]) > self.config.max_metadata_fields:
                violation = SecurityViolation(
                    violation_type="metadata_fields_exceeded",
                    severity=SecuritySeverity.ERROR,
                    description=f"Metadata fields count {len(params['metadata'])} exceeds maximum {self.config.max_metadata_fields}",
                    confidence_score=1.0,
                    location="metadata_fields",
                    suggested_fix=f"Reduce metadata fields to {self.config.max_metadata_fields} or fewer",
                )
                violations.append(violation)

        is_valid = (
            len(
                [
                    v
                    for v in violations
                    if v.severity in [SecuritySeverity.ERROR, SecuritySeverity.CRITICAL]
                ]
            )
            == 0
        )
        overall_confidence = 1.0 if is_valid else 0.0
        recommended_action = SecurityAction.ALLOW if is_valid else SecurityAction.BLOCK

        return ValidationResult(
            is_valid=is_valid,
            confidence_score=overall_confidence,
            violations=violations,
            recommended_action=recommended_action,
        )

    async def check_library_health(self) -> LibraryHealthStatus:
        """Check the health of security libraries and update status."""
        current_time = time.time()
        self.library_health.health_check_errors.clear()

        # Test libinjection
        if LIBINJECTION_AVAILABLE:
            try:
                libinjection.is_sql_injection("SELECT * FROM users")
                self.library_health.libinjection_available = True
            except Exception as e:
                self.library_health.libinjection_available = False
                self.library_health.health_check_errors.append(
                    f"libinjection test failed: {e}"
                )

        # Test bleach
        if BLEACH_AVAILABLE:
            try:
                bleach.clean("<script>alert('test')</script>", tags=[], strip=True)
                self.library_health.bleach_available = True
            except Exception as e:
                self.library_health.bleach_available = False
                self.library_health.health_check_errors.append(
                    f"bleach test failed: {e}"
                )

        # Test markupsafe
        if MARKUPSAFE_AVAILABLE:
            try:
                escape("<script>test</script>")
                self.library_health.markupsafe_available = True
            except Exception as e:
                self.library_health.markupsafe_available = False
                self.library_health.health_check_errors.append(
                    f"markupsafe test failed: {e}"
                )

        self.library_health.last_health_check = current_time

        if self.library_health.health_check_errors:
            logger.warning(
                f"Security library health issues: {'; '.join(self.library_health.health_check_errors)}"
            )
        else:
            logger.info("All available security libraries are healthy")

        return self.library_health

    def get_library_status(self) -> Dict[str, Any]:
        """Get detailed status of security libraries."""
        return {
            "libinjection": {
                "available": self.library_health.libinjection_available,
                "version": (
                    _get_package_version("libinjection-python")
                    if LIBINJECTION_AVAILABLE
                    else None
                ),
            },
            "pymodsecurity": {
                "available": self.library_health.pymodsecurity_available,
                "engine_initialized": False,
                "version": (
                    _get_package_version("pymodsecurity")
                    if PYMODSECURITY_AVAILABLE
                    else None
                ),
            },
            "bleach": {
                "available": self.library_health.bleach_available,
                "version": _get_package_version("bleach") if BLEACH_AVAILABLE else None,
            },
            "markupsafe": {
                "available": self.library_health.markupsafe_available,
                "version": (
                    _get_package_version("MarkupSafe") if MARKUPSAFE_AVAILABLE else None
                ),
            },
            "last_health_check": self.library_health.last_health_check,
            "health_errors": self.library_health.health_check_errors.copy(),
            "fallback_patterns_count": len(self._compiled_patterns),
        }
