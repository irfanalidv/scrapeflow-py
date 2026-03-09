"""Main ScrapeFlow engine that orchestrates all components."""

import asyncio
from typing import Optional, Dict, Any, Callable
from playwright.async_api import Page

from scrapeflow.config import ScrapeFlowConfig
from scrapeflow.anti_detection import AntiDetectionManager
from scrapeflow.rate_limiter import RateLimiter
from scrapeflow.retry import RetryHandler, ErrorClassifier
from scrapeflow.monitoring import Logger, PerformanceMonitor
from scrapeflow.workflow import Workflow, Step, WorkflowResult
from scrapeflow.workflow_executor import WorkflowExecutor
from scrapeflow.robots import RobotsChecker
from scrapeflow.registry import LoginHandler
from scrapeflow.browser_runtime import PlaywrightBrowserRuntime
from scrapeflow.ports import (
    RateLimiterPort,
    RetryHandlerPort,
    LoggerPort,
    MonitorPort,
    RobotsCheckerPort,
    BrowserRuntimePort,
)
from scrapeflow.exceptions import (
    ScrapeFlowError,
    ScrapeFlowTimeoutError,
    ScrapeFlowRobotsDisallowedError,
)


class ScrapeFlow:
    """Main ScrapeFlow engine for web scraping workflows."""

    def __init__(
        self,
        config: Optional[ScrapeFlowConfig] = None,
        *,
        rate_limiter: Optional[RateLimiterPort] = None,
        retry_handler: Optional[RetryHandlerPort] = None,
        logger: Optional[LoggerPort] = None,
        monitor: Optional[MonitorPort] = None,
        robots_checker: Optional[RobotsCheckerPort] = None,
        runtime: Optional[BrowserRuntimePort] = None,
        workflow_executor: Optional[WorkflowExecutor] = None,
    ):
        self.config = config or ScrapeFlowConfig()
        self.page: Optional[Page] = None

        # Initialize components
        self.anti_detection = AntiDetectionManager(self.config.anti_detection)
        self.rate_limiter = rate_limiter or RateLimiter(self.config.rate_limit)
        self.retry_handler = retry_handler or RetryHandler(self.config.retry)
        self.logger = logger or Logger(
            name="scrapeflow", level=self.config.log_level, log_file=self.config.log_file
        )
        self.monitor = monitor or PerformanceMonitor()
        self.robots_checker = robots_checker or RobotsChecker(
            user_agent=self.config.ethical_crawling.user_agent_for_robots,
            respect_robots=self.config.ethical_crawling.respect_robots_txt,
        )
        self.runtime = runtime or PlaywrightBrowserRuntime(self.config, self.anti_detection)
        self.workflow_executor = workflow_executor or WorkflowExecutor()

        self._is_running = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self):
        """Start the browser and initialize resources."""
        if self._is_running:
            return

        self.logger.info("Starting ScrapeFlow engine...")
        await self.runtime.start()
        self.page = self.runtime.page

        self._is_running = True
        self.logger.info("ScrapeFlow engine started successfully")

    async def close(self):
        """Close browser and cleanup resources."""
        if not self._is_running:
            return

        self.logger.info("Closing ScrapeFlow engine...")
        await self.runtime.close()
        self.page = None

        self._is_running = False
        self.logger.info("ScrapeFlow engine closed")

    async def navigate(self, url: str, wait_until: str = "load", timeout: Optional[int] = None):
        """Navigate to a URL with rate limiting, robots.txt check, and retry logic."""
        if not self._is_running:
            await self.start()

        # Check robots.txt before navigating
        if not await self.robots_checker.can_fetch(url):
            self.logger.warning(f"robots.txt disallows: {url}")
            raise ScrapeFlowRobotsDisallowedError(f"robots.txt disallows fetching: {url}")

        start_time = self.monitor.start_request()

        async def _navigate():
            await self.rate_limiter.acquire()
            timeout_ms = timeout or self.config.browser.timeout
            await self.runtime.goto(url, wait_until=wait_until, timeout=timeout_ms)
            self.page = self.runtime.page

        try:
            await self.retry_handler.execute_with_retry(
                _navigate,
                retryable_exceptions=(
                    Exception,
                ),  # Most navigation errors are retryable
            )
            self.monitor.end_request(start_time, success=True)
            self.logger.info(f"Successfully navigated to {url}")
        except Exception as e:
            self.monitor.end_request(start_time, success=False, error=e)
            self.logger.error(f"Failed to navigate to {url}: {str(e)}")
            raise

    async def click(self, selector: str, timeout: Optional[int] = None):
        """Click an element with retry logic."""
        if not self._is_running:
            raise ScrapeFlowError("Engine not started. Call start() first.")

        timeout_ms = timeout or self.config.browser.timeout

        async def _click():
            await self.page.click(selector, timeout=timeout_ms)

        await self.retry_handler.execute_with_retry(_click)

    async def fill(self, selector: str, value: str, timeout: Optional[int] = None):
        """Fill an input field with retry logic."""
        if not self._is_running:
            raise ScrapeFlowError("Engine not started. Call start() first.")

        timeout_ms = timeout or self.config.browser.timeout

        async def _fill():
            await self.page.fill(selector, value, timeout=timeout_ms)

        await self.retry_handler.execute_with_retry(_fill)

    async def login(
        self,
        login_url: str,
        username: str,
        password: str,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
        success_selector: Optional[str] = None,
        timeout: Optional[int] = None,
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
                return True
            except Exception:
                return False
        return True

    async def login_with_handler(
        self,
        login_url: str,
        username: str,
        password: str,
        handler: LoginHandler,
        timeout: Optional[int] = None,
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
        self, selector: str, timeout: Optional[int] = None, state: str = "visible"
    ):
        """Wait for a selector to appear."""
        if not self._is_running:
            raise ScrapeFlowError("Engine not started. Call start() first.")

        timeout_ms = timeout or self.config.browser.timeout
        await self.page.wait_for_selector(selector, timeout=timeout_ms, state=state)

    async def screenshot(self, path: str, full_page: bool = False):
        """Take a screenshot."""
        if not self._is_running:
            raise ScrapeFlowError("Engine not started. Call start() first.")

        await self.page.screenshot(path=path, full_page=full_page)

    async def execute_step(self, step: Step, context: Dict[str, Any]) -> Any:
        """Execute a workflow step with retry and error handling."""
        start_time = self.monitor.start_request()

        try:
            # Prepare function arguments
            func = step.func
            args = step.args
            kwargs = {**step.kwargs, **{"context": context, "page": self.page}}

            # Execute with timeout if specified
            if step.timeout:
                result = await asyncio.wait_for(
                    self._execute_function(func, *args, **kwargs),
                    timeout=step.timeout,
                )
            else:
                result = await self._execute_function(func, *args, **kwargs)

            self.monitor.end_request(start_time, success=True)
            return result

        except asyncio.TimeoutError:
            self.monitor.end_request(start_time, success=False, error=TimeoutError())
            raise ScrapeFlowTimeoutError(f"Step '{step.name}' timed out after {step.timeout}s")
        except Exception as e:
            self.monitor.end_request(start_time, success=False, error=e)

            if step.retryable and ErrorClassifier.is_retryable(e):
                self.monitor.record_retry()
                raise  # Let retry handler deal with it
            raise

    async def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function, handling both sync and async."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    async def _safe_call(self, func: Callable, *args, **kwargs):
        """Safely call a function, handling errors."""
        try:
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
        except Exception as e:
            self.logger.warning(f"Callback function failed: {str(e)}")

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

    def get_metrics(self):
        """Get current performance metrics."""
        return self.monitor.get_metrics()

    def reset_metrics(self):
        """Reset performance metrics."""
        self.monitor.reset()

