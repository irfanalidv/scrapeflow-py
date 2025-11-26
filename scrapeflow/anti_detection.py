"""Anti-detection utilities for web scraping."""

import random
from typing import List, Optional, Dict
from scrapeflow.config import AntiDetectionConfig


class UserAgentRotator:
    """Manages user agent rotation."""

    DEFAULT_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self, user_agents: Optional[List[str]] = None):
        self.user_agents = user_agents or self.DEFAULT_USER_AGENTS

    def get_random(self) -> str:
        """Get a random user agent."""
        return random.choice(self.user_agents)

    def get(self, index: int = None) -> str:
        """Get a user agent by index or random."""
        if index is not None:
            return self.user_agents[index % len(self.user_agents)]
        return self.get_random()


class ProxyRotator:
    """Manages proxy rotation."""

    def __init__(self, proxies: List[Dict[str, str]]):
        self.proxies = proxies
        self.current_index = 0

    def get_next(self) -> Optional[Dict[str, str]]:
        """Get the next proxy in rotation."""
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_index % len(self.proxies)]
        self.current_index += 1
        return proxy

    def get_random(self) -> Optional[Dict[str, str]]:
        """Get a random proxy."""
        if not self.proxies:
            return None
        return random.choice(self.proxies)


class StealthMode:
    """Applies stealth techniques to avoid detection."""

    @staticmethod
    async def apply_stealth(page):
        """Apply stealth techniques to a Playwright page."""
        # Remove webdriver property
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
        )

        # Override permissions
        await page.add_init_script(
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            """
        )

        # Override plugins
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            """
        )

        # Override languages
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            """
        )

        # Mock chrome object
        await page.add_init_script(
            """
            window.chrome = {
                runtime: {}
            };
            """
        )


class AntiDetectionManager:
    """Manages all anti-detection features."""

    def __init__(self, config: AntiDetectionConfig):
        self.config = config
        self.user_agent_rotator = (
            UserAgentRotator(config.user_agents) if config.rotate_user_agents else None
        )
        self.proxy_rotator = (
            ProxyRotator(config.proxies) if config.rotate_proxies else None
        )

    def get_user_agent(self) -> Optional[str]:
        """Get a user agent if rotation is enabled."""
        if self.user_agent_rotator:
            return self.user_agent_rotator.get_random()
        return None

    def get_proxy(self) -> Optional[Dict[str, str]]:
        """Get a proxy if rotation is enabled."""
        if self.proxy_rotator:
            return self.proxy_rotator.get_next()
        return None

    async def apply_stealth(self, page):
        """Apply stealth mode to a page if enabled."""
        if self.config.stealth_mode:
            await StealthMode.apply_stealth(page)

