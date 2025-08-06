"""
Optimized logging configuration to address performance overhead issues.

This module provides performance-optimized logging that:
1. Uses conditional logging to avoid expensive string formatting
2. Implements lazy evaluation for log messages
3. Provides configurable log levels to reduce overhead in production
4. Uses efficient handlers and formatters
5. Implements log level filtering at multiple stages
"""

import logging
import os
import sys
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional


class LazyLogRecord:
    """Lazy evaluation wrapper for expensive log message construction."""

    def __init__(self, func: Callable[[], str], *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._cached_result: Optional[str] = None

    def __str__(self) -> str:
        if self._cached_result is None:
            self._cached_result = self.func(*self.args, **self.kwargs)
        return self._cached_result


class PerformanceOptimizedLogger:
    """Performance-optimized logger with conditional logging and lazy evaluation."""

    def __init__(self, name: str, level: Optional[str] = None):
        self.logger = logging.getLogger(name)

        # Set log level from environment or default
        log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Track if expensive operations should be logged
        self._debug_enabled = self.logger.isEnabledFor(logging.DEBUG)
        self._info_enabled = self.logger.isEnabledFor(logging.INFO)

        # Setup optimized handler if none exists
        if not self.logger.handlers:
            self._setup_optimized_handler()

    def _setup_optimized_handler(self):
        """Setup an optimized console handler."""
        handler = logging.StreamHandler(sys.stdout)

        # Use a simple, fast formatter for performance
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",  # Shorter timestamp format
        )
        handler.setFormatter(formatter)

        # Only log warnings and above to console by default
        console_level = os.getenv("CONSOLE_LOG_LEVEL", "WARNING").upper()
        handler.setLevel(getattr(logging, console_level, logging.WARNING))

        self.logger.addHandler(handler)

        # Prevent propagation to avoid duplicate logging
        self.logger.propagate = False

    def is_debug_enabled(self) -> bool:
        """Check if debug logging is enabled to avoid expensive operations."""
        return self._debug_enabled

    def is_info_enabled(self) -> bool:
        """Check if info logging is enabled to avoid expensive operations."""
        return self._info_enabled

    def debug_lazy(self, msg_func: Callable[[], str], *args, **kwargs):
        """Debug logging with lazy evaluation."""
        if self._debug_enabled:
            self.logger.debug(LazyLogRecord(msg_func, *args, **kwargs))

    def info_lazy(self, msg_func: Callable[[], str], *args, **kwargs):
        """Info logging with lazy evaluation."""
        if self._info_enabled:
            self.logger.info(LazyLogRecord(msg_func, *args, **kwargs))

    def debug(self, msg: str, *args, **kwargs):
        """Conditional debug logging."""
        if self._debug_enabled:
            self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Conditional info logging."""
        if self._info_enabled:
            self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Warning logging (always enabled)."""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Error logging (always enabled)."""
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Critical logging (always enabled)."""
        self.logger.critical(msg, *args, **kwargs)


class OptimizedURLMetadataLogger:
    """Optimized version of URLMetadataLogger focused on performance."""

    def __init__(self, log_level: str = "INFO"):
        # Use optimized loggers
        self.validation_logger = PerformanceOptimizedLogger(
            "url_metadata.validation", log_level
        )
        self.upload_logger = PerformanceOptimizedLogger(
            "url_metadata.upload", log_level
        )
        self.retrieval_logger = PerformanceOptimizedLogger(
            "url_metadata.retrieval", log_level
        )
        self.sanitization_logger = PerformanceOptimizedLogger(
            "url_metadata.sanitization", log_level
        )
        self.retry_logger = PerformanceOptimizedLogger("url_metadata.retry", log_level)
        self.metrics_logger = PerformanceOptimizedLogger(
            "url_metadata.metrics", log_level
        )

        # Configuration
        self.config = {
            "query_truncation_length": int(os.getenv("QUERY_TRUNCATION_LENGTH", "100")),
            "url_truncation_length": int(os.getenv("URL_TRUNCATION_LENGTH", "200")),
        }

    def log_validation(
        self,
        url: str,
        is_valid: bool,
        validation_type: str,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ):
        """Optimized validation logging."""
        if is_valid:
            # Only log successful validations at debug level to reduce noise
            self.validation_logger.debug(
                f"URL validation succeeded: {validation_type} for {self._truncate_url(url)}"
            )
        else:
            # Log failures at warning level
            msg = f"URL validation failed: {validation_type} for {self._truncate_url(url)}"
            if duration_ms:
                msg += f" (took {duration_ms:.1f}ms)"
            if details:
                msg += f" - Details: {details}"
            self.validation_logger.warning(msg)

    def log_sanitization(
        self,
        original_url: str,
        sanitized_url: str,
        changes_made: list,
        duration_ms: Optional[float] = None,
    ):
        """Optimized sanitization logging."""
        if changes_made:
            self.sanitization_logger.info(
                f"URL sanitized: {len(changes_made)} changes - "
                f"{self._truncate_url(original_url)} -> {self._truncate_url(sanitized_url)}"
            )
        else:
            # Only log at debug level if no changes were made
            self.sanitization_logger.debug(
                f"URL already clean: {self._truncate_url(original_url)}"
            )

    def log_upload(
        self,
        url: str,
        success: bool,
        metadata_size: int,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ):
        """Optimized upload logging."""
        if success:
            # Use lazy evaluation for successful uploads to avoid string formatting overhead
            def success_msg():
                msg = f"Upload succeeded for {self._truncate_url(url)} ({metadata_size} bytes)"
                if duration_ms:
                    msg += f" in {duration_ms:.1f}ms"
                return msg

            self.upload_logger.info_lazy(success_msg)
        else:
            # Always log failures
            msg = f"Upload failed for {self._truncate_url(url)}"
            if error:
                msg += f": {error}"
            if duration_ms:
                msg += f" (took {duration_ms:.1f}ms)"
            self.upload_logger.error(msg)

    def log_retrieval(
        self, query: str, results_count: int, duration_ms: Optional[float] = None
    ):
        """Optimized retrieval logging."""

        # Use lazy evaluation to avoid expensive query truncation unless needed
        def retrieval_msg():
            truncated_query = query[: self.config["query_truncation_length"]]
            msg = f"Retrieved {results_count} results for query: '{truncated_query}'"
            if len(query) > self.config["query_truncation_length"]:
                msg += "..."
            if duration_ms:
                msg += f" ({duration_ms:.1f}ms)"
            return msg

        self.retrieval_logger.info_lazy(retrieval_msg)

    def log_retry(
        self,
        operation: str,
        attempt: int,
        max_attempts: int,
        error: str,
        url: Optional[str] = None,
    ):
        """Optimized retry logging."""
        level = "warning" if attempt < max_attempts else "error"

        msg = f"Retry {attempt}/{max_attempts} for {operation}: {error}"
        if url:
            msg += f" (URL: {self._truncate_url(url)})"

        getattr(self.retry_logger, level)(msg)

    def log_metrics(self, metrics: Dict[str, Any]):
        """Optimized metrics logging."""
        # Only log metrics at debug level unless there are alerts
        has_alerts = any(
            key.endswith("_failure_rate") and value > 0.05
            for key, value in metrics.items()
            if isinstance(value, (int, float))
        )

        if has_alerts:
            self.metrics_logger.warning(f"Metrics alert: {metrics}")
        else:
            self.metrics_logger.debug(f"Metrics update: {len(metrics)} metrics")

    def _truncate_url(self, url: str) -> str:
        """Efficiently truncate URL for logging."""
        max_len = self.config["url_truncation_length"]
        if len(url) <= max_len:
            return url
        return url[:max_len] + "..."


def timed_operation(logger: PerformanceOptimizedLogger, operation_name: str):
    """Decorator to time operations and log performance."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if logger.is_debug_enabled():
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000
                    logger.debug(f"{operation_name} completed in {duration_ms:.1f}ms")
                    return result
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.error(
                        f"{operation_name} failed after {duration_ms:.1f}ms: {e}"
                    )
                    raise
            else:
                # Skip timing overhead if debug logging is disabled
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Global optimized logger instance
optimized_url_metadata_logger = OptimizedURLMetadataLogger(
    log_level=os.getenv("URL_METADATA_LOG_LEVEL", "INFO")
)


# Convenience functions for backward compatibility
def log_validation_optimized(url: str, is_valid: bool, validation_type: str, **kwargs):
    """Optimized validation logging function."""
    optimized_url_metadata_logger.log_validation(
        url, is_valid, validation_type, **kwargs
    )


def log_upload_optimized(url: str, success: bool, metadata_size: int, **kwargs):
    """Optimized upload logging function."""
    optimized_url_metadata_logger.log_upload(url, success, metadata_size, **kwargs)


def log_retrieval_optimized(query: str, results_count: int, **kwargs):
    """Optimized retrieval logging function."""
    optimized_url_metadata_logger.log_retrieval(query, results_count, **kwargs)


def log_retry_optimized(
    operation: str, attempt: int, max_attempts: int, error: str, **kwargs
):
    """Optimized retry logging function."""
    optimized_url_metadata_logger.log_retry(
        operation, attempt, max_attempts, error, **kwargs
    )


def log_metrics_optimized(metrics: Dict[str, Any]):
    """Optimized metrics logging function."""
    optimized_url_metadata_logger.log_metrics(metrics)


# Environment-based configuration
def configure_optimized_logging():
    """Configure optimized logging based on environment variables."""

    # Set root logging level
    root_level = os.getenv("ROOT_LOG_LEVEL", "WARNING").upper()
    logging.getLogger().setLevel(getattr(logging, root_level, logging.WARNING))

    # Disable verbose logging from third-party libraries
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pinecone").setLevel(logging.WARNING)

    # Set specific loggers based on environment
    if os.getenv("ENVIRONMENT") == "production":
        # In production, only log warnings and errors by default
        for logger_name in [
            "url_metadata.validation",
            "url_metadata.upload",
            "url_metadata.retrieval",
            "url_metadata.sanitization",
        ]:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    return True


# Auto-configure on import
configure_optimized_logging()
