"""Retry logic and error recovery utilities."""

import asyncio
import random
import logging
from typing import Callable, Any, Optional, Type, Tuple
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    Retrying,
    RetryError,
)
from scrapeflow.config import RetryConfig
from scrapeflow.exceptions import (
    ScrapeFlowRetryError,
    ScrapeFlowBlockedError,
    ScrapeFlowTimeoutError,
)

logger = logging.getLogger(__name__)


class RetryHandler:
    """Handles retry logic with exponential backoff and jitter."""

    def __init__(self, config: RetryConfig):
        self.config = config

    def _add_jitter(self, delay: float) -> float:
        """Add random jitter to delay."""
        if self.config.jitter:
            jitter = delay * 0.1 * random.random()
            return delay + jitter
        return delay

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        **kwargs,
    ) -> Any:
        """Execute a function with retry logic."""
        retryable = retryable_exceptions or self.config.retryable_exceptions
        max_retries = self.config.max_retries
        delay = self.config.initial_delay

        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except retryable as e:
                if attempt == max_retries:
                    logger.error(
                        f"Max retries ({max_retries}) exceeded for {func.__name__}"
                    )
                    raise ScrapeFlowRetryError(
                        f"Operation failed after {max_retries} retries: {str(e)}",
                        retry_count=attempt,
                        max_retries=max_retries,
                    ) from e

                # Calculate delay with exponential backoff
                delay = min(
                    self.config.initial_delay
                    * (self.config.exponential_base ** attempt),
                    self.config.max_delay,
                )
                delay = self._add_jitter(delay)

                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {str(e)}. "
                    f"Retrying in {delay:.2f}s..."
                )

                await asyncio.sleep(delay)

        # Should never reach here, but just in case
        raise ScrapeFlowRetryError(
            f"Operation failed after {max_retries} retries",
            retry_count=max_retries,
            max_retries=max_retries,
        )


class ErrorClassifier:
    """Classifies errors to determine retry strategy."""

    @staticmethod
    def is_retryable(error: Exception) -> bool:
        """Determine if an error is retryable."""
        # Network errors
        if isinstance(error, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
            return True

        # HTTP errors that might be temporary
        if hasattr(error, "status_code"):
            status = error.status_code
            # 429 (Too Many Requests), 500, 502, 503, 504 are retryable
            if status in (429, 500, 502, 503, 504):
                return True

        # ScrapeFlow specific errors
        if isinstance(error, ScrapeFlowRetryError):
            return True

        if isinstance(error, ScrapeFlowTimeoutError):
            return True

        # Blocked errors might be retryable after a delay
        if isinstance(error, ScrapeFlowBlockedError):
            return True

        return False

    @staticmethod
    def get_retry_delay(error: Exception) -> Optional[float]:
        """Get suggested retry delay for an error."""
        if isinstance(error, ScrapeFlowBlockedError):
            return error.retry_after

        if hasattr(error, "status_code") and error.status_code == 429:
            # Check for Retry-After header
            if hasattr(error, "headers") and "Retry-After" in error.headers:
                return float(error.headers["Retry-After"])

        return None

