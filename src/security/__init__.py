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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Import types for static type checkers without runtime overhead
    from .interfaces import (
        ISecurityValidator,
        IPromptInjectionDetector,
        IAuthenticationManager,
        ISecurePineconeClient,
        ISecurityMonitor,
        IConfigurationValidator
    )
    
    from .models import (
        SecurityEvent,
        SecurityEventType,
        SecuritySeverity,
        SecurityAction,
        SecurityViolation,
        ValidationResult,
        DetectionResult,
        AuthenticationContext,
        SecurityConfiguration,
        AuthResult,
        RateLimitResult,
        Anomaly,
        SecureQuery,
        SecureResponse,
        SecurityErrorResponse,
        TokenBucket,
        ResourceMetrics,
        AuthenticationStatus,
        RateLimitStatus
    )
    
    from .config import SecurityConfigurationManager

# Lazy loading mapping: attribute_name -> (module_name, attribute_name)
_LAZY = {
    # Interfaces
    'ISecurityValidator': ('interfaces', 'ISecurityValidator'),
    'IPromptInjectionDetector': ('interfaces', 'IPromptInjectionDetector'),
    'IAuthenticationManager': ('interfaces', 'IAuthenticationManager'),
    'ISecurePineconeClient': ('interfaces', 'ISecurePineconeClient'),
    'ISecurityMonitor': ('interfaces', 'ISecurityMonitor'),
    'IConfigurationValidator': ('interfaces', 'IConfigurationValidator'),
    
    # Models
    'SecurityEvent': ('models', 'SecurityEvent'),
    'SecurityEventType': ('models', 'SecurityEventType'),
    'SecuritySeverity': ('models', 'SecuritySeverity'),
    'SecurityAction': ('models', 'SecurityAction'),
    'SecurityViolation': ('models', 'SecurityViolation'),
    'ValidationResult': ('models', 'ValidationResult'),
    'DetectionResult': ('models', 'DetectionResult'),
    'AuthenticationContext': ('models', 'AuthenticationContext'),
    'SecurityConfiguration': ('models', 'SecurityConfiguration'),
    'AuthResult': ('models', 'AuthResult'),
    'RateLimitResult': ('models', 'RateLimitResult'),
    'Anomaly': ('models', 'Anomaly'),
    'SecureQuery': ('models', 'SecureQuery'),
    'SecureResponse': ('models', 'SecureResponse'),
    'SecurityErrorResponse': ('models', 'SecurityErrorResponse'),
    'TokenBucket': ('models', 'TokenBucket'),
    'ResourceMetrics': ('models', 'ResourceMetrics'),
    'AuthenticationStatus': ('models', 'AuthenticationStatus'),
    'RateLimitStatus': ('models', 'RateLimitStatus'),
    
    # Configuration
    'SecurityConfigurationManager': ('config', 'SecurityConfigurationManager')
}

def __getattr__(name: str):
    """
    Lazy loading implementation for module attributes.
    
    This function is called when an attribute is accessed that doesn't exist
    in the module's namespace, allowing us to import modules only when needed.
    
    Args:
        name: The name of the attribute being accessed
        
    Returns:
        The requested attribute from the appropriate module
        
    Raises:
        AttributeError: If the attribute is not found in the lazy loading map
    """
    if name in _LAZY:
        module_name, attr_name = _LAZY[name]
        
        # Import the module dynamically
        if module_name == 'interfaces':
            from . import interfaces
            module = interfaces
        elif module_name == 'models':
            from . import models
            module = models
        elif module_name == 'config':
            from . import config
            module = config
        else:
            raise AttributeError(f"Unknown module '{module_name}' for attribute '{name}'")
        
        # Get the attribute from the module
        try:
            attr = getattr(module, attr_name)
            # Cache the attribute in the module's namespace for future access
            globals()[name] = attr
            return attr
        except AttributeError:
            raise AttributeError(f"Module '{module_name}' has no attribute '{attr_name}'")
    
    raise AttributeError(f"Module '{__name__}' has no attribute '{name}'")

# Automatically generate __all__ from _LAZY dictionary keys, sorted alphabetically
# This ensures __all__ stays synchronized with actual exports and reduces maintenance overhead
__all__ = tuple(sorted(_LAZY.keys()))