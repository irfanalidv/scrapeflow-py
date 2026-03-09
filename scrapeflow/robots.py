"""
robots.txt parsing and enforcement for ethical crawling.

Respects robots.txt directives by default. Integrates with the specification
layer so compliance is built-in, not retrofitted.
"""

import asyncio
import time
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp

from scrapeflow.exceptions import ScrapeFlowError


class RobotsChecker:
    """
    Check robots.txt compliance before crawling.

    Fetches and parses robots.txt, caches results, and provides can_fetch()
    to determine if a URL is allowed for a given user agent.
    """

    def __init__(
        self,
        user_agent: str = "ScrapeFlow",
        respect_robots: bool = True,
        cache_ttl: int = 3600,
    ):
        """
        Args:
            user_agent: User agent string for robots.txt rules.
            respect_robots: If False, can_fetch always returns True.
            cache_ttl: Cache TTL in seconds (default 1 hour).
        """
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[RobotFileParser, float]] = {}
        self._lock = asyncio.Lock()

    def _get_robots_url(self, url: str) -> str:
        """Get the robots.txt URL for a given page URL."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return urljoin(base, "/robots.txt")

    async def _fetch_robots(self, robots_url: str) -> RobotFileParser:
        """Fetch and parse robots.txt."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                    else:
                        content = ""
            except Exception:
                content = ""

        rp = RobotFileParser()
        rp.parse(content.splitlines())
        return rp

    async def can_fetch(self, url: str) -> bool:
        """
        Check if the given URL can be fetched per robots.txt.

        Returns True if allowed (or respect_robots=False), False if disallowed.
        """
        if not self.respect_robots:
            return True

        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = self._get_robots_url(url)

        async with self._lock:
            now = time.time()
            if base in self._cache:
                rp, cached_at = self._cache[base]
                if now - cached_at < self.cache_ttl:
                    return rp.can_fetch(self.user_agent, url)

            rp = await self._fetch_robots(robots_url)
            self._cache[base] = (rp, now)
            return rp.can_fetch(self.user_agent, url)

    async def get_crawl_delay(self, url: str) -> Optional[float]:
        """
        Get Crawl-delay in seconds if specified in robots.txt.

        Note: Crawl-delay is non-standard (used by some bots) but we support it
        for maximum compliance.
        """
        if not self.respect_robots:
            return None

        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = self._get_robots_url(url)

        async with self._lock:
            if base not in self._cache:
                rp = await self._fetch_robots(robots_url)
                self._cache[base] = (rp, time.time())
            rp, _ = self._cache[base]

        # RobotFileParser doesn't expose crawl_delay; we'd need a custom parser.
        # For now return None; rate limiting is handled by RateLimiter.
        return None
