"""
TTS Error Handling Module

This module provides comprehensive error handling for Text-to-Speech operations,
including custom exceptions, retry mechanisms with exponential backoff, rate limiting
handling, and graceful degradation strategies.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Optional, TypeVar, Dict, Union
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import deque
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)

# Type variable for generic return type
T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests are short-circuited
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: float = 0.5  # 50% failure rate to open circuit
    window_size: int = 10           # Number of requests to track
    cooldown_period: int = 60       # Seconds to wait before half-open
    success_threshold: int = 3      # Consecutive successes to close circuit


@dataclass
class TTSErrorState:
    """Represents the current error state of the TTS service."""
    has_error: bool = False
    error_type: str = ""
    error_message: str = ""
    last_error_time: Optional[datetime] = None
    consecutive_failures: int = 0
    recovery_check_count: int = 0
    is_muted: bool = False
    # Circuit breaker state
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_opened_at: Optional[datetime] = None


class TTSError(Exception):
    """Base exception for all TTS-related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        original_error: Optional[Exception] = None,
        recoverable: bool = True
    ):
        super().__init__(message)
        self.error_code = error_code
        self.original_error = original_error
        self.recoverable = recoverable
        self.timestamp = datetime.now(timezone.utc)

    def __str__(self):
        base_msg = super().__str__()
        if self.error_code:
            base_msg += f" (Code: {self.error_code})"
        if self.original_error:
            base_msg += f" - Original error: {str(self.original_error)}"
        return base_msg


class TTSAPIKeyError(TTSError):
    """Raised when API key is missing or invalid."""
    
    def __init__(self, message: str = "ElevenLabs API key is missing or invalid"):
        super().__init__(message, error_code="API_KEY_ERROR", recoverable=False)


class TTSRateLimitError(TTSError):
    """Raised when API rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, error_code="RATE_LIMIT", recoverable=True)
        self.retry_after = retry_after


class TTSServerError(TTSError):
    """Raised when ElevenLabs server returns 5xx errors."""
    
    def __init__(self, message: str, status_code: int):
        super().__init__(message, error_code=f"SERVER_ERROR_{status_code}", recoverable=True)
        self.status_code = status_code


class TTSNetworkError(TTSError):
    """Raised when network connectivity issues occur."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, error_code="NETWORK_ERROR", original_error=original_error, recoverable=True)


class TTSRetryExhaustedError(TTSError):
    """Raised when all retry attempts are exhausted."""
    
    def __init__(self, message: str, attempts: int, last_error: Optional[Exception] = None):
        super().__init__(message, error_code="RETRY_EXHAUSTED", original_error=last_error, recoverable=False)
        self.attempts = attempts


class TTSCircuitOpenError(TTSError):
    """Raised when circuit breaker is open and requests are short-circuited."""
    
    def __init__(self, message: str = "Circuit breaker is open - requests are being short-circuited"):
        super().__init__(message, error_code="CIRCUIT_OPEN", recoverable=False)


class CircuitBreaker:
    """Circuit breaker implementation for TTS service resilience."""
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
        
        # Sliding window to track request outcomes
        self.request_window: deque = deque(maxlen=self.config.window_size)
        
        logger.info(f"Circuit breaker initialized - Threshold: {self.config.failure_threshold}, "
                   f"Window: {self.config.window_size}, Cooldown: {self.config.cooldown_period}s")
    
    def _calculate_failure_rate(self) -> float:
        """Calculate current failure rate from sliding window."""
        if not self.request_window:
            return 0.0
        
        failures = sum(1 for success in self.request_window if not success)
        return failures / len(self.request_window)
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should transition from OPEN to HALF_OPEN."""
        if self.state != CircuitState.OPEN or not self.opened_at:
            return False
        
        now = datetime.now(timezone.utc)
        time_since_opened = (now - self.opened_at).total_seconds()
        return time_since_opened >= self.config.cooldown_period
    
    def _log_state_change(self, old_state: CircuitState, new_state: CircuitState, reason: str):
        """Log circuit breaker state changes."""
        logger.warning(
            f"Circuit breaker state change: {old_state.value} → {new_state.value} - {reason}",
            extra={
                'circuit_breaker': {
                    'old_state': old_state.value,
                    'new_state': new_state.value,
                    'reason': reason,
                    'failure_rate': self._calculate_failure_rate(),
                    'window_size': len(self.request_window),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            }
        )
    
    def can_execute(self) -> bool:
        """Check if request can be executed based on circuit state."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.HALF_OPEN:
            return True
        elif self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                old_state = self.state
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self._log_state_change(old_state, self.state, "Cooldown period expired, testing service recovery")
                return True
            return False
        
        return False
    
    def record_success(self):
        """Record a successful request."""
        self.request_window.append(True)
        self.last_failure_time = None
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                old_state = self.state
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.opened_at = None
                self._log_state_change(old_state, self.state, 
                                     f"Service recovered after {self.success_count} consecutive successes")
        elif self.state == CircuitState.OPEN:
            # This shouldn't happen, but handle gracefully
            logger.warning("Received success while circuit is OPEN - this indicates a logic error")
    
    def record_failure(self):
        """Record a failed request and update circuit state."""
        self.request_window.append(False)
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.state == CircuitState.HALF_OPEN:
            # Failure during half-open means service is still down
            old_state = self.state
            self.state = CircuitState.OPEN
            self.opened_at = self.last_failure_time
            self.success_count = 0
            self._log_state_change(old_state, self.state, "Service still failing during recovery test")
        
        elif self.state == CircuitState.CLOSED:
            # Check if we should open the circuit
            failure_rate = self._calculate_failure_rate()
            if (len(self.request_window) >= self.config.window_size and 
                failure_rate >= self.config.failure_threshold):
                old_state = self.state
                self.state = CircuitState.OPEN
                self.opened_at = self.last_failure_time
                self._log_state_change(old_state, self.state, 
                                     f"Failure rate {failure_rate:.2%} exceeded threshold {self.config.failure_threshold:.2%}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state information."""
        return {
            'state': self.state.value,
            'failure_rate': self._calculate_failure_rate(),
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'window_size': len(self.request_window),
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'can_execute': self.can_execute()
        }
    
    def reset(self):
        """Reset circuit breaker to initial state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None
        self.request_window.clear()
        
        if old_state != CircuitState.CLOSED:
            self._log_state_change(old_state, self.state, "Circuit breaker manually reset")


class TTSErrorHandler:
    """Handles TTS errors with retry logic, rate limiting, circuit breaker, and graceful degradation."""
    
    def __init__(self, circuit_config: Optional[CircuitBreakerConfig] = None):
        self.error_state = TTSErrorState()
        self.circuit_breaker = CircuitBreaker(circuit_config)
        self.retry_config = {
            'max_retries_429': 3,
            'max_retries_5xx': 2,
            'base_delay_429': 1.0,
            'base_delay_5xx': 0.5,
            'max_delay_429': 16.0,
            'max_delay_5xx': 8.0,
            'jitter_factor': 0.25,
            # Timeout configuration
            'connection_timeout': 10.0,  # seconds
            'read_timeout': 30.0,        # seconds
            'total_timeout': 45.0        # seconds
        }
        self.recovery_check_interval = 30  # seconds
        self.max_recovery_checks = 10  # 5 minutes at 30s intervals
        self.reduced_check_interval = 120  # 2 minutes after max checks
    
    def _calculate_backoff_delay(self, attempt: int, base_delay: float, max_delay: float) -> float:
        """Calculate exponential backoff delay with jitter."""
        # Exponential backoff: base_delay * (2 ^ attempt)
        delay = base_delay * (2 ** attempt)
        delay = min(delay, max_delay)
        
        # Add jitter (±25% of calculated delay)
        jitter = delay * self.retry_config['jitter_factor']
        delay += random.uniform(-jitter, jitter)
        
        return max(0, delay)
    
    def _log_retry_attempt(self, attempt: int, max_attempts: int, error: Exception, delay: float):
        """Log retry attempt with detailed information."""
        error_code = getattr(error, 'error_code', 'UNKNOWN')
        status_code = getattr(error, 'status_code', None)
        
        log_data = {
            'operation': 'tts_synthesis',
            'attempt': attempt + 1,
            'max_attempts': max_attempts,
            'error_code': error_code,
            'error_message': str(error),
            'backoff_delay': delay,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if status_code:
            log_data['http_status'] = status_code
        
        logger.warning(
            f"TTS synthesis retry {attempt + 1}/{max_attempts} - "
            f"Error: {error_code} ({str(error)}) - "
            f"Retrying in {delay:.2f}s",
            extra=log_data
        )
    
    def _update_error_state(self, error: Optional[Exception] = None):
        """Update the current error state and circuit breaker."""
        if error:
            self.error_state.has_error = True
            self.error_state.error_type = getattr(error, 'error_code', 'UNKNOWN')
            self.error_state.error_message = str(error)
            self.error_state.last_error_time = datetime.now(timezone.utc)
            self.error_state.consecutive_failures += 1
            self.error_state.is_muted = True
            
            # Update circuit breaker state
            self.error_state.circuit_state = self.circuit_breaker.state
            self.error_state.circuit_opened_at = self.circuit_breaker.opened_at
            
            # Record failure in circuit breaker
            self.circuit_breaker.record_failure()
            
            logger.error(
                f"TTS error state updated - Type: {self.error_state.error_type}, "
                f"Failures: {self.error_state.consecutive_failures}, "
                f"Circuit: {self.circuit_breaker.state.value}, "
                f"Message: {self.error_state.error_message}"
            )
        else:
            # Clear error state on success
            if self.error_state.has_error:
                logger.info("TTS error state cleared - service recovered")
            
            self.error_state.has_error = False
            self.error_state.error_type = ""
            self.error_state.error_message = ""
            self.error_state.consecutive_failures = 0
            self.error_state.recovery_check_count = 0
            self.error_state.is_muted = False
            
            # Update circuit breaker state
            self.error_state.circuit_state = self.circuit_breaker.state
            self.error_state.circuit_opened_at = self.circuit_breaker.opened_at
            
            # Record success in circuit breaker
            self.circuit_breaker.record_success()
    
    def get_error_state(self) -> TTSErrorState:
        """Get the current error state."""
        # Update circuit state before returning
        self.error_state.circuit_state = self.circuit_breaker.state
        self.error_state.circuit_opened_at = self.circuit_breaker.opened_at
        return self.error_state
    
    def get_circuit_breaker_state(self) -> Dict[str, Any]:
        """Get detailed circuit breaker state information."""
        return self.circuit_breaker.get_state()
    
    def is_in_error_state(self) -> bool:
        """Check if TTS service is currently in error state."""
        return self.error_state.has_error
    
    def should_attempt_recovery(self) -> bool:
        """Determine if recovery should be attempted based on timing and attempt count."""
        if not self.error_state.has_error:
            return False
        
        if not self.error_state.last_error_time:
            return True
        
        now = datetime.now(timezone.utc)
        time_since_error = (now - self.error_state.last_error_time).total_seconds()
        
        # Use different intervals based on recovery check count
        if self.error_state.recovery_check_count < self.max_recovery_checks:
            interval = self.recovery_check_interval
        else:
            interval = self.reduced_check_interval
        
        return time_since_error >= interval
    
    async def attempt_recovery(self, tts_service, test_text: str = "Hi") -> bool:
        """
        Attempt to recover from error state by testing the API.

        Args:
            tts_service: The TTS service instance to test
            test_text: Text to use for health check (default: "Hi" for minimal token usage)

        Returns:
            True if recovery successful, False otherwise
        """
        if not self.should_attempt_recovery():
            return False

        self.error_state.recovery_check_count += 1

        try:
            # Perform a lightweight health check
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{tts_service.config.voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": tts_service.config.api_key
            }
            
            payload = {
                "text": test_text,
                "model_id": tts_service.config.model_id,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        logger.info(
                            f"TTS recovery successful after {self.error_state.recovery_check_count} attempts"
                        )
                        self._update_error_state()  # Clear error state
                        return True
                    else:
                        logger.warning(
                            f"TTS recovery check failed - Status: {response.status}, "
                            f"Attempt: {self.error_state.recovery_check_count}"
                        )
                        return False
        
        except Exception as e:
            logger.warning(
                f"TTS recovery check failed with exception - "
                f"Attempt: {self.error_state.recovery_check_count}, "
                f"Error: {str(e)}"
            )
            return False
    
    def _classify_http_error(self, status_code: int, response_text: str) -> TTSError:
        """Classify HTTP errors into appropriate TTS error types."""
        if status_code == 401:
            return TTSAPIKeyError("Invalid API key")
        elif status_code == 429:
            return TTSRateLimitError(f"Rate limit exceeded: {response_text}")
        elif 500 <= status_code < 600:
            return TTSServerError(f"Server error ({status_code}): {response_text}", status_code)
        else:
            return TTSError(f"HTTP error ({status_code}): {response_text}", error_code=f"HTTP_{status_code}")
    
    async def execute_with_retry(
        self,
        operation: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Execute TTS operation with comprehensive retry logic, circuit breaker, and timeout handling.
        
        Implements:
        - Circuit breaker pattern for resilience
        - Exponential backoff with jitter for different error types:
          - HTTP 429 (Rate Limit): 3 retries, 1s base delay, max 16s
          - HTTP 5xx (Server Error): 2 retries, 0.5s base delay, max 8s
          - Network errors: 2 retries with 5xx timing
        - Timeout handling (connection: 10s, read: 30s, total: 45s)
        
        Args:
            operation: The async operation to execute
            *args: Arguments to pass to the operation
            **kwargs: Keyword arguments to pass to the operation
            
        Returns:
            Result of the operation
            
        Raises:
            TTSCircuitOpenError: When circuit breaker is open
            TTSRetryExhaustedError: When all retries are exhausted
            TTSAPIKeyError: When API key is invalid (non-recoverable)
        """
        # Check circuit breaker first
        if not self.circuit_breaker.can_execute():
            circuit_state = self.circuit_breaker.get_state()
            error_msg = (f"Circuit breaker is {circuit_state['state']} - "
                        f"failure rate: {circuit_state['failure_rate']:.2%}")
            logger.warning(f"Request short-circuited: {error_msg}")
            raise TTSCircuitOpenError(error_msg)
        
        last_error = None
        
        for attempt in range(max(self.retry_config['max_retries_429'], self.retry_config['max_retries_5xx']) + 1):
            try:
                result = await operation(*args, **kwargs)
                # Success - clear error state and reset retry counters
                self._update_error_state()
                logger.info("TTS operation successful - error state cleared")
                return result
                
            except asyncio.TimeoutError as e:
                # Timeout errors - treat as network issues
                last_error = TTSNetworkError(f"Request timeout: {str(e)}", e)
                
                if attempt < self.retry_config['max_retries_5xx']:
                    delay = self._calculate_backoff_delay(
                        attempt,
                        self.retry_config['base_delay_5xx'],
                        self.retry_config['max_delay_5xx']
                    )
                    self._log_retry_attempt(attempt, self.retry_config['max_retries_5xx'], last_error, delay)
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Timeout retries exhausted after {attempt + 1} attempts")
                    break
            
            except aiohttp.ClientError as e:
                # Network connectivity issues
                last_error = TTSNetworkError(f"Network error: {str(e)}", e)
                
                if attempt < self.retry_config['max_retries_5xx']:
                    delay = self._calculate_backoff_delay(
                        attempt,
                        self.retry_config['base_delay_5xx'],
                        self.retry_config['max_delay_5xx']
                    )
                    self._log_retry_attempt(attempt, self.retry_config['max_retries_5xx'], last_error, delay)
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Network error retries exhausted after {attempt + 1} attempts")
                    break
            
            except aiohttp.ClientResponseError as e:
                if e.status == 429:  # Rate limit - use 429-specific retry config
                    last_error = TTSRateLimitError(f"Rate limit exceeded: {e.message}")
                    
                    if attempt < self.retry_config['max_retries_429']:
                        delay = self._calculate_backoff_delay(
                            attempt,
                            self.retry_config['base_delay_429'],
                            self.retry_config['max_delay_429']
                        )
                        self._log_retry_attempt(attempt, self.retry_config['max_retries_429'], last_error, delay)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Rate limit retries exhausted after {attempt + 1} attempts")
                        break
                
                elif 500 <= e.status < 600:  # Server errors - use 5xx-specific retry config
                    last_error = TTSServerError(f"Server error: {e.message}", e.status)
                    
                    if attempt < self.retry_config['max_retries_5xx']:
                        delay = self._calculate_backoff_delay(
                            attempt,
                            self.retry_config['base_delay_5xx'],
                            self.retry_config['max_delay_5xx']
                        )
                        self._log_retry_attempt(attempt, self.retry_config['max_retries_5xx'], last_error, delay)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Server error retries exhausted after {attempt + 1} attempts")
                        break
                
                elif e.status == 401:
                    # API key error - don't retry, immediately fail
                    last_error = TTSAPIKeyError("Invalid API key")
                    logger.error("API key error detected - no retries will be attempted")
                    break
                
                else:
                    # Other HTTP errors - don't retry
                    last_error = self._classify_http_error(e.status, str(e))
                    logger.error(f"Non-retryable HTTP error {e.status} - no retries will be attempted")
                    break
            
            except TTSAPIKeyError:
                # API key errors should not be retried
                logger.error("API key error detected - no retries will be attempted")
                raise
            
            except Exception as e:
                # Unexpected errors - don't retry to avoid infinite loops
                last_error = TTSError(f"Unexpected error: {str(e)}", original_error=e)
                logger.error(f"Unexpected error during TTS operation: {str(e)} - no retries will be attempted")
                break
        
        # All retries exhausted or non-recoverable error occurred
        self._update_error_state(last_error)
        
        if isinstance(last_error, TTSAPIKeyError):
            # Don't wrap API key errors - they should be handled directly
            raise last_error
        else:
            # Wrap other errors in retry exhausted error
            total_attempts = attempt + 1
            logger.error(f"TTS operation failed after {total_attempts} attempts - falling back to muted state")
            raise TTSRetryExhaustedError(
                f"TTS synthesis failed after {total_attempts} attempts - service will fall back to muted state",
                attempts=total_attempts,
                last_error=last_error
            )


def tts_error_handler(
    max_retries_429: int = 3,
    max_retries_5xx: int = 2,
    base_delay_429: float = 1.0,
    base_delay_5xx: float = 0.5,
    max_delay_429: float = 16.0,
    max_delay_5xx: float = 8.0,
    jitter_factor: float = 0.25
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for TTS operations with comprehensive error handling.
    
    Args:
        max_retries_429: Maximum retries for rate limit errors
        max_retries_5xx: Maximum retries for server errors
        base_delay_429: Base delay for rate limit retries
        base_delay_5xx: Base delay for server error retries
        max_delay_429: Maximum delay for rate limit retries
        max_delay_5xx: Maximum delay for server error retries
        jitter_factor: Jitter factor for backoff delays
        
    Returns:
        Decorated function with error handling
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            handler = TTSErrorHandler()
            handler.retry_config.update({
                'max_retries_429': max_retries_429,
                'max_retries_5xx': max_retries_5xx,
                'base_delay_429': base_delay_429,
                'base_delay_5xx': base_delay_5xx,
                'max_delay_429': max_delay_429,
                'max_delay_5xx': max_delay_5xx,
                'jitter_factor': jitter_factor
            })
            
            return await handler.execute_with_retry(func, *args, **kwargs)
        
        return wrapper
    return decorator


# Global error handler instance for the TTS service
_global_tts_error_handler: Optional[TTSErrorHandler] = None


def get_tts_error_handler() -> TTSErrorHandler:
    """Get the global TTS error handler instance."""
    global _global_tts_error_handler
    if _global_tts_error_handler is None:
        _global_tts_error_handler = TTSErrorHandler()
    return _global_tts_error_handler


def reset_tts_error_handler():
    """Reset the global TTS error handler (useful for testing)."""
    global _global_tts_error_handler
    _global_tts_error_handler = None