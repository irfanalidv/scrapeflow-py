"""Architecture ports (protocols) for dependency inversion."""

from typing import Any, Awaitable, Callable, Optional, Protocol
from playwright.async_api import Page


class RateLimiterPort(Protocol):
    async def acquire(self) -> None:
        ...


class RetryHandlerPort(Protocol):
    async def execute_with_retry(
        self,
        func: Callable[[], Awaitable[Any]],
        retryable_exceptions: Optional[tuple[type[Exception], ...]] = None,
    ) -> Any:
        ...


class MonitorPort(Protocol):
    def start_request(self) -> float:
        ...

    def end_request(
        self, start_time: float, success: bool, error: Optional[Exception] = None
    ) -> None:
        ...

    def record_retry(self) -> None:
        ...

    def get_metrics(self) -> Any:
        ...

    def reset(self) -> None:
        ...


class LoggerPort(Protocol):
    def debug(self, message: str, **kwargs: Any) -> None:
        ...

    def info(self, message: str, **kwargs: Any) -> None:
        ...

    def warning(self, message: str, **kwargs: Any) -> None:
        ...

    def error(self, message: str, **kwargs: Any) -> None:
        ...


class RobotsCheckerPort(Protocol):
    async def can_fetch(self, url: str) -> bool:
        ...


class BrowserRuntimePort(Protocol):
    @property
    def page(self) -> Optional[Page]:
        ...

    async def start(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        ...
