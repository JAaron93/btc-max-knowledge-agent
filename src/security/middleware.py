"""
FastAPI security middleware for input validation and request processing.

This module implements middleware that intercepts all incoming requests,
validates them using the SecurityValidator, and handles security violations
appropriately.
"""

import io
import json
import time
import logging
from typing import Dict, Any, Optional, Callable
from uuid import uuid4

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.datastructures import Headers
from starlette.requests import empty_receive, empty_send
            

from .interfaces import ISecurityValidator, ISecurityMonitor
from .models import (
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
    SecurityAction,
    ValidationResult,
    SecurityConfiguration
)


logger = logging.getLogger(__name__)


class SecurityValidationMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for security validation of incoming requests.
    
    This middleware:
    - Intercepts all incoming requests before they reach endpoints
    - Validates request content using SecurityValidator
    - Logs security events and violations
    - Handles security violations with appropriate responses
    - Provides configurable security policies per endpoint
    """
    
    def __init__(
        self,
        app: ASGIApp,
        validator: ISecurityValidator,
        monitor: ISecurityMonitor,
        config: SecurityConfiguration,
        exempt_paths: Optional[list] = None
    ):
        """
        Initialize security validation middleware.
        
        Args:
            app: FastAPI application instance
            validator: Security validator implementation
            monitor: Security monitor for logging events
            config: Security configuration
            exempt_paths: List of paths to exempt from validation
        """
        super().__init__(app)
        self.validator = validator
        self.monitor = monitor
        self.config = config
        self.exempt_paths = exempt_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico"
        ]
        
        logger.info(f"Security validation middleware initialized with {len(self.exempt_paths)} exempt paths")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process incoming request through security validation.
        
        Args:
            request: Incoming FastAPI request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response from next middleware or security error response
        """
        start_time = time.time()
        request_id = str(uuid4())
        
        # Add request ID to request state for logging
        request.state.security_request_id = request_id
        
        try:
            # Check if path is exempt from validation
            if self._is_exempt_path(request.url.path):
                logger.debug(f"Request {request_id} to {request.url.path} is exempt from security validation")
                return await call_next(request)
            
            # Extract request context
            context = await self._extract_request_context(request)
            
            # Validate request
            validation_result = await self._validate_request(request, context)
            
            # Handle validation result
            if not validation_result.is_valid:
                return await self._handle_validation_failure(
                    request, validation_result, context, request_id
                )
            
            # Log successful validation
            await self._log_validation_success(request, context, request_id)
            
            # Process request through next middleware/endpoint
            response = await call_next(request)
            
            # Log successful request completion
            processing_time = time.time() - start_time
            await self._log_request_completion(request, response, processing_time, request_id)
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions (they're handled by FastAPI)
            raise
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error in security middleware for request {request_id}: {e}")
            
            # Log security event for unexpected error
            await self._log_security_event(
                SecurityEvent(
                    event_id=request_id,
                    timestamp=time.time(),
                    event_type=SecurityEventType.SYSTEM_ERROR,
                    severity=SecuritySeverity.ERROR,
                    source_ip=self._get_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                    details={
                        "error": str(e),
                        "path": request.url.path,
                        "method": request.method,
                        "error_type": type(e).__name__
                    },
                    mitigation_action="internal_error_response"
                )
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "An internal security error occurred",
                    "request_id": request_id
                }
            )
    
    def _is_exempt_path(self, path: str) -> bool:
        """
        Check if request path is exempt from security validation.
        
        Args:
            path: Request path to check
            
        Returns:
            True if path is exempt, False otherwise
        """
        # Normalize paths
        normalized_path = path.rstrip('/')
        return any(
            normalized_path == exempt.rstrip('/') or
            normalized_path.startswith(exempt.rstrip('/') + '/')
            for exempt in self.exempt_paths
        )
    async def _extract_request_context(self, request: Request) -> Dict[str, Any]:
        """
        Extract security-relevant context from request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Dictionary containing request context
        """
        return {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "content_type": request.headers.get("content-type", ""),
            "content_length": request.headers.get("content-length", "0"),
            "timestamp": time.time()
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request headers.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client IP address string
        """
        # Check for forwarded headers (common in load balancer setups)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    async def _validate_request(self, request: Request, context: Dict[str, Any]) -> ValidationResult:
        """
        Validate request using SecurityValidator.
        
        Args:
            request: FastAPI request object
            context: Request context dictionary
            
        Returns:
            ValidationResult from security validation
        """
        try:
            # Read request body for validation
            body = await request.body()
            body_str = body.decode('utf-8') if body else ""

            # Reconstruct the body stream for the endpoint         
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            
            request._receive = receive
            
            # Validate request body content
            if body_str:
                validation_result = await self.validator.validate_input(body_str, context)
                if not validation_result.is_valid:
                    return validation_result
            
            # Validate query parameters
            query_string = str(request.url.query) if request.url.query else ""
            if query_string:
                query_validation = await self.validator.validate_input(query_string, context)
                if not query_validation.is_valid:
                    return query_validation
            
            # Validate specific query parameters structure
            if request.query_params:
                param_validation = await self.validator.validate_query_parameters(
                    dict(request.query_params)
                )
                if not param_validation.is_valid:
                    return param_validation
            
            # If all validations pass, return success
            return ValidationResult(
                is_valid=True,
        except Exception as e:
            logger.error(f"Error during request validation: {e}")
            # Return validation failure for any errors
            return ValidationResult(
                is_valid=False,
                confidence_score=1.0,
                violations=[{
                    "violation_type": "validation_error",
                    "severity": SecuritySeverity.ERROR,
                    "description": f"Validation error: {str(e)}",
                    "confidence_score": 1.0,
                    "detected_pattern": None,
                    "location": "request_validation"
                }],
                recommended_action=SecurityAction.BLOCK
            )
                confidence_score=1.0,
                violations=[],
                recommended_action=SecurityAction.BLOCK
            )
    
    async def _handle_validation_failure(
        self,
        request: Request,
        validation_result: ValidationResult,
        context: Dict[str, Any],
        request_id: str
    ) -> JSONResponse:
        """
        Handle validation failure with appropriate response and logging.
        
        Args:
            request: FastAPI request object
            validation_result: Failed validation result
            context: Request context
            request_id: Unique request identifier
            
        Returns:
            JSONResponse with error details
        """
        # Determine response based on recommended action
        if validation_result.recommended_action == SecurityAction.BLOCK:
            status_code = 400
            error_code = "input_validation_failed"
            message = "Request contains invalid or potentially malicious content"
        elif validation_result.recommended_action == SecurityAction.SANITIZE:
            status_code = 422
            error_code = "input_sanitization_required"
            message = "Request content requires sanitization"
        else:
            status_code = 400
            error_code = "security_validation_failed"
            message = "Request failed security validation"
        
        # Log security event
        await self._log_security_event(
            SecurityEvent(
                event_id=request_id,
                timestamp=time.time(),
                event_type=SecurityEventType.INPUT_VALIDATION_FAILURE,
                severity=self._get_severity_from_violations(validation_result.violations),
                source_ip=context.get("client_ip"),
                user_agent=context.get("user_agent"),
                details={
                    "path": context.get("path"),
                    "method": context.get("method"),
                    "violations": [
                        {
                            "type": v.violation_type,
                            "severity": v.severity.value,
                            "description": v.description,
                            "confidence": v.confidence_score,
                            "pattern": v.detected_pattern,
                            "location": v.location
                        }
                        for v in validation_result.violations
                    ],
                    "confidence_score": validation_result.confidence_score,
                    "recommended_action": validation_result.recommended_action.value
                },
                mitigation_action=f"blocked_request_{validation_result.recommended_action.value}"
            )
        )
        
        # Return error response
        return JSONResponse(
            status_code=status_code,
            content={
                "error": error_code,
                "message": message,
                "request_id": request_id,
                "violations": len(validation_result.violations),
                "confidence_score": validation_result.confidence_score
            }
        )
    
    def _get_severity_from_violations(self, violations: list) -> SecuritySeverity:
        """
        Determine overall severity from list of violations.
        
        Args:
            violations: List of SecurityViolation objects
            
        Returns:
            Highest severity level found
        """
        if not violations:
            return SecuritySeverity.INFO
        
        severity_order = {
            SecuritySeverity.INFO: 0,
            SecuritySeverity.WARNING: 1,
            SecuritySeverity.ERROR: 2,
            SecuritySeverity.CRITICAL: 3
        }
        
        max_severity = max(violations, key=lambda v: severity_order[v.severity])
        return max_severity.severity
    
    async def _log_validation_success(
        self,
        request: Request,
        context: Dict[str, Any],
        request_id: str
    ) -> None:
        """
        Log successful validation event.
        
        Args:
            request: FastAPI request object
            context: Request context
            request_id: Unique request identifier
        """
        await self._log_security_event(
            SecurityEvent(
                event_id=request_id,
                timestamp=time.time(),
                event_type=SecurityEventType.INPUT_VALIDATION_SUCCESS,
                severity=SecuritySeverity.INFO,
                source_ip=context.get("client_ip"),
                user_agent=context.get("user_agent"),
                details={
                    "path": context.get("path"),
                    "method": context.get("method"),
                    "content_length": context.get("content_length"),
                    "validation_passed": True
                },
                mitigation_action="request_allowed"
            )
        )
    
    async def _log_request_completion(
        self,
        request: Request,
        response: Response,
        processing_time: float,
        request_id: str
    ) -> None:
        """
        Log successful request completion.
        
        Args:
            request: FastAPI request object
            response: Response object
            processing_time: Total processing time in seconds
            request_id: Unique request identifier
        """
        await self._log_security_event(
            SecurityEvent(
                event_id=request_id,
                timestamp=time.time(),
                event_type=SecurityEventType.REQUEST_SUCCESS,
                severity=SecuritySeverity.INFO,
                source_ip=self._get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "processing_time_ms": processing_time * 1000,
                    "response_size": getattr(response, "content_length", None)
                },
                mitigation_action="request_success"
            )
        )
    
    async def _log_security_event(self, event: SecurityEvent) -> None:
        """
        Log security event using the security monitor.
        
        Args:
            event: SecurityEvent to log
        """
        try:
            await self.monitor.log_security_event(event)
        except Exception as e:
            # Don't fail the request if logging fails
            logger.error(f"Failed to log security event {event.event_id}: {e}")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    This middleware adds standard security headers to protect against
    common web vulnerabilities.
    """
    
    def __init__(self, app: ASGIApp, config: SecurityConfiguration):
        """
        Initialize security headers middleware.
        
        Args:
            app: FastAPI application instance
            config: Security configuration
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "connect-src 'self'"
            ),
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            )
        }

        # Only add HSTS in production with HTTPS
        if self.config.environment == "production":
            self.security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            )
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add security headers to response.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response with security headers added
        """
        response = await call_next(request)
        
        # Add security headers
        for header_name, header_value in self.security_headers.items():
            response.headers[header_name] = header_value
        
        # Add custom security headers based on configuration
        if self.config.environment == "production":
            response.headers["Server"] = "BTC-Assistant"  # Hide server details
        
        return response


def create_security_middleware(
    validator: ISecurityValidator,
    monitor: ISecurityMonitor,
    config: SecurityConfiguration,
    exempt_paths: Optional[list] = None
) -> tuple:
    """
    Factory function to create security middleware classes.
    
    This function returns middleware factory functions (classes) that can be
    passed directly to FastAPI add_middleware() method. FastAPI will
    instantiate the middleware classes automatically.
    
    Args:
        validator: Security validator implementation
        monitor: Security monitor implementation
        config: Security configuration
        exempt_paths: Optional list of paths to exempt from validation
        
    Returns:
        Tuple of (validation_middleware_class, headers_middleware_class)
        These are callable classes, not instances.
    """
    def validation_middleware(app: ASGIApp) -> SecurityValidationMiddleware:
        return SecurityValidationMiddleware(app, validator, monitor, config, exempt_paths)
    
    def headers_middleware(app: ASGIApp) -> SecurityHeadersMiddleware:
        return SecurityHeadersMiddleware(app, config)
    
    return validation_middleware, headers_middleware
