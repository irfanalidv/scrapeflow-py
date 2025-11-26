"""Main ScrapeFlow engine that orchestrates all components."""

import asyncio
import time
from typing import Optional, Dict, Any, Callable
from playwright.async_api import (
    async_playwright,
    Playwright,
    Browser,
    BrowserContext,
    Page,
)

from scrapeflow.config import (
    ScrapeFlowConfig,
    BrowserConfig,
    RetryConfig,
    RateLimitConfig,
    AntiDetectionConfig,
    BrowserType,
)
from scrapeflow.anti_detection import AntiDetectionManager
from scrapeflow.rate_limiter import RateLimiter
from scrapeflow.retry import RetryHandler, ErrorClassifier
from scrapeflow.monitoring import Logger, PerformanceMonitor
from scrapeflow.workflow import Workflow, Step, WorkflowResult
from scrapeflow.exceptions import (
    ScrapeFlowError,
    ScrapeFlowTimeoutError,
    ScrapeFlowBlockedError,
)


class ScrapeFlow:
    """Main ScrapeFlow engine for web scraping workflows."""

    def __init__(self, config: Optional[ScrapeFlowConfig] = None):
        self.config = config or ScrapeFlowConfig()
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Initialize components
        self.anti_detection = AntiDetectionManager(self.config.anti_detection)
        self.rate_limiter = RateLimiter(self.config.rate_limit)
        self.retry_handler = RetryHandler(self.config.retry)
        self.logger = Logger(
            name="scrapeflow",
            level=self.config.log_level,
            log_file=self.config.log_file,
        )
        self.monitor = PerformanceMonitor()

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
        self.playwright = await async_playwright().start()

        # Get browser type
        browser_type_map = {
            BrowserType.CHROMIUM: self.playwright.chromium,
            BrowserType.FIREFOX: self.playwright.firefox,
            BrowserType.WEBKIT: self.playwright.webkit,
        }
        browser_launcher = browser_type_map[self.config.browser.browser_type]

        # Get proxy if configured
        proxy = self.config.browser.proxy or self.anti_detection.get_proxy()

        # Launch browser
        browser_args = self.config.browser.args.copy()
        if self.config.anti_detection.stealth_mode:
            # Add stealth arguments
            browser_args.extend(
                [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            )

        self.browser = await browser_launcher.launch(
            headless=self.config.browser.headless,
            slow_mo=self.config.browser.slow_mo,
            args=browser_args,
            proxy=proxy,
        )

        # Create browser context
        context_options = {
            "viewport": {
                "width": self.config.anti_detection.viewport_width,
                "height": self.config.anti_detection.viewport_height,
            },
            "user_agent": self.anti_detection.get_user_agent(),
        }

        self.context = await self.browser.new_context(**context_options)

        # Create page
        self.page = await self.context.new_page()

        # Apply stealth mode
        await self.anti_detection.apply_stealth(self.page)

        # Set default timeout
        self.page.set_default_timeout(self.config.browser.timeout)

        self._is_running = True
        self.logger.info("ScrapeFlow engine started successfully")

    async def close(self):
        """Close browser and cleanup resources."""
        if not self._is_running:
            return

        self.logger.info("Closing ScrapeFlow engine...")

        if self.page:
            await self.page.close()
            self.page = None

        if self.context:
            await self.context.close()
            self.context = None

        if self.browser:
            await self.browser.close()
            self.browser = None

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        self._is_running = False
        self.logger.info("ScrapeFlow engine closed")

    async def navigate(self, url: str, wait_until: str = "load", timeout: Optional[int] = None):
        """Navigate to a URL with rate limiting and retry logic."""
        if not self._is_running:
            await self.start()

        start_time = self.monitor.start_request()

        async def _navigate():
            await self.rate_limiter.acquire()
            timeout_ms = timeout or self.config.browser.timeout
            await self.page.goto(url, wait_until=wait_until, timeout=timeout_ms)

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
        result = await workflow.execute(self)
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

