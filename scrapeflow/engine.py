"""Main ScrapeFlow engine that orchestrates all components."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from playwright.async_api import Page

from scrapeflow.anti_detection import AntiDetectionManager
from scrapeflow.browser_runtime import PlaywrightBrowserRuntime
from scrapeflow.config import ScrapeFlowConfig
from scrapeflow.exceptions import (
    ScrapeFlowBlockedError,
    ScrapeFlowNotStartedError,
    ScrapeFlowRobotsDisallowedError,
    ScrapeFlowTimeoutError,
)
from scrapeflow.monitoring import Logger, PerformanceMonitor, ScrapeMetrics
from scrapeflow.ports import (
    BrowserRuntimePort,
    LoggerPort,
    MonitorPort,
    RateLimiterPort,
    RetryHandlerPort,
    RobotsCheckerPort,
)
from scrapeflow.rate_limiter import RateLimiter
from scrapeflow.registry import LoginHandler
from scrapeflow.retry import RetryHandler
from scrapeflow.robots import RobotsChecker
from scrapeflow.workflow import Step, Workflow, WorkflowResult
from scrapeflow.workflow_executor import WorkflowExecutor

#: Transient errors that make a ``retryable`` workflow step worth running again.
#: ``ScrapeFlowRetryError`` is deliberately absent: it means an inner operation (such as
#: ``navigate``) already used up its own retries, and retrying again would multiply attempts.
_RETRYABLE_STEP_ERRORS: tuple[type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
    ScrapeFlowTimeoutError,
    ScrapeFlowBlockedError,
)


class ScrapeFlow:
    """Main ScrapeFlow engine for web scraping workflows.

    Every collaborator (rate limiter, retry handler, logger, monitor, robots checker, browser
    runtime, workflow executor) can be injected; anything not supplied gets the default
    implementation built from ``config``.
    """

    def __init__(
        self,
        config: ScrapeFlowConfig | None = None,
        *,
        rate_limiter: RateLimiterPort | None = None,
        retry_handler: RetryHandlerPort | None = None,
        logger: LoggerPort | None = None,
        monitor: MonitorPort | None = None,
        robots_checker: RobotsCheckerPort | None = None,
        runtime: BrowserRuntimePort | None = None,
        workflow_executor: WorkflowExecutor | None = None,
    ) -> None:
        self.config = config or ScrapeFlowConfig()
        self.page: Page | None = None

        # Initialize components
        self.anti_detection = AntiDetectionManager(self.config.anti_detection)
        self.rate_limiter: RateLimiterPort = rate_limiter or RateLimiter(self.config.rate_limit)
        self.retry_handler: RetryHandlerPort = retry_handler or RetryHandler(self.config.retry)
        self.logger: LoggerPort = logger or Logger(
            name="scrapeflow", level=self.config.log_level, log_file=self.config.log_file
        )
        self.monitor: MonitorPort = monitor or PerformanceMonitor()
        self.robots_checker: RobotsCheckerPort = robots_checker or RobotsChecker(
            user_agent=self.config.ethical_crawling.user_agent_for_robots,
            respect_robots=self.config.ethical_crawling.respect_robots_txt,
        )
        self.runtime: BrowserRuntimePort = runtime or PlaywrightBrowserRuntime(
            self.config, self.anti_detection
        )
        self.workflow_executor = workflow_executor or WorkflowExecutor()

        self._is_running = False

    async def __aenter__(self) -> ScrapeFlow:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def _require_page(self) -> Page:
        """Return the active page, or raise a clear error if the engine is not running."""
        if not self._is_running or self.page is None:
            raise ScrapeFlowNotStartedError("Engine not started. Call start() first.")
        return self.page

    def _timeout_ms(self, timeout: int | None) -> int:
        """Resolve a per-call timeout. ``0`` is passed through (Playwright: no timeout)."""
        return self.config.browser.timeout if timeout is None else timeout

    async def start(self) -> None:
        """Start the browser and initialize resources."""
        if self._is_running:
            return

        self.logger.info("Starting ScrapeFlow engine...")
        await self.runtime.start()
        self.page = self.runtime.page

        self._is_running = True
        self.logger.info("ScrapeFlow engine started successfully")

    async def close(self) -> None:
        """Close browser and cleanup resources."""
        if not self._is_running:
            return

        self.logger.info("Closing ScrapeFlow engine...")
        await self.runtime.close()
        self.page = None

        self._is_running = False
        self.logger.info("ScrapeFlow engine closed")

    async def navigate(
        self, url: str, wait_until: str = "load", timeout: int | None = None
    ) -> None:
        """Navigate to a URL with robots.txt check, rate limiting and retry logic.

        Raises:
            ScrapeFlowRobotsDisallowedError: robots.txt disallows ``url`` (checked first,
                before any request to the page itself).
            ScrapeFlowRetryError: navigation still failed after all retries.
        """
        if not self._is_running:
            await self.start()

        # Check robots.txt before navigating
        if not await self.robots_checker.can_fetch(url):
            self.logger.warning(f"robots.txt disallows: {url}")
            raise ScrapeFlowRobotsDisallowedError(f"robots.txt disallows fetching: {url}")

        start_time = self.monitor.start_request()
        timeout_ms = self._timeout_ms(timeout)

        async def _navigate() -> None:
            await self.rate_limiter.acquire()
            await self.runtime.goto(url, wait_until=wait_until, timeout=timeout_ms)
            self.page = self.runtime.page

        try:
            await self.retry_handler.execute_with_retry(
                _navigate,
                retryable_exceptions=(Exception,),  # Most navigation errors are retryable
            )
            self.monitor.end_request(start_time, success=True)
            self.logger.info(f"Successfully navigated to {url}")
        except Exception as e:
            self.monitor.end_request(start_time, success=False, error=e)
            self.logger.error(f"Failed to navigate to {url}: {e!s}")
            raise

    async def click(self, selector: str, timeout: int | None = None) -> None:
        """Click an element with retry logic."""
        page = self._require_page()
        timeout_ms = self._timeout_ms(timeout)

        async def _click() -> None:
            await page.click(selector, timeout=timeout_ms)

        await self.retry_handler.execute_with_retry(_click)

    async def fill(self, selector: str, value: str, timeout: int | None = None) -> None:
        """Fill an input field with retry logic."""
        page = self._require_page()
        timeout_ms = self._timeout_ms(timeout)

        async def _fill() -> None:
            await page.fill(selector, value, timeout=timeout_ms)

        await self.retry_handler.execute_with_retry(_fill)

    async def login(
        self,
        login_url: str,
        username: str,
        password: str,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
        success_selector: str | None = None,
        timeout: int | None = None,
    ) -> bool:
        """
        Perform a reusable login flow.

        Returns True when login succeeds. If `success_selector` is provided,
        success is verified by waiting for that selector.
        """
        if not self._is_running:
            await self.start()

        await self.navigate(login_url, timeout=timeout)
        await self.fill(username_selector, username, timeout=timeout)
        await self.fill(password_selector, password, timeout=timeout)
        await self.click(submit_selector, timeout=timeout)

        if success_selector:
            try:
                await self.wait_for_selector(success_selector, timeout=timeout)
            except Exception as exc:
                self.logger.warning(
                    f"Login check failed: {success_selector!r} did not appear ({exc!s})"
                )
                return False
        return True

    async def login_with_handler(
        self,
        login_url: str,
        username: str,
        password: str,
        handler: LoginHandler,
        timeout: int | None = None,
    ) -> bool:
        """
        Perform login using a reusable LoginHandler component.
        """
        return await self.login(
            login_url=login_url,
            username=username,
            password=password,
            username_selector=handler.username_selector,
            password_selector=handler.password_selector,
            submit_selector=handler.submit_selector,
            success_selector=handler.success_selector,
            timeout=timeout,
        )

    async def wait_for_selector(
        self, selector: str, timeout: int | None = None, state: str = "visible"
    ) -> None:
        """Wait for a selector to reach ``state`` (default ``"visible"``)."""
        page = self._require_page()
        await page.wait_for_selector(
            selector,
            timeout=self._timeout_ms(timeout),
            state=state,  # type: ignore[arg-type]
        )

    async def screenshot(self, path: str, full_page: bool = False) -> None:
        """Take a screenshot."""
        page = self._require_page()
        await page.screenshot(path=path, full_page=full_page)

    async def save_storage_state(self, path: str) -> None:
        """Save cookies and local storage; load them later with ``storage_state_path``."""
        self._require_page()
        save = getattr(self.runtime, "save_storage_state", None)
        if save is None:
            raise ScrapeFlowNotStartedError(
                f"{type(self.runtime).__name__} does not support save_storage_state()"
            )
        await save(path)

    async def _run_step_once(self, step: Step, context: dict[str, Any]) -> Any:
        kwargs = {**step.kwargs, "context": context, "page": self.page}
        call = self._execute_function(step.func, *step.args, **kwargs)
        if not step.timeout:
            return await call
        try:
            return await asyncio.wait_for(call, timeout=step.timeout)
        except asyncio.TimeoutError as exc:
            raise ScrapeFlowTimeoutError(
                f"Step '{step.name}' timed out after {step.timeout}s"
            ) from exc

    async def execute_step(self, step: Step, context: dict[str, Any]) -> Any:
        """Execute a workflow step with timeout, metrics and optional retries.

        A step with ``retryable=True`` is re-run through the engine's retry handler when it
        fails with a transient error (connection errors, timeouts, ``ScrapeFlowBlockedError``);
        once retries run out the handler raises ``ScrapeFlowRetryError``. Any other exception
        propagates immediately.
        """
        start_time = self.monitor.start_request()
        attempts = 0

        async def _attempt() -> Any:
            nonlocal attempts
            if attempts:
                self.monitor.record_retry()
            attempts += 1
            return await self._run_step_once(step, context)

        try:
            if step.retryable:
                result = await self.retry_handler.execute_with_retry(
                    _attempt, retryable_exceptions=_RETRYABLE_STEP_ERRORS
                )
            else:
                result = await _attempt()
        except Exception as e:
            self.monitor.end_request(start_time, success=False, error=e)
            raise
        self.monitor.end_request(start_time, success=True)
        return result

    async def _execute_function(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Call ``func`` and await the result if it is awaitable (sync and async both work)."""
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _safe_call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Call a user callback, logging (not raising) any error it throws."""
        try:
            await self._execute_function(func, *args, **kwargs)
        except Exception as e:
            self.logger.warning(f"Callback function failed: {e!s}")

    async def run_workflow(self, workflow: Workflow) -> WorkflowResult:
        """Run a complete workflow."""
        if not self._is_running:
            await self.start()

        self.logger.info(f"Starting workflow: {workflow.name}")
        result = await self.workflow_executor.execute(workflow, self)
        self.logger.info(
            f"Workflow '{workflow.name}' completed. "
            f"Success: {result.success}, Steps: {len(result.steps_completed)}/{len(workflow.steps)}"
        )
        return result

    def get_metrics(self) -> ScrapeMetrics:
        """Get current performance metrics."""
        metrics: ScrapeMetrics = self.monitor.get_metrics()
        return metrics

    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self.monitor.reset()
