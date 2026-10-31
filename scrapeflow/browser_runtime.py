"""Playwright browser runtime adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from scrapeflow.anti_detection import AntiDetectionManager
from scrapeflow.config import BrowserType, ScrapeFlowConfig
from scrapeflow.exceptions import ScrapeFlowNotStartedError


class PlaywrightBrowserRuntime:
    """Infrastructure adapter for Playwright lifecycle and navigation."""

    def __init__(self, config: ScrapeFlowConfig, anti_detection: AntiDetectionManager) -> None:
        self.config = config
        self.anti_detection = anti_detection
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self._page: Page | None = None
        self._is_running = False

    @property
    def page(self) -> Page | None:
        return self._page

    async def start(self) -> None:
        """Launch Playwright, the browser, a context and a page.

        If any step fails, everything already launched is shut down before the error is
        re-raised, so a failed start never leaks a browser process.
        """
        if self._is_running:
            return
        try:
            await self._launch()
        except BaseException:
            await self._teardown()
            raise
        self._is_running = True

    async def _launch(self) -> None:
        self.playwright = await async_playwright().start()
        browser_type_map = {
            BrowserType.CHROMIUM: self.playwright.chromium,
            BrowserType.FIREFOX: self.playwright.firefox,
            BrowserType.WEBKIT: self.playwright.webkit,
        }
        browser_launcher = browser_type_map[self.config.browser.browser_type]

        proxy = self.config.browser.proxy or self.anti_detection.get_proxy()
        browser_args = self.config.browser.args.copy()
        if self.config.anti_detection.stealth_mode:
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
            proxy=proxy,  # type: ignore[arg-type]
        )

        context_options: dict[str, Any] = {
            "viewport": {
                "width": self.config.anti_detection.viewport_width,
                "height": self.config.anti_detection.viewport_height,
            },
            "user_agent": self.anti_detection.get_user_agent(),
        }
        state_path = self.config.browser.storage_state_path
        if state_path and Path(state_path).exists():
            context_options["storage_state"] = state_path
        self.context = await self.browser.new_context(**context_options)
        self._page = await self.context.new_page()
        await self.anti_detection.apply_stealth(self._page)
        self._page.set_default_timeout(self.config.browser.timeout)

    async def close(self) -> None:
        """Close the page, context, browser and Playwright driver."""
        if not self._is_running:
            return
        await self._teardown()

    async def _teardown(self) -> None:
        if self._page:
            await self._page.close()
            self._page = None
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

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        if not self._page:
            raise ScrapeFlowNotStartedError("Browser runtime is not started.")
        await self._page.goto(url, wait_until=wait_until, timeout=timeout)  # type: ignore[arg-type]

    async def save_storage_state(self, path: str) -> None:
        """Save cookies and local storage to a JSON file for session persistence."""
        if not self.context:
            raise ScrapeFlowNotStartedError("Browser runtime is not started.")
        await self.context.storage_state(path=path)
