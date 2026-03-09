"""Architecture seam tests for engine orchestration."""

import pytest

from scrapeflow.engine import ScrapeFlow
from scrapeflow.exceptions import ScrapeFlowRobotsDisallowedError


class FakeRuntime:
    def __init__(self):
        self.page = object()
        self.started = False
        self.closed = False
        self.goto_calls = 0
        self.last_goto = None

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.goto_calls += 1
        self.last_goto = (url, wait_until, timeout)


class FakeRateLimiter:
    def __init__(self):
        self.acquire_calls = 0

    async def acquire(self) -> None:
        self.acquire_calls += 1


class FakeRetryHandler:
    async def execute_with_retry(self, func, retryable_exceptions=None):
        return await func()


class FakeLogger:
    def debug(self, message: str, **kwargs):
        pass

    def info(self, message: str, **kwargs):
        pass

    def warning(self, message: str, **kwargs):
        pass

    def error(self, message: str, **kwargs):
        pass


class FakeMonitor:
    def __init__(self):
        self.success = 0
        self.failure = 0

    def start_request(self) -> float:
        return 0.0

    def end_request(self, start_time: float, success: bool, error=None) -> None:
        if success:
            self.success += 1
        else:
            self.failure += 1

    def record_retry(self) -> None:
        pass

    def get_metrics(self):
        return {"success": self.success, "failure": self.failure}

    def reset(self):
        self.success = 0
        self.failure = 0


class FakeRobotsChecker:
    def __init__(self, allowed: bool):
        self.allowed = allowed

    async def can_fetch(self, url: str) -> bool:
        return self.allowed


@pytest.mark.asyncio
async def test_navigate_blocks_when_robots_disallow():
    runtime = FakeRuntime()
    scraper = ScrapeFlow(
        runtime=runtime,
        rate_limiter=FakeRateLimiter(),
        retry_handler=FakeRetryHandler(),
        logger=FakeLogger(),
        monitor=FakeMonitor(),
        robots_checker=FakeRobotsChecker(allowed=False),
    )

    with pytest.raises(ScrapeFlowRobotsDisallowedError):
        await scraper.navigate("https://example.com")
    assert runtime.goto_calls == 0


@pytest.mark.asyncio
async def test_navigate_uses_injected_components():
    runtime = FakeRuntime()
    limiter = FakeRateLimiter()
    monitor = FakeMonitor()
    scraper = ScrapeFlow(
        runtime=runtime,
        rate_limiter=limiter,
        retry_handler=FakeRetryHandler(),
        logger=FakeLogger(),
        monitor=monitor,
        robots_checker=FakeRobotsChecker(allowed=True),
    )

    await scraper.navigate("https://example.com/path")

    assert runtime.started is True
    assert limiter.acquire_calls == 1
    assert runtime.goto_calls == 1
    assert runtime.last_goto[0] == "https://example.com/path"
    assert monitor.success == 1
