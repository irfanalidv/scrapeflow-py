"""Monitoring, logging, and metrics for ScrapeFlow."""

import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime


@dataclass
class ScrapeMetrics:
    """Metrics for scraping operations."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retry_count: int = 0
    total_duration: float = 0.0
    average_response_time: float = 0.0
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def record_success(self, duration: float):
        """Record a successful request."""
        self.total_requests += 1
        self.successful_requests += 1
        self.total_duration += duration
        self._update_average()

    def record_failure(self, duration: float, error: Exception):
        """Record a failed request."""
        self.total_requests += 1
        self.failed_requests += 1
        self.total_duration += duration
        error_type = type(error).__name__
        self.errors_by_type[error_type] += 1
        self._update_average()

    def record_retry(self):
        """Record a retry."""
        self.retry_count += 1

    def _update_average(self):
        """Update average response time."""
        if self.total_requests > 0:
            self.average_response_time = self.total_duration / self.total_requests

    def get_success_rate(self) -> float:
        """Get success rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "retry_count": self.retry_count,
            "total_duration": self.total_duration,
            "average_response_time": self.average_response_time,
            "success_rate": self.get_success_rate(),
            "errors_by_type": dict(self.errors_by_type),
        }


class Logger:
    """Centralized logging for ScrapeFlow."""

    def __init__(
        self,
        name: str = "scrapeflow",
        level: str = "INFO",
        log_file: Optional[str] = None,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))

        # Remove existing handlers
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper()))
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(getattr(logging, level.upper()))
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        self.logger.exception(message, **kwargs)


class PerformanceMonitor:
    """Monitors performance of scraping operations."""

    def __init__(self):
        self.metrics = ScrapeMetrics()
        self.metrics.start_time = time.time()

    def start_request(self):
        """Mark the start of a request."""
        return time.time()

    def end_request(self, start_time: float, success: bool, error: Optional[Exception] = None):
        """Mark the end of a request and record metrics."""
        duration = time.time() - start_time
        if success:
            self.metrics.record_success(duration)
        else:
            self.metrics.record_failure(duration, error)

    def record_retry(self):
        """Record a retry."""
        self.metrics.record_retry()

    def get_metrics(self) -> ScrapeMetrics:
        """Get current metrics."""
        self.metrics.end_time = time.time()
        return self.metrics

    def reset(self):
        """Reset metrics."""
        self.metrics = ScrapeMetrics()
        self.metrics.start_time = time.time()

