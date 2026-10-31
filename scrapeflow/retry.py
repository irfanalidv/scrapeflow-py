"""Retry logic and error recovery utilities."""

import asyncio
import inspect
import logging
import random
from collections.abc import Callable
from typing import Any

from scrapeflow.config import RetryConfig
from scrapeflow.exceptions import (
    ScrapeFlowBlockedError,
    ScrapeFlowRetryError,
    ScrapeFlowTimeoutError,
)

logger = logging.getLogger(__name__)


class RetryHandler:
    """Handles retry logic with exponential backoff and jitter."""

    def __init__(self, config: RetryConfig) -> None:
        self.config = config

    def _add_jitter(self, delay: float) -> float:
        """Add random jitter to delay."""
        if self.config.jitter:
            jitter = delay * 0.1 * random.random()
            return delay + jitter
        return delay

    async def execute_with_retry(
        self,
        func: Callable[..., Any],
        *args: Any,
        retryable_exceptions: tuple[type[BaseException], ...] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Call ``func`` (sync or async), retrying on ``retryable_exceptions``.

        Delays grow as ``initial_delay * exponential_base ** attempt``, capped at ``max_delay``,
        plus up to 10% jitter when enabled. Non-retryable exceptions propagate unchanged.

        Raises:
            ScrapeFlowRetryError: the call still failed after ``max_retries`` retries. The last
                underlying exception is chained as ``__cause__``.
        """
        retryable = retryable_exceptions or self.config.retryable_exceptions
        max_retries = self.config.max_retries
        name = getattr(func, "__name__", repr(func))

        for attempt in range(max_retries + 1):
            try:
                result = func(*args, **kwargs)
                if inspect.isawaitable(result):
                    result = await result
                return result
            except retryable as e:
                if attempt == max_retries:
                    logger.error("Max retries (%d) exceeded for %s", max_retries, name)
                    raise ScrapeFlowRetryError(
                        f"Operation failed after {max_retries} retries: {e!s}",
                        retry_count=attempt,
                        max_retries=max_retries,
                    ) from e

                delay = min(
                    self.config.initial_delay * (self.config.exponential_base**attempt),
                    self.config.max_delay,
                )
                delay = self._add_jitter(delay)
                logger.warning(
                    "Attempt %d/%d failed for %s: %s. Retrying in %.2fs...",
                    attempt + 1,
                    max_retries + 1,
                    name,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)

        # Unreachable: the loop either returns or raises on the last attempt.
        raise AssertionError("unreachable")  # pragma: no cover


class ErrorClassifier:
    """Classifies errors to determine retry strategy."""

    @staticmethod
    def is_retryable(error: Exception) -> bool:
        """Determine if an error is retryable."""
        # Network errors
        if isinstance(error, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
            return True

        # HTTP errors that might be temporary
        # 429 (Too Many Requests), 500, 502, 503, 504 are retryable
        if getattr(error, "status_code", None) in (429, 500, 502, 503, 504):
            return True

        # ScrapeFlow specific errors
        if isinstance(error, ScrapeFlowRetryError):
            return True

        if isinstance(error, ScrapeFlowTimeoutError):
            return True

        # Blocked errors might be retryable after a delay
        return isinstance(error, ScrapeFlowBlockedError)

    @staticmethod
    def get_retry_delay(error: Exception) -> float | None:
        """Get suggested retry delay for an error."""
        if isinstance(error, ScrapeFlowBlockedError):
            return error.retry_after

        if getattr(error, "status_code", None) == 429:
            headers = getattr(error, "headers", None) or {}
            retry_after = headers.get("Retry-After") if hasattr(headers, "get") else None
            if retry_after is not None:
                try:
                    return float(retry_after)
                except (TypeError, ValueError):
                    # Retry-After may also be an HTTP date; we do not parse that form.
                    return None

        return None
