"""Rate limiting utilities for controlling request frequency."""

import asyncio
import time
from typing import Optional
from collections import deque
from scrapeflow.config import RateLimitConfig


class RateLimiter:
    """Token bucket rate limiter for controlling request rate."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.burst_size
        self.last_update = time.time()
        self._lock = asyncio.Lock()

        # Calculate token refill rate
        if config.requests_per_second:
            self.refill_rate = 1.0 / config.requests_per_second
        elif config.requests_per_minute:
            self.refill_rate = 60.0 / config.requests_per_minute
        else:
            self.refill_rate = 1.0  # Default: 1 request per second

        self.max_tokens = config.burst_size

    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            tokens_to_add = elapsed / self.refill_rate
            self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
            self.last_update = now

            # If no tokens available, wait
            if self.tokens < 1:
                wait_time = self.refill_rate - (self.tokens * self.refill_rate)
                await asyncio.sleep(wait_time)
                self.tokens = 0
                self.last_update = time.time()
            else:
                self.tokens -= 1


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts based on detected rate limits."""

    def __init__(self, config: RateLimitConfig):
        super().__init__(config)
        self.backoff_factor = 1.5
        self.min_rate = 0.1  # Minimum 1 request per 10 seconds
        self.current_rate = config.requests_per_second or (
            60.0 / config.requests_per_minute if config.requests_per_minute else 1.0
        )

    def backoff(self):
        """Increase wait time when rate limited."""
        self.current_rate = max(
            self.min_rate, self.current_rate / self.backoff_factor
        )
        self.refill_rate = 1.0 / self.current_rate

    def speed_up(self):
        """Gradually increase rate when successful."""
        original_rate = (
            self.config.requests_per_second
            or (60.0 / self.config.requests_per_minute if self.config.requests_per_minute else 1.0)
        )
        if self.current_rate < original_rate:
            self.current_rate = min(original_rate, self.current_rate * 1.1)
            self.refill_rate = 1.0 / self.current_rate

