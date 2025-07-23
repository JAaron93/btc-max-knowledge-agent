"""
URL Metadata Logger with structured logging, correlation IDs, and specialized loggers.
Provides comprehensive logging infrastructure for URL-related operations.
"""

import json
import logging
import logging.handlers
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import local
from typing import Any, Dict, List, Optional

# Logging configuration constants
LOG_ROTATION_MAX_BYTES = 50 * 1024 * 1024  # 50MB
LOG_ROTATION_BACKUP_COUNT = 5

# Thread-local storage for correlation IDs

__all__ = [
    "URLMetadataLogger",
    "url_metadata_logger",
    "log_validation",
    "log_sanitization",
    "log_upload",
    "log_retrieval",
    "log_retry",
    "log_metrics",
    "correlation_context",
    "set_correlation_id",
    "get_correlation_id",
    "LOG_ROTATION_MAX_BYTES",
    "LOG_ROTATION_BACKUP_COUNT",
    "logger",
]

_thread_locals = local()


class CorrelationIdFilter(logging.Filter):
    """Adds correlation ID to log records."""

    def filter(self, record):
        record.correlation_id = getattr(
            _thread_locals, "correlation_id", "no-correlation-id"
        )
        return True


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": getattr(record, "correlation_id", "no-correlation-id"),
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add custom fields from extra
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class URLMetadataLogger:
    """Central logging configuration for URL metadata operations."""

    def __init__(self, log_dir: str = "logs", query_truncation_length: int = 100):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Configure root logger
        self._configure_root_logger()

        # Create specialized loggers
        self.validation_logger = self._create_logger("url_metadata.validation")
        self.upload_logger = self._create_logger("url_metadata.upload")
        self.retrieval_logger = self._create_logger("url_metadata.retrieval")
        self.sanitization_logger = self._create_logger("url_metadata.sanitization")
        self.retry_logger = self._create_logger("url_metadata.retry")
        self.metrics_logger = self._create_logger("url_metadata.metrics")

        # Alert thresholds
        self.alert_thresholds = {
            "validation_failure_rate": 0.10,  # 10%
            "upload_failure_rate": 0.05,  # 5%
            "retry_max_attempts": 5,
            "response_time_ms": 5000,
        }

        # Configuration options
        self.config = {
            "query_truncation_length": query_truncation_length,  # Configurable truncation length for query logging
        }

    def _configure_root_logger(self):
        """Configure the root logger with appropriate handlers."""
        root_logger = logging.getLogger("url_metadata")
        root_logger.setLevel(logging.DEBUG)

        # Only add handlers if none exist
        if not root_logger.handlers:
            # Add correlation ID filter to all handlers
            correlation_filter = CorrelationIdFilter()

            # Console handler for warnings and above
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(JsonFormatter())
            console_handler.addFilter(correlation_filter)
            root_logger.addHandler(console_handler)

    def _create_logger(self, name: str) -> logging.Logger:
        """Create a specialized logger with appropriate handlers."""
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Create a single handler that will handle all log levels
        log_prefix = name.split(".")[-1]
        handler = self._create_combined_file_handler(log_prefix)

        # Add correlation filter and formatter
        correlation_filter = CorrelationIdFilter()
        formatter = JsonFormatter()

        handler.addFilter(correlation_filter)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Prevent propagation to parent loggers to avoid duplicate logging
        logger.propagate = False

        return logger

    def _create_combined_file_handler(self, log_prefix: str) -> logging.Handler:
        """Create a single handler that routes messages to appropriate files."""

        class LevelBasedFileHandler(logging.Handler):
            """Custom handler that routes messages to different files based on level."""

            def __init__(self, log_dir, prefix):
                super().__init__(level=logging.DEBUG)
                self.log_dir = log_dir
                self.prefix = prefix
                self.handlers = {}
                self._setup_handlers()

            def _setup_handlers(self):
                """Set up the actual file handlers for different log levels."""
                # Individual log files for each level
                self.handlers = {
                    logging.DEBUG: self._create_rotating_handler(
                        f"{self.prefix}_debug.log"
                    ),
                    logging.INFO: self._create_rotating_handler(
                        f"{self.prefix}_info.log"
                    ),
                    logging.ERROR: self._create_rotating_handler(
                        f"{self.prefix}_error.log"
                    ),
                    "all": self._create_rotating_handler("all_operations.log"),
                }

            def _create_rotating_handler(self, filename):
                """Create a rotating file handler with standard settings."""
                filepath = self.log_dir / filename
                handler = logging.handlers.RotatingFileHandler(
                    filepath,
                    maxBytes=LOG_ROTATION_MAX_BYTES,
                    backupCount=LOG_ROTATION_BACKUP_COUNT,
                    encoding="utf-8",
                )
                handler.setFormatter(logging.Formatter("%(message)s"))
                return handler

            def emit(self, record):
                """Emit a record to the appropriate log file(s)."""
                try:
                    # Write to the specific level log file
                    if record.levelno >= logging.ERROR:
                        self.handlers[logging.ERROR].emit(record)
                    elif record.levelno >= logging.INFO:
                        self.handlers[logging.INFO].emit(record)
                    else:  # DEBUG
                        self.handlers[logging.DEBUG].emit(record)

                    # Always write to the all_operations.log
                    self.handlers["all"].emit(record)
                except Exception:
                    self.handleError(record)

            def close(self):
                """Close all file handlers."""
                for handler in self.handlers.values():
                    try:
                        handler.close()
                    except Exception:
                        pass
                super().close()

        return LevelBasedFileHandler(self.log_dir, log_prefix)

    @staticmethod
    def generate_correlation_id() -> str:
        """Generate a new correlation ID."""
        return str(uuid.uuid4())

    @staticmethod
    @contextmanager
    def correlation_context(correlation_id: Optional[str] = None):
        """Context manager for setting correlation ID."""
        if correlation_id is None:
            correlation_id = URLMetadataLogger.generate_correlation_id()

        old_id = getattr(_thread_locals, "correlation_id", None)
        _thread_locals.correlation_id = correlation_id

        try:
            yield correlation_id
        finally:
            if old_id is not None:
                _thread_locals.correlation_id = old_id
            else:
                delattr(_thread_locals, "correlation_id")

    @staticmethod
    def set_correlation_id(correlation_id: Optional[str]) -> None:
        """Set correlation ID outside of context manager (compat shim)."""
        if correlation_id is None:
            if hasattr(_thread_locals, "correlation_id"):
                delattr(_thread_locals, "correlation_id")
        else:
            _thread_locals.correlation_id = correlation_id

    @staticmethod
    def get_logger(logger_type: str) -> logging.Logger:
        """Get a specific logger from the global instance."""
        logger_map = {
            "validation": url_metadata_logger.validation_logger,
            "upload": url_metadata_logger.upload_logger,
            "retrieval": url_metadata_logger.retrieval_logger,
            "sanitization": url_metadata_logger.sanitization_logger,
            "retry": url_metadata_logger.retry_logger,
            "metrics": url_metadata_logger.metrics_logger,
        }
        return logger_map.get(
            logger_type, logging.getLogger(f"url_metadata.{logger_type}")
        )

    def log_validation(
        self,
        url: str,
        is_valid: bool,
        validation_type: str,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ):
        """Log URL validation operations."""
        extra_fields = {
            "operation": "validation",
            "url": self._sanitize_url_for_logging(url),
            "is_valid": is_valid,
            "validation_type": validation_type,
            "duration_ms": duration_ms,
        }

        if details:
            extra_fields["details"] = details

        level = logging.INFO if is_valid else logging.WARNING
        self.validation_logger.log(
            level,
            f"URL validation {'succeeded' if is_valid else 'failed'}: {validation_type}",
            extra={"extra_fields": extra_fields},
        )

    def log_sanitization(
        self,
        original_url: str,
        sanitized_url: str,
        changes_made: List[str],
        duration_ms: Optional[float] = None,
    ):
        """Log URL sanitization operations."""
        extra_fields = {
            "operation": "sanitization",
            "original_url": self._sanitize_url_for_logging(original_url),
            "sanitized_url": self._sanitize_url_for_logging(sanitized_url),
            "changes_made": changes_made,
            "duration_ms": duration_ms,
        }

        self.sanitization_logger.info(
            f"URL sanitized with {len(changes_made)} changes",
            extra={"extra_fields": extra_fields},
        )

    def log_upload(
        self,
        url: str,
        success: bool,
        metadata_size: int,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ):
        """Log URL metadata upload operations."""
        extra_fields = {
            "operation": "upload",
            "url": self._sanitize_url_for_logging(url),
            "success": success,
            "metadata_size": metadata_size,
            "duration_ms": duration_ms,
        }

        if error:
            extra_fields["error"] = error

        level = logging.INFO if success else logging.ERROR
        self.upload_logger.log(
            level,
            f"Metadata upload {'succeeded' if success else 'failed'} for URL",
            extra={"extra_fields": extra_fields},
        )

    def log_retrieval(
        self, query: str, results_count: int, duration_ms: Optional[float] = None
    ):
        """Log URL metadata retrieval operations."""
        extra_fields = {
            "operation": "retrieval",
            "query": query[
                : self.config["query_truncation_length"]
            ],  # Configurable query truncation
            "results_count": results_count,
            "duration_ms": duration_ms,
        }

        self.retrieval_logger.info(
            f"Retrieved {results_count} results", extra={"extra_fields": extra_fields}
        )

    def log_retry(
        self,
        operation: str,
        attempt: int,
        max_attempts: int,
        error: str,
        url: Optional[str] = None,
    ):
        """Log retry attempts."""
        extra_fields = {
            "operation": "retry",
            "retry_operation": operation,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "error": error,
        }

        if url:
            extra_fields["url"] = self._sanitize_url_for_logging(url)

        level = logging.WARNING if attempt < max_attempts else logging.ERROR
        self.retry_logger.log(
            level,
            f"Retry attempt {attempt}/{max_attempts} for {operation}",
            extra={"extra_fields": extra_fields},
        )

        # Check if we need to trigger an alert
        if attempt >= self.alert_thresholds["retry_max_attempts"]:
            self._trigger_alert("excessive_retries", extra_fields)

    def log_metrics(self, metrics: Dict[str, Any]):
        """Log aggregated metrics."""
        extra_fields = {
            "operation": "metrics",
            "metrics": metrics,
        }

        self.metrics_logger.info("Metrics update", extra={"extra_fields": extra_fields})

        # Check alert thresholds
        self._check_metric_alerts(metrics)

    def _sanitize_url_for_logging(self, url: str) -> str:
        """Sanitize URL to remove sensitive information."""
        # Remove query parameters that might contain sensitive data
        if "?" in url:
            base_url = url.split("?")[0]
            return f"{base_url}?[params_removed]"
        return url

    def _check_metric_alerts(self, metrics: Dict[str, Any]):
        """Check metrics against alert thresholds."""
        if "validation_failure_rate" in metrics:
            if (
                metrics["validation_failure_rate"]
                > self.alert_thresholds["validation_failure_rate"]
            ):
                self._trigger_alert("high_validation_failure_rate", metrics)

        if "upload_failure_rate" in metrics:
            if (
                metrics["upload_failure_rate"]
                > self.alert_thresholds["upload_failure_rate"]
            ):
                self._trigger_alert("high_upload_failure_rate", metrics)

        if "avg_response_time_ms" in metrics:
            if (
                metrics["avg_response_time_ms"]
                > self.alert_thresholds["response_time_ms"]
            ):
                self._trigger_alert("slow_response_time", metrics)

    def _trigger_alert(self, alert_type: str, details: Dict[str, Any]):
        """Trigger an alert (placeholder for actual alerting mechanism)."""
        alert_data = {
            "alert_type": alert_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }

        # Log the alert
        self.metrics_logger.critical(
            f"ALERT: {alert_type}", extra={"extra_fields": alert_data}
        )

        # Here you would integrate with your alerting system
        # (e.g., send email, Slack notification, PagerDuty, etc.)


# Global logger instance
url_metadata_logger = URLMetadataLogger()

# Module-level logger for backward compatibility
logger: logging.Logger = logging.getLogger("url_metadata")


# Convenience functions
def log_validation(url: str, is_valid: bool, validation_type: str, **kwargs):
    """Convenience function for logging validation."""
    url_metadata_logger.log_validation(url, is_valid, validation_type, **kwargs)


def log_sanitization(
    original_url: str, sanitized_url: str, changes_made: List[str], **kwargs
):
    """Convenience function for logging sanitization."""
    url_metadata_logger.log_sanitization(
        original_url, sanitized_url, changes_made, **kwargs
    )


def log_upload(url: str, success: bool, metadata_size: int, **kwargs):
    """Convenience function for logging uploads."""
    url_metadata_logger.log_upload(url, success, metadata_size, **kwargs)


def log_retrieval(query: str, results_count: int, **kwargs):
    """Convenience function for logging retrieval."""
    url_metadata_logger.log_retrieval(query, results_count, **kwargs)


def log_retry(operation: str, attempt: int, max_attempts: int, error: str, **kwargs):
    """Convenience function for logging retries."""
    url_metadata_logger.log_retry(operation, attempt, max_attempts, error, **kwargs)


def log_metrics(metrics: Dict[str, Any]):
    """Convenience function for logging metrics."""
    url_metadata_logger.log_metrics(metrics)


# Export correlation context
correlation_context = URLMetadataLogger.correlation_context
generate_correlation_id = URLMetadataLogger.generate_correlation_id


def set_correlation_id(correlation_id: Optional[str] = None) -> None:
    """Set correlation ID globally for the current thread."""
    URLMetadataLogger.set_correlation_id(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Retrieve the current correlation ID for the current thread, if set."""
    return getattr(_thread_locals, "correlation_id", None)
