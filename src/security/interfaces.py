"""
Abstract base classes and interfaces for security components.

This module defines the contracts that all security components must implement,
ensuring consistent behavior and enabling dependency injection for testing.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from .models import (
    ValidationResult,
    DetectionResult,
    AuthenticationContext,
    SecurityEvent,
    SecurityConfiguration,
    Anomaly,
    SecureQuery,
    SecureResponse,
    PineconeResponse,
    AuthResult,
    RateLimitResult
)


class ISecurityValidator(ABC):
    """Interface for input validation and sanitization services."""
    
    @abstractmethod
    async def validate_input(self, input_data: str, context: Dict[str, Any]) -> ValidationResult:
        """
        Validate input data against security policies.
        
        Args:
            input_data: The input string to validate
            context: Additional context for validation (IP, user agent, etc.)
            
        Returns:
            ValidationResult containing validation status and details
        """
        pass
    
    @abstractmethod
    async def sanitize_input(self, input_data: str) -> str:
        """
        Sanitize input data to remove or neutralize threats.
        
        Args:
            input_data: The input string to sanitize
            
        Returns:
            Sanitized input string
        """
        pass
    
    @abstractmethod
    async def validate_query_parameters(self, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate query parameters against defined limits.
        
        Args:
            params: Dictionary of query parameters to validate
            
        Returns:
            ValidationResult indicating parameter validity
        """
        pass


class IPromptInjectionDetector(ABC):
    """Interface for prompt injection detection and prevention."""
    
    @abstractmethod
    async def detect_injection(self, query: str, context: Dict[str, Any]) -> DetectionResult:
        """
        Detect prompt injection attempts in user queries.
        
        Args:
            query: The user query to analyze
            context: Additional context for detection
            
        Returns:
            DetectionResult with injection analysis results
        """
        pass
    
    @abstractmethod
    async def neutralize_injection(self, query: str) -> str:
        """
        Neutralize detected injection attempts while preserving legitimate content.
        
        Args:
            query: The query containing potential injection
            
        Returns:
            Neutralized query string
        """
        pass
    
    @abstractmethod
    async def validate_context_window(self, context: str) -> ValidationResult:
        """
        Validate that context doesn't exceed maximum token limits.
        
        Args:
            context: The context string to validate
            
        Returns:
            ValidationResult indicating whether context is within limits
        """
        pass


class IAuthenticationManager(ABC):
    """Interface for authentication and authorization services."""
    
    @abstractmethod
    async def validate_credentials(self, credentials: Dict[str, str]) -> AuthResult:
        """
        Validate API credentials (API keys, JWT tokens).
        
        Args:
            credentials: Dictionary containing credential information
            
        Returns:
            AuthResult with validation status and context
        """
        pass
    
    @abstractmethod
    async def get_authentication_context(self, client_id: str) -> Optional[AuthenticationContext]:
        """
        Retrieve authentication context for a client.
        
        Args:
            client_id: Unique identifier for the client
            
        Returns:
            AuthenticationContext if found, None otherwise
        """
        pass


class IRateLimitManager(ABC):
    """Interface for rate limiting services."""
    
    @abstractmethod
    async def check_rate_limit(self, client_id: str, endpoint: str = "default") -> RateLimitResult:
        """
        Check if client has exceeded rate limits.
        
        Args:
            client_id: Unique identifier for the client
            endpoint: Specific endpoint being accessed
            
        Returns:
            RateLimitResult with limit status and remaining quota
        """
        pass
    
    @abstractmethod
    async def update_rate_limit(self, client_id: str, endpoint: str = "default") -> None:
        """
        Update rate limit counters after successful request.
        
        Args:
            client_id: Unique identifier for the client
            endpoint: Specific endpoint being accessed
        """
        pass


class ISecurePineconeClient(ABC):
    """Interface for secure Pinecone API interactions."""
    
    @abstractmethod
    async def secure_query(self, query: SecureQuery) -> SecureResponse:
        """
        Execute a secure query against Pinecone with validation.
        
        Args:
            query: SecureQuery object with validated parameters
            
        Returns:
            SecureResponse with filtered and validated results
        """
        pass
    
    @abstractmethod
    async def validate_response(self, response: PineconeResponse) -> ValidationResult:
        """
        Validate Pinecone response for security issues.
        
        Args:
            response: Raw response from Pinecone API with structured type
            
        Returns:
            ValidationResult indicating response safety
        """
        pass
    
    @abstractmethod
    async def check_resource_limits(self) -> Dict[str, float]:
        """
        Check current resource utilization against limits.
        
        Returns:
            Dictionary of resource metrics (CPU, memory, connections)
        """
        pass


class ISecurityMonitor(ABC):
    """Interface for security monitoring and alerting."""
    
    @abstractmethod
    async def log_security_event(self, event: SecurityEvent) -> None:
        """
        Log a security event to the monitoring system.
        
        Args:
            event: SecurityEvent to be logged
        """
        pass
    
    @abstractmethod
    async def detect_anomalies(self, metrics: Dict[str, Any]) -> List[Anomaly]:
        """
        Detect anomalous patterns in system metrics.
        
        Args:
            metrics: Dictionary of system metrics to analyze
            
        Returns:
            List of detected anomalies
        """
        pass
    
    @abstractmethod
    async def generate_alert(self, anomaly: Anomaly) -> None:
        """
        Generate and send security alerts.
        
        Args:
            anomaly: Anomaly that triggered the alert
        """
        pass
    
    @abstractmethod
    async def get_security_metrics(self, time_range: int = 3600) -> Dict[str, Any]:
        """
        Retrieve security metrics for the specified time range.
        
        Args:
            time_range: Time range in seconds (default: 1 hour)
            
        Returns:
            Dictionary of aggregated security metrics
        """
        pass


class IConfigurationValidator(ABC):
    """Interface for security configuration management."""
    
    @abstractmethod
    def validate_config(self, config: SecurityConfiguration) -> ValidationResult:
        """
        Validate security configuration for correctness and safety.
        
        Args:
            config: SecurityConfiguration to validate
            
        Returns:
            ValidationResult indicating configuration validity
        """
        pass
    
    @abstractmethod
    def load_secure_config(self) -> SecurityConfiguration:
        """
        Load and validate security configuration from environment.
        
        Returns:
            Validated SecurityConfiguration instance
        """
        pass
    
    @abstractmethod
    def reload_config(self) -> SecurityConfiguration:
        """
        Reload configuration from environment variables.
        
        Returns:
            Updated SecurityConfiguration instance
        """
        pass
    
    @abstractmethod
    def validate_environment_variables(self) -> ValidationResult:
        """
        Validate that all required environment variables are present and valid.
        
        Returns:
            ValidationResult indicating environment validity
        """
        pass