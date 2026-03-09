"""Playwright browser runtime adapter."""

from typing import Optional
from playwright.async_api import (
    async_playwright,
    Playwright,
    Browser,
    BrowserContext,
    Page,
)

from scrapeflow.config import ScrapeFlowConfig, BrowserType
from scrapeflow.anti_detection import AntiDetectionManager


class PlaywrightBrowserRuntime:
    """Infrastructure adapter for Playwright lifecycle and navigation."""

    def __init__(self, config: ScrapeFlowConfig, anti_detection: AntiDetectionManager):
        self.config = config
        self.anti_detection = anti_detection
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_running = False

    @property
    def page(self) -> Optional[Page]:
        return self._page

    async def start(self) -> None:
        if self._is_running:
            return

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
            proxy=proxy,
        )

        context_options = {
            "viewport": {
                "width": self.config.anti_detection.viewport_width,
                "height": self.config.anti_detection.viewport_height,
            },
            "user_agent": self.anti_detection.get_user_agent(),
        }
        if self.config.browser.storage_state_path:
            import os
            if os.path.exists(self.config.browser.storage_state_path):
                context_options["storage_state"] = self.config.browser.storage_state_path
        self.context = await self.browser.new_context(**context_options)
        self._page = await self.context.new_page()
        await self.anti_detection.apply_stealth(self._page)
        self._page.set_default_timeout(self.config.browser.timeout)
        self._is_running = True

    async def close(self) -> None:
        if not self._is_running:
            return

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
            raise RuntimeError("Browser runtime is not started.")
        await self._page.goto(url, wait_until=wait_until, timeout=timeout)

    async def save_storage_state(self, path: str) -> None:
        """Save cookies and local storage to a JSON file for session persistence."""
        if not self.context:
            raise RuntimeError("Browser runtime is not started.")
        await self.context.storage_state(path=path)
