"""
Security configuration management and validation.

This module handles loading, validating, and managing security configuration
from environment variables and other sources.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from .models import SecurityConfiguration, ValidationResult, SecurityViolation, SecuritySeverity, SecurityAction
from .interfaces import IConfigurationValidator


logger = logging.getLogger(__name__)


class SecurityConfigurationManager(IConfigurationValidator):
    """Manages security configuration loading and validation."""
    
    def __init__(self):
        self._config: Optional[SecurityConfiguration] = None
        self._environment_cache: Dict[str, str] = {}
    
    def _classify_config_error(self, error_message: str) -> tuple[str, SecuritySeverity, float, SecurityAction]:
        """
        Classify configuration error and return appropriate violation properties.
        
        Args:
            error_message: The error message from config validation
            
        Returns:
            Tuple of (violation_type, severity, confidence_score, recommended_action)
        """
        error_lower = error_message.lower()
        
        # Critical security-related errors
        if any(keyword in error_lower for keyword in [
            'injection_detection_threshold', 'injection_accuracy_target', 
            'sanitization_confidence_threshold', 'api_key'
        ]):
            return ("security_configuration_error", SecuritySeverity.CRITICAL, 1.0, SecurityAction.BLOCK)
        
        # Authentication and rate limiting errors (high severity)
        elif any(keyword in error_lower for keyword in [
            'rate_limit', 'auth_cache', 'auth_remote', 'processing_timeout'
        ]):
            return ("authentication_configuration_error", SecuritySeverity.ERROR, 0.95, SecurityAction.RATE_LIMIT)
        
        # Resource threshold errors (medium-high severity)
        elif any(keyword in error_lower for keyword in [
            'cpu_threshold', 'memory_threshold', 'disk_threshold'
        ]):
            return ("resource_threshold_error", SecuritySeverity.ERROR, 0.9, SecurityAction.LOG_AND_MONITOR)
        
        # Environment configuration errors (medium severity)
        elif 'environment' in error_lower:
            return ("environment_configuration_error", SecuritySeverity.WARNING, 0.8, SecurityAction.SANITIZE)
        
        # Input validation limits (medium severity)
        elif any(keyword in error_lower for keyword in [
            'max_query_length', 'max_metadata_fields', 'max_context_tokens', 'max_tokens'
        ]):
            return ("input_validation_error", SecuritySeverity.WARNING, 0.85, SecurityAction.SANITIZE)
        
        # General positive value requirements (lower severity)
        elif 'must be positive' in error_lower:
            return ("numeric_validation_error", SecuritySeverity.WARNING, 0.9, SecurityAction.SANITIZE)
        
        # Range validation errors (medium severity)
        elif 'must be between' in error_lower:
            return ("range_validation_error", SecuritySeverity.ERROR, 0.95, SecurityAction.SANITIZE)
        
        # Default case for unclassified errors
        else:
            return ("configuration_error", SecuritySeverity.ERROR, 0.8, SecurityAction.BLOCK)

    async def validate_config(self, config: SecurityConfiguration) -> ValidationResult:
        """
        Validate security configuration for correctness and safety.
        
        Args:
            config: SecurityConfiguration to validate
            
        Returns:
            ValidationResult indicating configuration validity
        """
        errors = config.validate()
        violations = []
        
        for error in errors:
            # Dynamically classify the error and get appropriate properties
            violation_type, severity, confidence_score, recommended_action = self._classify_config_error(error)
            
            violation = SecurityViolation(
                violation_type=violation_type,
                severity=severity,
                description=error,
                confidence_score=confidence_score
            )
            violations.append(violation)
        
        is_valid = len(violations) == 0
        
        # Determine overall recommended action based on most severe violation
        if violations:
            # Get the most severe violation to determine overall action
            severity_order = {
                SecuritySeverity.INFO: 0,
                SecuritySeverity.WARNING: 1,
                SecuritySeverity.ERROR: 2,
                SecuritySeverity.CRITICAL: 3
            }
            most_severe = max(violations, key=lambda v: severity_order[v.severity])
            _, _, _, recommended_action = self._classify_config_error(most_severe.description)
        else:
            recommended_action = SecurityAction.ALLOW
        
        # Calculate overall confidence score as average of violation confidence scores
        overall_confidence = 1.0 if is_valid else (
            sum(v.confidence_score for v in violations) / len(violations)
        )
        
        return ValidationResult(
            is_valid=is_valid,
            confidence_score=overall_confidence,
            violations=violations,
            recommended_action=recommended_action
        )
    
    def _safe_int_conversion(self, value: str, default: int, var_name: str) -> int:
        """
        Safely convert string to integer with error handling.
        
        Args:
            value: String value to convert
            default: Default value if conversion fails
            var_name: Variable name for error logging
            
        Returns:
            Converted integer value or default
        """
        try:
            return int(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid integer value for {var_name}: '{value}'. Using default: {default}. Error: {e}")
            return default
    
    def _safe_float_conversion(self, value: str, default: float, var_name: str) -> float:
        """
        Safely convert string to float with error handling.
        
        Args:
            value: String value to convert
            default: Default value if conversion fails
            var_name: Variable name for error logging
            
        Returns:
            Converted float value or default
        """
        try:
            return float(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid float value for {var_name}: '{value}'. Using default: {default}. Error: {e}")
            return default
    
    def _parse_boolean(self, value: str, default: bool = False) -> bool:
        """
        Parse boolean value from string with error handling.
        
        Args:
            value: String value to parse
            default: Default value if parsing fails
            
        Returns:
            Parsed boolean value or default
        """
        if not isinstance(value, str):
            return default
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def _load_alert_thresholds(self, env_vars: dict) -> dict:
        """
        Load alert thresholds with proper type handling.
        
        Args:
            env_vars: Environment variables dictionary
            
        Returns:
            Dictionary of alert thresholds with correct types
        """
        return {
            "error_rate_percent": self._safe_float_conversion(
                env_vars.get('ALERT_ERROR_RATE_PERCENT', '10.0'), 10.0, 'ALERT_ERROR_RATE_PERCENT'
            ),
            "response_time_seconds": self._safe_float_conversion(
                env_vars.get('ALERT_RESPONSE_TIME_SECONDS', '5.0'), 5.0, 'ALERT_RESPONSE_TIME_SECONDS'
            ),
            "memory_usage_percent": self._safe_float_conversion(
                env_vars.get('ALERT_MEMORY_USAGE_PERCENT', '80.0'), 80.0, 'ALERT_MEMORY_USAGE_PERCENT'
            ),
            "failed_auth_attempts": self._safe_int_conversion(
                env_vars.get('ALERT_FAILED_AUTH_ATTEMPTS', '5'), 5, 'ALERT_FAILED_AUTH_ATTEMPTS'
            ),
            "suspicious_ip_count": self._safe_int_conversion(
                env_vars.get('ALERT_SUSPICIOUS_IP_COUNT', '10'), 10, 'ALERT_SUSPICIOUS_IP_COUNT'
            ),
            "query_volume_increase_percent": self._safe_float_conversion(
                env_vars.get('ALERT_QUERY_VOLUME_INCREASE_PERCENT', '300.0'), 300.0, 'ALERT_QUERY_VOLUME_INCREASE_PERCENT'
            ),
            "entropy_threshold": self._safe_float_conversion(
                env_vars.get('ALERT_ENTROPY_THRESHOLD', '4.5'), 4.5, 'ALERT_ENTROPY_THRESHOLD'
            )
        }

    async def load_secure_config(self) -> SecurityConfiguration:
        """
        Load and validate security configuration from environment.
        
        Returns:
            Validated SecurityConfiguration instance
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Load environment variables
        env_vars = self._load_environment_variables()
        
        # Create configuration with environment overrides using safe conversions
        config = SecurityConfiguration(
            # Input validation limits
            max_query_length=self._safe_int_conversion(
                env_vars.get('MAX_QUERY_LENGTH', '4096'), 4096, 'MAX_QUERY_LENGTH'
            ),
            max_metadata_fields=self._safe_int_conversion(
                env_vars.get('MAX_METADATA_FIELDS', '50'), 50, 'MAX_METADATA_FIELDS'
            ),
            max_context_tokens=self._safe_int_conversion(
                env_vars.get('MAX_CONTEXT_TOKENS', '8192'), 8192, 'MAX_CONTEXT_TOKENS'
            ),
            max_tokens=self._safe_int_conversion(
                env_vars.get('MAX_TOKENS', '1000'), 1000, 'MAX_TOKENS'
            ),
            
            # Authentication and rate limiting
            rate_limit_per_minute=self._safe_int_conversion(
                env_vars.get('RATE_LIMIT_PER_MINUTE', '100'), 100, 'RATE_LIMIT_PER_MINUTE'
            ),
            rate_limit_burst=self._safe_int_conversion(
                env_vars.get('RATE_LIMIT_BURST', '10'), 10, 'RATE_LIMIT_BURST'
            ),
            rate_limit_refill_rate=self._safe_float_conversion(
                env_vars.get('RATE_LIMIT_REFILL_RATE', '1.67'), 1.67, 'RATE_LIMIT_REFILL_RATE'
            ),
            auth_cache_validation_timeout_ms=self._safe_int_conversion(
                env_vars.get('AUTH_CACHE_VALIDATION_TIMEOUT_MS', '100'), 100, 'AUTH_CACHE_VALIDATION_TIMEOUT_MS'
            ),
            auth_remote_fetch_timeout_ms=self._safe_int_conversion(
                env_vars.get('AUTH_REMOTE_FETCH_TIMEOUT_MS', '300'), 300, 'AUTH_REMOTE_FETCH_TIMEOUT_MS'
            ),
            api_key_min_length=self._safe_int_conversion(
                env_vars.get('API_KEY_MIN_LENGTH', '32'), 32, 'API_KEY_MIN_LENGTH'
            ),
            api_key_max_length=self._safe_int_conversion(
                env_vars.get('API_KEY_MAX_LENGTH', '64'), 64, 'API_KEY_MAX_LENGTH'
            ),
            
            # Prompt injection detection
            injection_detection_threshold=self._safe_float_conversion(
                env_vars.get('INJECTION_DETECTION_THRESHOLD', '0.8'), 0.8, 'INJECTION_DETECTION_THRESHOLD'
            ),
            injection_accuracy_target=self._safe_float_conversion(
                env_vars.get('INJECTION_ACCURACY_TARGET', '0.95'), 0.95, 'INJECTION_ACCURACY_TARGET'
            ),
            sanitization_confidence_threshold=self._safe_float_conversion(
                env_vars.get('SANITIZATION_CONFIDENCE_THRESHOLD', '0.7'), 0.7, 'SANITIZATION_CONFIDENCE_THRESHOLD'
            ),
            
            # Resource limits
            max_concurrent_per_ip=self._safe_int_conversion(
                env_vars.get('MAX_CONCURRENT_PER_IP', '50'), 50, 'MAX_CONCURRENT_PER_IP'
            ),
            max_concurrent_system=self._safe_int_conversion(
                env_vars.get('MAX_CONCURRENT_SYSTEM', '200'), 200, 'MAX_CONCURRENT_SYSTEM'
            ),
            processing_timeout_seconds=self._safe_int_conversion(
                env_vars.get('PROCESSING_TIMEOUT_SECONDS', '60'), 60, 'PROCESSING_TIMEOUT_SECONDS'
            ),
            estimated_processing_limit_seconds=self._safe_int_conversion(
                env_vars.get('ESTIMATED_PROCESSING_LIMIT_SECONDS', '30'), 30, 'ESTIMATED_PROCESSING_LIMIT_SECONDS'
            ),
            cpu_threshold_percent=self._safe_float_conversion(
                env_vars.get('CPU_THRESHOLD_PERCENT', '85.0'), 85.0, 'CPU_THRESHOLD_PERCENT'
            ),
            memory_threshold_percent=self._safe_float_conversion(
                env_vars.get('MEMORY_THRESHOLD_PERCENT', '90.0'), 90.0, 'MEMORY_THRESHOLD_PERCENT'
            ),
            disk_threshold_percent=self._safe_float_conversion(
                env_vars.get('DISK_THRESHOLD_PERCENT', '95.0'), 95.0, 'DISK_THRESHOLD_PERCENT'
            ),
            
            # Monitoring and alerting
            monitoring_enabled=self._parse_boolean(env_vars.get('MONITORING_ENABLED', 'true'), True),
            log_retention_days=self._safe_int_conversion(
                env_vars.get('LOG_RETENTION_DAYS', '90'), 90, 'LOG_RETENTION_DAYS'
            ),
            alert_response_time_seconds=self._safe_int_conversion(
                env_vars.get('ALERT_RESPONSE_TIME_SECONDS', '10'), 10, 'ALERT_RESPONSE_TIME_SECONDS'
            ),
            anomaly_detection_time_seconds=self._safe_int_conversion(
                env_vars.get('ANOMALY_DETECTION_TIME_SECONDS', '300'), 300, 'ANOMALY_DETECTION_TIME_SECONDS'
            ),
            
            # Database configuration
            database_url=env_vars.get('DATABASE_URL'),
            database_pool_size=self._safe_int_conversion(
                env_vars.get('DATABASE_POOL_SIZE', '10'), 10, 'DATABASE_POOL_SIZE'
            ),
            database_max_overflow=self._safe_int_conversion(
                env_vars.get('DATABASE_MAX_OVERFLOW', '20'), 20, 'DATABASE_MAX_OVERFLOW'
            ),
            
            # Environment-specific settings
            environment=env_vars.get('ENVIRONMENT', 'development'),
            debug_mode=self._parse_boolean(env_vars.get('DEBUG_MODE', 'false'), False)
        )
        
        # Load alert thresholds with proper type handling
        config.alert_thresholds.update(self._load_alert_thresholds(env_vars))
        
        # Validate configuration
        validation_result = await self.validate_config(config)
        if not validation_result.is_valid:
            error_messages = [v.description for v in validation_result.violations]
            raise ValueError(f"Invalid security configuration: {'; '.join(error_messages)}")
        
        self._config = config
        logger.info("Security configuration loaded and validated successfully")
        return config
    
    async def reload_config(self) -> SecurityConfiguration:
        """
        Reload configuration from environment variables.
        
        Returns:
            Updated SecurityConfiguration instance
        """
        # Clear cache to force reload
        self._environment_cache.clear()
        return await self.load_secure_config()
    
    async def validate_environment_variables(self) -> ValidationResult:
        """
        Validate that all required environment variables are present and valid.
        
        Returns:
            ValidationResult indicating environment validity
        """
        violations = []
        
        # Check for required environment variables
        required_vars = [
            'DATABASE_URL',      # Required for security logging
            'PINECONE_API_KEY',  # Required for core Bitcoin knowledge functionality
            'ENVIRONMENT',       # Required for proper security configuration
        ]
        
        env_vars = self._load_environment_variables()
        
        # Check required variables
        for var_name in required_vars:
            if var_name not in env_vars or not env_vars[var_name]:
                violation = SecurityViolation(
                    violation_type="missing_environment_variable",
                    severity=SecuritySeverity.ERROR,
                    description=f"Required environment variable {var_name} is missing or empty",
                    confidence_score=1.0
                )
                violations.append(violation)
        
        # Validate numeric environment variables
        numeric_vars = {
            'MAX_QUERY_LENGTH': (1, 1024*1024),  # 1 byte to 1MB
            'MAX_METADATA_FIELDS': (1, 1000),
            'RATE_LIMIT_PER_MINUTE': (1, 10000),
            'AUTH_CACHE_VALIDATION_TIMEOUT_MS': (1, 5000),
            'CPU_THRESHOLD_PERCENT': (0.0, 100.0),
            'MEMORY_THRESHOLD_PERCENT': (0.0, 100.0)
        }
        
        for var_name, (min_val, max_val) in numeric_vars.items():
            if var_name in env_vars:
                try:
                    value = float(env_vars[var_name])
                    if not min_val <= value <= max_val:
                        violation = SecurityViolation(
                            violation_type="invalid_environment_variable",
                            severity=SecuritySeverity.WARNING,
                            description=f"Environment variable {var_name}={value} is outside valid range [{min_val}, {max_val}]",
                            confidence_score=1.0
                        )
                        violations.append(violation)
                except ValueError:
                    violation = SecurityViolation(
                        violation_type="invalid_environment_variable",
                        severity=SecuritySeverity.ERROR,
                        description=f"Environment variable {var_name}={env_vars[var_name]} is not a valid number",
                        confidence_score=1.0
                    )
                    violations.append(violation)
        
        is_valid = len([v for v in violations if v.severity in [SecuritySeverity.ERROR, SecuritySeverity.CRITICAL]]) == 0
        recommended_action = SecurityAction.ALLOW if is_valid else SecurityAction.BLOCK
        
        return ValidationResult(
            is_valid=is_valid,
            confidence_score=1.0 if is_valid else 0.0,
            violations=violations,
            recommended_action=recommended_action
        )
    
    def _load_environment_variables(self) -> Dict[str, str]:
        """
        Load environment variables with caching using specific prefixes.
        
        Returns:
            Dictionary of environment variables
        """
        if not self._environment_cache:
            # Define specific prefixes to avoid capturing unrelated variables
            specific_prefixes = [
                # Input validation limits
                'MAX_QUERY_LENGTH', 'MAX_METADATA_FIELDS', 'MAX_CONTEXT_TOKENS', 'MAX_TOKENS',
                'MAX_CONCURRENT_PER_IP', 'MAX_CONCURRENT_SYSTEM',
                
                # Rate limiting
                'RATE_LIMIT_PER_MINUTE', 'RATE_LIMIT_BURST', 'RATE_LIMIT_REFILL_RATE',
                
                # Authentication
                'AUTH_CACHE_VALIDATION_TIMEOUT_MS', 'AUTH_REMOTE_FETCH_TIMEOUT_MS',
                'API_KEY_MIN_LENGTH', 'API_KEY_MAX_LENGTH',
                
                # Injection detection
                'INJECTION_DETECTION_THRESHOLD', 'INJECTION_ACCURACY_TARGET',
                'SANITIZATION_CONFIDENCE_THRESHOLD',
                
                # Resource thresholds
                'CPU_THRESHOLD_PERCENT', 'MEMORY_THRESHOLD_PERCENT', 'DISK_THRESHOLD_PERCENT',
                'PROCESSING_TIMEOUT_SECONDS', 'ESTIMATED_PROCESSING_LIMIT_SECONDS',
                
                # Monitoring and alerting
                'MONITORING_ENABLED', 'LOG_RETENTION_DAYS', 
                'ALERT_RESPONSE_TIME_SECONDS', 'ANOMALY_DETECTION_TIME_SECONDS',
                
                # Alert thresholds
                'ALERT_ERROR_RATE_PERCENT', 'ALERT_RESPONSE_TIME_SECONDS', 'ALERT_MEMORY_USAGE_PERCENT',
                'ALERT_FAILED_AUTH_ATTEMPTS', 'ALERT_SUSPICIOUS_IP_COUNT', 
                'ALERT_QUERY_VOLUME_INCREASE_PERCENT', 'ALERT_ENTROPY_THRESHOLD',
                
                # Database configuration
                'DATABASE_URL', 'DATABASE_POOL_SIZE', 'DATABASE_MAX_OVERFLOW',
                
                # External services
                'PINECONE_API_KEY',
                
                # Environment settings
                'ENVIRONMENT', 'DEBUG_MODE'
            ]
            
            # Load only the specific variables we need
            for var_name in specific_prefixes:
                if var_name in os.environ:
                    self._environment_cache[var_name] = os.environ[var_name]
        
        return self._environment_cache.copy()
    
    def get_current_config(self) -> Optional[SecurityConfiguration]:
        """
        Get the currently loaded configuration.
        
        Returns:
            Current SecurityConfiguration or None if not loaded
        """
        return self._config
    
    def export_config_dict(self) -> Dict[str, Any]:
        """
        Export current configuration as dictionary for debugging.
        
        Returns:
            Dictionary representation of current configuration
        """
        if self._config is None:
            return {}
        
        config_dict = asdict(self._config)
        
        # Remove sensitive information
        sensitive_keys = ['database_url']
        for key in sensitive_keys:
            if key in config_dict and config_dict[key]:
                config_dict[key] = "***REDACTED***"
        
        return config_dict