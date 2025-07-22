"""
URL Error Handling Module

This module provides robust error handling utilities for URL metadata operations,
including custom exceptions, retry mechanisms with exponential backoff, and
graceful degradation strategies.
"""

import functools
import logging
import time
from typing import Any, Callable, Optional, TypeVar
from urllib.parse import urlparse
import random

# Import our structured logging infrastructure
from btc_max_knowledge_agent.utils.url_metadata_logger import (
    log_retry
)

logger = logging.getLogger(__name__)

# Type variable for generic return type
T = TypeVar('T')


class URLMetadataError(Exception):
    """Base exception for all URL metadata-related errors."""
    
    def __init__(self, message: str, url: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.url = url
        self.original_error = original_error
        
    def __str__(self):
        base_msg = super().__str__()
        if self.url:
            base_msg += f" (URL: {self.url})"
        if self.original_error:
            base_msg += f" - Original error: {str(self.original_error)}"
        return base_msg


class URLValidationError(URLMetadataError):
    """Raised when URL validation fails."""
    pass


class URLMetadataUploadError(URLMetadataError):
    """Raised when URL metadata upload to Pinecone fails."""
    pass


class URLRetrievalError(URLMetadataError):
    """Raised when URL metadata retrieval fails."""
    pass


class RetryExhaustedError(URLMetadataError):
    """Raised when all retry attempts are exhausted."""
    
    def __init__(self, message: str, attempts: int, last_error: Optional[Exception] = None):
        super().__init__(message, original_error=last_error)
        self.attempts = attempts


def exponential_backoff_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    fallback_result: Optional[Any] = None,
    raise_on_exhaust: bool = True
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that implements exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        jitter: Whether to add random jitter to delays (default: True)
        exceptions: Tuple of exceptions to catch and retry (default: (Exception,))
        fallback_result: Result to return if all retries fail (default: None)
        raise_on_exhaust: Whether to raise exception when retries exhausted (default: True)
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    
                    if attempt == max_retries:
                        # Log the final failure
                        log_retry(
                            operation=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=max_retries + 1,
                            error=str(e)
                        )
                        logger.error(f"All {max_retries} retry attempts "
                                   f"exhausted for {func.__name__}")
                        if raise_on_exhaust:
                            raise RetryExhaustedError(
                                f"Failed after {max_retries + 1} attempts",
                                attempts=max_retries + 1,
                                last_error=e
                            )
                        else:
                            logger.warning(
                                f"Returning fallback result: {fallback_result}"
                            )
                            return fallback_result
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # Add jitter if enabled
                    if jitter:
                        delay = delay * (0.9 + random.random() * 0.2)  # ±10% jitter
                    
                    # Log the retry attempt
                    log_retry(
                        operation=func.__name__,
                        attempt=attempt + 1,
                        max_attempts=max_retries + 1,
                        error=str(e)
                    )
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed "
                        f"for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    time.sleep(delay)
            
            # This should never be reached due to the logic above
            raise AssertionError("Unreachable code in retry logic")
        
        return wrapper
    return decorator


class FallbackURLStrategy:
    """Provides fallback strategies for URL generation when primary methods fail."""
    
    @staticmethod
    def domain_only_url(original_url: str) -> Optional[str]:
        """
        Extract domain-only URL as fallback.
        
        Args:
            original_url: The original URL that failed
            
        Returns:
            Domain-only URL or None if extraction fails
        """
        try:
            parsed = urlparse(original_url)
            if parsed.netloc:
                scheme = parsed.scheme or 'https'
                return f"{scheme}://{parsed.netloc}"
        except Exception as e:
            logger.error(f"Failed to extract domain from URL: {e}")
        return None
    
    @staticmethod
    def placeholder_url(identifier: Optional[str] = None) -> str:
        """
        Generate a placeholder URL.
        
        Args:
            identifier: Optional identifier to include in placeholder
            
        Returns:
            Placeholder URL
        """
        if identifier:
            return f"https://placeholder.local/{identifier}"
        return "https://placeholder.local/document"
    
    @staticmethod
    def empty_url() -> str:
        """Return empty string as ultimate fallback."""
        return ""


class GracefulDegradation:
    """Utilities for graceful degradation of URL operations."""
    
    @staticmethod
    def safe_url_operation(
        operation: Callable[..., T],
        fallback_strategies: list[Callable[..., Any]] = None,
        operation_name: str = "URL operation"
    ) -> Callable[..., Optional[T]]:
        """
        Wrap URL operation with graceful degradation.
        
        Args:
            operation: The operation to wrap
            fallback_strategies: List of fallback strategies to try
            operation_name: Name of operation for logging
            
        Returns:
            Wrapped operation that handles failures gracefully
        """
        if fallback_strategies is None:
            fallback_strategies = []
        
        @functools.wraps(operation)
        def wrapper(*args, **kwargs) -> Optional[T]:
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                logger.error(f"{operation_name} failed: {e}")
                
                # Try fallback strategies
                for i, strategy in enumerate(fallback_strategies):
                    try:
                        logger.info(f"Attempting fallback strategy {i + 1}/{len(fallback_strategies)}")
                        return strategy(*args, **kwargs)
                    except Exception as fallback_error:
                        logger.warning(f"Fallback strategy {i + 1} failed: {fallback_error}")
                
                logger.error(f"All fallback strategies exhausted for {operation_name}")
                return None
        
        return wrapper
    
    @staticmethod
    def null_safe_metadata(metadata: Optional[dict]) -> dict:
        """
        Ensure metadata is safe for operations even with missing URL data.
        
        Args:
            metadata: Original metadata dictionary
            
        Returns:
            Metadata with safe defaults for missing URL fields
        """
        if metadata is None:
            metadata = {}
        
        # Ensure all URL-related fields have safe defaults
        url_fields = ['url', 'source_url', 'document_url', 'reference_url']
        for field in url_fields:
            if field not in metadata or metadata[field] is None:
                metadata[field] = ''
        
        return metadata
    
    @staticmethod
    def create_partial_result(
        success_data: dict,
        failed_operations: list[str],
        error_details: Optional[dict] = None
    ) -> dict:
        """
        Create a partial result when some operations succeed and others fail.
        
        Args:
            success_data: Data from successful operations
            failed_operations: List of operations that failed
            error_details: Optional details about errors
            
        Returns:
            Combined result with success data and error information
        """
        result = {
            'status': 'partial_success',
            'data': success_data,
            'errors': {
                'failed_operations': failed_operations,
                'error_count': len(failed_operations)
            }
        }
        
        if error_details:
            result['errors']['details'] = error_details
        
        return result


# Configuration constants for consistency
MAX_QUERY_RETRIES = 10
DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_MAX_DELAY = 60.0
DEFAULT_EXPONENTIAL_BASE = 2.0


# Enhanced convenience wrapper that maintains consistency with MAX_QUERY_RETRIES
def query_retry_with_backoff(
    max_retries: Optional[int] = None,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    fallback_result: Optional[Any] = None,
    raise_on_exhaust: bool = True
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Enhanced retry decorator that maintains consistency with MAX_QUERY_RETRIES.
    
    This wrapper provides a standardized retry mechanism with exponential backoff
    and jitter that's consistent across the application. It automatically uses
    MAX_QUERY_RETRIES if no specific max_retries is provided.
    
    Args:
        max_retries: Maximum retry attempts (uses MAX_QUERY_RETRIES if None)
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        exceptions: Tuple of exceptions to catch and retry
        fallback_result: Result to return if all retries fail
        raise_on_exhaust: Whether to raise exception when retries exhausted
    
    Returns:
        Decorated function with retry logic
        
    Example:
        @query_retry_with_backoff(exceptions=(requests.RequestException,))
        def query_external_api():
            # Your query logic here
            pass
    """
    effective_max_retries = max_retries if max_retries is not None else MAX_QUERY_RETRIES
    
    return exponential_backoff_retry(
        max_retries=effective_max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        exceptions=exceptions,
        fallback_result=fallback_result,
        raise_on_exhaust=raise_on_exhaust
    )


# Convenience functions for common retry scenarios
def retry_url_validation(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator specifically for URL validation operations."""
    return exponential_backoff_retry(
        max_retries=3,
        initial_delay=0.5,
        max_delay=10.0,
        exceptions=(URLValidationError, ValueError, ConnectionError),
        raise_on_exhaust=False
    )(func)


def retry_url_upload(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator specifically for URL upload operations."""
    return exponential_backoff_retry(
        max_retries=5,
        initial_delay=1.0,
        max_delay=30.0,
        exceptions=(URLMetadataUploadError, ConnectionError, TimeoutError),
        raise_on_exhaust=True
    )(func)


def retry_url_retrieval(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator specifically for URL retrieval operations."""
    return exponential_backoff_retry(
        max_retries=3,
        initial_delay=0.5,
        max_delay=15.0,
        exceptions=(URLRetrievalError, ConnectionError, TimeoutError),
        raise_on_exhaust=False,
        fallback_result={}
    )(func)
