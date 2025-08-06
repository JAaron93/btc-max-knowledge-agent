"""
Security module for BTC Max Knowledge Agent.

This module provides comprehensive security infrastructure including:
- Input validation and sanitization
- Authentication and authorization
- Prompt injection detection
- Rate limiting and DoS protection
- Security monitoring and logging
- Configuration management
"""

import logging
import os
from typing import TYPE_CHECKING

# Configure debug logging for lazy loading
_DEBUG_LAZY_LOADING = os.getenv("SECURITY_DEBUG_LAZY_LOADING", "").lower() in (
    "true",
    "1",
    "yes",
    "on",
)
_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # Import types for static type checkers without runtime overhead
    from .config import SecurityConfigurationManager  # noqa: F401
    from .interfaces import (  # noqa: F401
        IAuthenticationManager,
        IConfigurationValidator,
        IPromptInjectionDetector,
        IRateLimitManager,
        ISecurePineconeClient,
        ISecurityMonitor,
        ISecurityValidator,
    )
    from .models import (  # noqa: F401
        Anomaly,
        AuthenticationContext,
        AuthenticationStatus,
        AuthResult,
        DetectionResult,
        PineconeResponse,
        RateLimitResult,
        RateLimitStatus,
        ResourceMetrics,
        SecureQuery,
        SecureResponse,
        SecurityAction,
        SecurityConfiguration,
        SecurityErrorResponse,
        SecurityEvent,
        SecurityEventType,
        SecuritySeverity,
        SecurityViolation,
        TokenBucket,
        ValidationResult,
    )

# Lazy loading mapping: attribute_name -> (module_name, attribute_name)
_LAZY = {
    # Interfaces
    "ISecurityValidator": ("interfaces", "ISecurityValidator"),
    "IPromptInjectionDetector": ("interfaces", "IPromptInjectionDetector"),
    "IAuthenticationManager": ("interfaces", "IAuthenticationManager"),
    "IRateLimitManager": ("interfaces", "IRateLimitManager"),
    "ISecurePineconeClient": ("interfaces", "ISecurePineconeClient"),
    "ISecurityMonitor": ("interfaces", "ISecurityMonitor"),
    "IConfigurationValidator": ("interfaces", "IConfigurationValidator"),
    # Models
    "SecurityEvent": ("models", "SecurityEvent"),
    "SecurityEventType": ("models", "SecurityEventType"),
    "SecuritySeverity": ("models", "SecuritySeverity"),
    "SecurityAction": ("models", "SecurityAction"),
    "SecurityViolation": ("models", "SecurityViolation"),
    "ValidationResult": ("models", "ValidationResult"),
    "DetectionResult": ("models", "DetectionResult"),
    "AuthenticationContext": ("models", "AuthenticationContext"),
    "SecurityConfiguration": ("models", "SecurityConfiguration"),
    "AuthResult": ("models", "AuthResult"),
    "RateLimitResult": ("models", "RateLimitResult"),
    "Anomaly": ("models", "Anomaly"),
    "SecureQuery": ("models", "SecureQuery"),
    "SecureResponse": ("models", "SecureResponse"),
    "PineconeResponse": ("models", "PineconeResponse"),
    "SecurityErrorResponse": ("models", "SecurityErrorResponse"),
    "TokenBucket": ("models", "TokenBucket"),
    "ResourceMetrics": ("models", "ResourceMetrics"),
    "AuthenticationStatus": ("models", "AuthenticationStatus"),
    "RateLimitStatus": ("models", "RateLimitStatus"),
    # Configuration
    "SecurityConfigurationManager": ("config", "SecurityConfigurationManager"),
}

# Module mapping for dynamic imports - more maintainable than if-elif chains
_MODULE_MAP = {
    "interfaces": lambda: __import__("interfaces", globals(), locals(), level=1),
    "models": lambda: __import__("models", globals(), locals(), level=1),
    "config": lambda: __import__("config", globals(), locals(), level=1),
}


def __getattr__(name: str):
    """
    Lazy loading implementation for module attributes.

    This function is called when an attribute is accessed that doesn't exist
    in the module's namespace, allowing us to import modules only when needed.

    Debug logging can be enabled by setting the SECURITY_DEBUG_LAZY_LOADING
    environment variable to 'true', '1', 'yes', or 'on'.

    Args:
        name: The name of the attribute being accessed

    Returns:
        The requested attribute from the appropriate module

    Raises:
        AttributeError: If the attribute is not found in the lazy loading map
    """
    if _DEBUG_LAZY_LOADING:
        _logger.debug(f"Lazy loading requested for attribute: {name}")

    if name in _LAZY:
        module_name, attr_name = _LAZY[name]

        if _DEBUG_LAZY_LOADING:
            _logger.debug(
                f"Found {name} in lazy map: module='{module_name}', attribute='{attr_name}'"
            )

        # Get the module using dictionary lookup
        if module_name in _MODULE_MAP:
            if _DEBUG_LAZY_LOADING:
                _logger.debug(
                    f"Importing module '{module_name}' for attribute '{name}'"
                )

            try:
                module = _MODULE_MAP[module_name]()

                if _DEBUG_LAZY_LOADING:
                    _logger.debug(
                        f"Successfully imported module '{module_name}': {module}"
                    )

            except Exception as e:
                if _DEBUG_LAZY_LOADING:
                    _logger.error(
                        f"Failed to import module '{module_name}' for attribute '{name}': {e}"
                    )
                raise AttributeError(
                    f"Failed to import module '{module_name}' for attribute '{name}': {e}"
                )
        else:
            if _DEBUG_LAZY_LOADING:
                _logger.error(
                    f"Unknown module '{module_name}' for attribute '{name}'. Available modules: {list(_MODULE_MAP.keys())}"
                )
            raise AttributeError(
                f"Unknown module '{module_name}' for attribute '{name}'"
            )

        # Get the attribute from the module
        try:
            if _DEBUG_LAZY_LOADING:
                _logger.debug(
                    f"Retrieving attribute '{attr_name}' from module '{module_name}'"
                )

            attr = getattr(module, attr_name)

            if _DEBUG_LAZY_LOADING:
                _logger.debug(f"Successfully retrieved attribute '{attr_name}': {attr}")

            # Cache the attribute in the module's namespace for future access
            globals()[name] = attr

            if _DEBUG_LAZY_LOADING:
                _logger.debug(
                    f"Cached attribute '{name}' in module globals for future access"
                )

            return attr

        except AttributeError as e:
            if _DEBUG_LAZY_LOADING:
                _logger.error(
                    f"Module '{module_name}' has no attribute '{attr_name}': {e}"
                )
            raise AttributeError(
                f"Module '{module_name}' has no attribute '{attr_name}'"
            )

    if _DEBUG_LAZY_LOADING:
        _logger.error(
            f"Attribute '{name}' not found in lazy loading map. Available attributes: {sorted(_LAZY.keys())}"
        )

    raise AttributeError(f"Module '{__name__}' has no attribute '{name}'")


# Automatically generate __all__ from _LAZY dictionary keys, sorted alphabetically
# This ensures __all__ stays synchronized with actual exports and reduces maintenance overhead
__all__ = tuple(sorted(_LAZY.keys()))
