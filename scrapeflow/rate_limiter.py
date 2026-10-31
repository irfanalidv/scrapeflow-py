"""Rate limiting utilities for controlling request frequency."""

import asyncio
import time

from scrapeflow.config import RateLimitConfig


def effective_rate(config: RateLimitConfig) -> float:
    """Return the requests-per-second rate implied by ``config``.

    When both ``requests_per_second`` and ``requests_per_minute`` are set, the slower (more
    polite) of the two wins. With neither set, the default is 1 request per second.
    """
    rates = []
    if config.requests_per_second:
        rates.append(float(config.requests_per_second))
    if config.requests_per_minute:
        rates.append(config.requests_per_minute / 60.0)
    return min(rates) if rates else 1.0


class RateLimiter:
    """Token bucket rate limiter for controlling request rate.

    The bucket holds up to ``burst_size`` tokens and refills at :func:`effective_rate` tokens
    per second. Each :meth:`acquire` takes one token, sleeping when the bucket is empty.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config
        self.tokens: float = config.burst_size
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
        # Seconds between tokens.
        self.refill_rate = 1.0 / effective_rate(config)
        self.max_tokens = config.burst_size

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(self.max_tokens, self.tokens + elapsed / self.refill_rate)
            self.last_update = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) * self.refill_rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
                self.last_update = time.monotonic()
            else:
                self.tokens -= 1


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that slows down on :meth:`backoff` and recovers on :meth:`speed_up`."""

    def __init__(self, config: RateLimitConfig) -> None:
        super().__init__(config)
        self.backoff_factor = 1.5
        self.min_rate = 0.1  # Minimum 1 request per 10 seconds
        self.current_rate = effective_rate(config)

    def backoff(self) -> None:
        """Increase wait time when rate limited."""
        self.current_rate = max(self.min_rate, self.current_rate / self.backoff_factor)
        self.refill_rate = 1.0 / self.current_rate

    def speed_up(self) -> None:
        """Gradually increase rate when successful, never above the configured rate."""
        original_rate = effective_rate(self.config)
        if self.current_rate < original_rate:
            self.current_rate = min(original_rate, self.current_rate * 1.1)
            self.refill_rate = 1.0 / self.current_rate
