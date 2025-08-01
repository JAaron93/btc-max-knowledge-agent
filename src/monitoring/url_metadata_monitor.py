"""
URL Metadata Monitor for metrics collection, monitoring, and alert generation.
Tracks validation success rates, broken links, performance metrics, and generates reports.
"""

import json
import logging
import statistics
import threading
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


@dataclass
class URLMetric:
    """Represents a single metric data point."""

    timestamp: datetime
    operation_type: str
    success: bool
    duration_ms: float
    url: Optional[str] = None
    error_type: Optional[str] = None
    metadata_size: Optional[int] = None
    correlation_id: Optional[str] = None
    query: Optional[str] = None
    results_count: Optional[int] = None


@dataclass
class AlertThreshold:
    """Defines alert threshold configuration."""

    name: str
    threshold_value: float
    window_minutes: int
    cooldown_minutes: int = 60


class URLMetadataMonitor:
    """Monitor for URL metadata operations with metrics collection and alerting."""

    def __init__(
        self,
        metrics_retention_hours: int = 24,
        alert_thresholds: Optional[List[AlertThreshold]] = None,
    ):
        self.metrics_retention_hours = metrics_retention_hours
        self.metrics_store: Dict[str, deque] = defaultdict(deque)

        # Alert configurations
        self.alert_thresholds = alert_thresholds or [
            AlertThreshold("validation_failure_rate", 0.10, 60, 120),
            AlertThreshold("upload_failure_rate", 0.05, 60, 120),
            AlertThreshold("response_time_p95", 5000, 30, 60),
            AlertThreshold("broken_links_rate", 0.15, 120, 180),
        ]

        # Alert tracking
        self.last_alert_times: Dict[str, datetime] = {}
        self.alert_history: List[Dict[str, Any]] = []

        # Performance tracking
        self.performance_buckets = {
            "fast": (0, 1000),  # < 1s
            "normal": (1000, 3000),  # 1-3s
            "slow": (3000, 5000),  # 3-5s
            "very_slow": (5000, float("inf")),  # > 5s
        }

        # Thread safety
        self._lock = threading.Lock()

        # Background URL checking
        self.url_check_executor = ThreadPoolExecutor(
            max_workers=5, thread_name_prefix="url_checker"
        )
        self.broken_urls_cache = {}
        self._shutdown_lock = threading.Lock()
        self._is_shutdown = False

    def record_validation(
        self,
        url: str,
        success: bool,
        duration_ms: float,
        error_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Record a URL validation metric."""
        metric = URLMetric(
            timestamp=datetime.now(timezone.utc),
            operation_type="validation",
            success=success,
            duration_ms=duration_ms,
            url=url,
            error_type=error_type,
            correlation_id=correlation_id,
        )
        self._add_metric(metric)

    def record_upload(
        self,
        url: str,
        success: bool,
        duration_ms: float,
        metadata_size: int,
        error_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Record a URL metadata upload metric."""
        metric = URLMetric(
            timestamp=datetime.now(timezone.utc),
            operation_type="upload",
            success=success,
            duration_ms=duration_ms,
            url=url,
            metadata_size=metadata_size,
            error_type=error_type,
            correlation_id=correlation_id,
        )
        self._add_metric(metric)

    def record_retrieval(
        self,
        query: str,
        results_count: int,
        duration_ms: float,
        success: bool = True,
        correlation_id: Optional[str] = None,
    ):
        """Record a retrieval operation metric."""
        metric = URLMetric(
            timestamp=datetime.now(timezone.utc),
            operation_type="retrieval",
            success=success,
            duration_ms=duration_ms,
            query=query,
            results_count=results_count,
            correlation_id=correlation_id,
        )
        self._add_metric(metric)

    def _add_metric(self, metric: URLMetric) -> None:
        """Add a metric to the store."""
        with self._lock:
            self.metrics_store[metric.operation_type].append(metric)
        self._clean_old_metrics()

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the URL metadata monitor and release resources.

        Args:
            wait: If True, wait for all pending tasks to complete. If False, attempt to cancel them.
        """
        with self._shutdown_lock:
            if not self._is_shutdown:
                self.url_check_executor.shutdown(wait=wait)
                self._is_shutdown = True

    def __enter__(self):
        """Enable use as a context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure resources are cleaned up when exiting the context."""
        self.shutdown(wait=True)
        return False  # Don't suppress exceptions

    def _clean_old_metrics(self):
        """Remove metrics older than retention period."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(
            hours=self.metrics_retention_hours
        )

        with self._lock:
            for operation_type, metrics in self.metrics_store.items():
                # Remove old metrics from the left side of deque
                while metrics and metrics[0].timestamp < cutoff_time:
                    metrics.popleft()

    def _check_alerts(self):
        """Check all alert thresholds."""
        current_time = datetime.now(timezone.utc)

        for threshold in self.alert_thresholds:
            # Check cooldown
            last_alert = self.last_alert_times.get(threshold.name)
            if last_alert:
                cooldown_end = last_alert + timedelta(
                    minutes=threshold.cooldown_minutes
                )
                if current_time < cooldown_end:
                    continue

            # Calculate metric value
            metric_value = self._calculate_metric(
                threshold.name, threshold.window_minutes
            )

            # Check threshold
            if metric_value is not None and metric_value > threshold.threshold_value:
                self._trigger_alert(threshold, metric_value)

    def _calculate_metric(
        self, metric_name: str, window_minutes: int
    ) -> Optional[float]:
        """Calculate a specific metric value."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

        if metric_name == "validation_failure_rate":
            return self._calculate_failure_rate("validation", cutoff_time)
        elif metric_name == "upload_failure_rate":
            return self._calculate_failure_rate("upload", cutoff_time)
        elif metric_name == "response_time_p95":
            return self._calculate_response_time_percentile(95, cutoff_time)
        elif metric_name == "broken_links_rate":
            return self._calculate_broken_links_rate(cutoff_time)

        return None

    def _calculate_failure_rate(
        self, operation_type: str, cutoff_time: datetime
    ) -> Optional[float]:
        """Calculate failure rate for an operation type."""
        with self._lock:
            metrics = [
                m
                for m in self.metrics_store.get(operation_type, [])
                if m.timestamp >= cutoff_time
            ]

        if not metrics:
            return None

        failures = sum(1 for m in metrics if not m.success)
        return failures / len(metrics)

    def _calculate_response_time_percentile(
        self, percentile: int, cutoff_time: datetime
    ) -> Optional[float]:
        """Calculate response time percentile."""
        with self._lock:
            all_metrics = []
            for metrics in self.metrics_store.values():
                all_metrics.extend([m for m in metrics if m.timestamp >= cutoff_time])

        if not all_metrics:
            return None

        import math
        durations = [
            m.duration_ms
            for m in all_metrics
            if isinstance(m.duration_ms, (int, float)) and math.isfinite(m.duration_ms)
        ]
        if not durations:
            return None
        durations.sort()
        k = max(
            0,
            min(
                len(durations) - 1,
                int(round((percentile / 100) * (len(durations) - 1))),
            ),
        )
        return durations[k]
    def _calculate_broken_links_rate(self, cutoff_time: datetime) -> Optional[float]:
        """Calculate rate of broken links."""
        with self._lock:
            validation_metrics = [
                m
                for m in self.metrics_store.get("validation", [])
                if m.timestamp >= cutoff_time and m.url
            ]

        if not validation_metrics:
            return None

        broken_count = sum(
            1 for m in validation_metrics if m.error_type == "broken_link"
        )
        return broken_count / len(validation_metrics)

    def _trigger_alert(self, threshold: AlertThreshold, metric_value: float):
        """Trigger an alert and record it."""
        alert_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alert_name": threshold.name,
            "threshold_value": threshold.threshold_value,
            "actual_value": metric_value,
            "window_minutes": threshold.window_minutes,
        }

        with self._lock:
            self.last_alert_times[threshold.name] = datetime.now(timezone.utc)
            self.alert_history.append(alert_data)

        # Here you would integrate with your alerting system
        logger.warning(f"Alert triggered: {threshold.name}", extra=alert_data)
        # TODO: Integrate with alerting system (e.g., send to monitoring service)

    def check_url_accessibility(self, url: str) -> Tuple[bool, Optional[str]]:
        """Check if a URL is accessible."""
        # Check cache first
        if url in self.broken_urls_cache:
            is_accessible, check_time = self.broken_urls_cache[url]
            if datetime.now(timezone.utc) - check_time < timedelta(hours=1):
                return is_accessible, None

        try:
            headers = {"User-Agent": "URLMetadataMonitor/1.0"}
            # Try HEAD first, fall back to GET if needed
            try:
                response = requests.head(
                    url, timeout=5, allow_redirects=True, headers=headers
                )
            except requests.RequestException:
                # Some servers don't support HEAD, try GET with streaming
                response = requests.get(
                    url, timeout=5, allow_redirects=True, headers=headers, stream=True
                )
                response.close()  # Don't download the body
            is_accessible = response.status_code < 400
            error = None if is_accessible else f"HTTP {response.status_code}"
        except requests.RequestException as e:
            is_accessible = False
            error = str(e)

        # Cache the result
        self.broken_urls_cache[url] = (is_accessible, datetime.now(timezone.utc))

        # Record as broken link if not accessible
        if not is_accessible:
            self.record_validation(url, False, 0, error_type="broken_link")

        return is_accessible, error

    def generate_hourly_summary(self) -> Dict[str, Any]:
        """Generate hourly metrics summary."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "period": "hourly",
            "operations": {},
        }

        with self._lock:
            for op_type, metrics in self.metrics_store.items():
                recent_metrics = [m for m in metrics if m.timestamp >= cutoff_time]

                if recent_metrics:
                    summary["operations"][op_type] = self._calculate_operation_stats(
                        recent_metrics
                    )

        # Add performance distribution
        summary["performance_distribution"] = self._calculate_performance_distribution(
            cutoff_time
        )

        # Add recent alerts with error handling for malformed timestamps
        recent_alerts = []
        for alert in self.alert_history:
            try:
                alert_time = datetime.fromisoformat(alert["timestamp"])
                if alert_time >= cutoff_time:
                    recent_alerts.append(alert)
            except (ValueError, TypeError, KeyError) as e:
                # Log warning for malformed timestamps but continue processing
                import logging

                logging.warning(
                    f"Skipping alert due to invalid timestamp format: "
                    f"{alert.get('timestamp')}. Error: {str(e)}"
                )
                continue

        summary["recent_alerts"] = recent_alerts

        return summary

    def generate_daily_summary(self) -> Dict[str, Any]:
        """Generate daily metrics summary."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=1)

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "period": "daily",
            "operations": {},
            "top_errors": {},
            "slowest_operations": [],
        }

        with self._lock:
            all_metrics = []
            for op_type, metrics in self.metrics_store.items():
                recent_metrics = [m for m in metrics if m.timestamp >= cutoff_time]
                all_metrics.extend(recent_metrics)

                if recent_metrics:
                    summary["operations"][op_type] = self._calculate_operation_stats(
                        recent_metrics
                    )

                    # Collect top errors
                    error_counts = defaultdict(int)
                    for m in recent_metrics:
                        if not m.success and m.error_type:
                            error_counts[m.error_type] += 1

                    if error_counts:
                        summary["top_errors"][op_type] = sorted(
                            error_counts.items(), key=lambda x: x[1], reverse=True
                        )[:5]

        # Find slowest operations
        all_metrics.sort(key=lambda m: m.duration_ms, reverse=True)
        summary["slowest_operations"] = [
            {
                "operation": m.operation_type,
                "url": m.url,
                "duration_ms": m.duration_ms,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in all_metrics[:10]
        ]

        # Add performance trends
        summary["performance_trends"] = self._calculate_performance_trends()

        return summary

    def _calculate_operation_stats(self, metrics: List[URLMetric]) -> Dict[str, Any]:
        """Calculate statistics for a set of metrics."""
        total = len(metrics)
        successes = sum(1 for m in metrics if m.success)
        failures = total - successes
# at the top of the file
import statistics, math
...

            # only keep finite numbers
            valid_durations = [
                d for d in durations
                if isinstance(d, (int, float)) and math.isfinite(d)
            ]

            if valid_durations:
                # Safe percentile helper avoids StatisticsError on small samples
                def _pct(seq, p):
                    if not seq:
                        return 0.0
                    seq = sorted(seq)
                    idx = int(round(p / 100 * (len(seq) - 1)))
                    return seq[idx]

                stats.update(
                    {
                        "avg_duration_ms": statistics.mean(valid_durations),
                        "min_duration_ms": min(valid_durations),
                        "max_duration_ms": max(valid_durations),
                        "p50_duration_ms": statistics.median(valid_durations),
                        "p95_duration_ms": _pct(valid_durations, 95),
                        "p99_duration_ms": _pct(valid_durations, 99),
                    }
                )
                            statistics.quantiles(valid_durations, n=20)[18]
                            if len(valid_durations) > 1
                            else valid_durations[0]
                        ),
                        "p99_duration_ms": (
                            statistics.quantiles(valid_durations, n=100)[98]
                            if len(valid_durations) > 1
                            else valid_durations[0]
                        ),
                    }
                )

        return stats

    def _calculate_performance_distribution(
        self, cutoff_time: datetime
    ) -> Dict[str, int]:
        """Calculate performance distribution across buckets."""
        distribution = {name: 0 for name in self.performance_buckets}

        with self._lock:
            for metrics in self.metrics_store.values():
                for m in metrics:
                    if m.timestamp >= cutoff_time and isinstance(m.duration_ms, (int, float)) and not (isinstance(m.duration_ms, float) and (m.duration_ms != m.duration_ms or m.duration_ms == float('inf') or m.duration_ms == float('-inf'))):
                        for name, (min_ms, max_ms) in self.performance_buckets.items():
                            if min_ms <= m.duration_ms < max_ms:
                                distribution[name] += 1
                                break

        return distribution

    def _calculate_performance_trends(self) -> Dict[str, List[Dict[str, Any]]]:
        """Calculate hourly performance trends for the past 24 hours."""
        trends = defaultdict(list)
        now = datetime.now(timezone.utc)

        for hour in range(24):
            hour_start = now - timedelta(hours=hour + 1)
            hour_end = now - timedelta(hours=hour)

            with self._lock:
                for op_type, metrics in self.metrics_store.items():
                    hour_metrics = [
                        m for m in metrics if hour_start <= m.timestamp < hour_end
                    ]

                    if hour_metrics:
                        durations = [m.duration_ms for m in hour_metrics]
                        trends[op_type].append(
                            {
                                "hour": hour_end.isoformat(),
                                "avg_duration_ms": statistics.mean(durations),
                                "success_rate": sum(
                                    1 for m in hour_metrics if m.success
                                )
                                / len(hour_metrics),
                            }
                        )

        return dict(trends)

    def export_metrics(self, filepath: Path, hours: Optional[int] = None) -> None:
        """Export metrics to a JSON file."""
        if hours:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        else:
            cutoff_time = datetime.min.replace(tzinfo=timezone.utc)

        export_data = {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {},
        }

        with self._lock:
            for op_type, metrics in self.metrics_store.items():
                export_data["metrics"][op_type] = [
                    asdict(m) for m in metrics if m.timestamp >= cutoff_time
                ]

        # Convert datetime objects to strings
        for op_type in export_data["metrics"]:
            for metric in export_data["metrics"][op_type]:
                metric["timestamp"] = metric["timestamp"].isoformat()

        try:
            # Ensure parent directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file first, then rename for atomicity
            temp_path = filepath.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(export_data, f, indent=2)
            temp_path.replace(filepath)
        except (IOError, OSError) as e:
            logger.error(f"Failed to export metrics to {filepath}: {e}")
            raise


# Global monitor instance
url_metadata_monitor = URLMetadataMonitor()


# Convenience functions
def record_validation(url: str, success: bool, duration_ms: float, **kwargs):
    """Record a validation metric."""
    url_metadata_monitor.record_validation(url, success, duration_ms, **kwargs)


def record_upload(
    url: str, success: bool, duration_ms: float, metadata_size: int, **kwargs
):
    """Record an upload metric."""
    url_metadata_monitor.record_upload(
        url, success, duration_ms, metadata_size, **kwargs
    )


def record_retrieval(
    query: str, results_count: int, duration_ms: float, success: bool = True, **kwargs
):
    """Record a retrieval metric."""
    url_metadata_monitor.record_retrieval(
        query, results_count, duration_ms, success, **kwargs
    )


def check_url_accessibility(url: str) -> Tuple[bool, Optional[str]]:
    """Check URL accessibility."""
    return url_metadata_monitor.check_url_accessibility(url)


def generate_hourly_summary() -> Dict[str, Any]:
    """Generate hourly summary."""
    return url_metadata_monitor.generate_hourly_summary()


def generate_daily_summary() -> Dict[str, Any]:
    """Generate daily summary."""
    return url_metadata_monitor.generate_daily_summary()
