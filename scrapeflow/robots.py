"""
robots.txt parsing and enforcement for ethical crawling.

Respects robots.txt directives by default. Fetch failures are handled as described in
RFC 9309 (Robots Exclusion Protocol), section 2.3.1:

* 2xx: parse the file and apply its rules.
* 4xx ("unavailable"): no rules apply, so every path is allowed.
* 5xx, or a network error ("unreachable"): assume complete disallow.

Only ``http`` and ``https`` URLs are checked; other schemes (``about:``, ``data:``,
``file:``) have no robots.txt and are always allowed.
"""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import aiohttp

logger = logging.getLogger(__name__)

_DISALLOW_ALL = ["User-agent: *", "Disallow: /"]


class RobotsChecker:
    """
    Check robots.txt compliance before crawling.

    Fetches and parses robots.txt, caches results per origin, and provides can_fetch()
    to determine if a URL is allowed for a given user agent.
    """

    def __init__(
        self,
        user_agent: str = "ScrapeFlow",
        respect_robots: bool = True,
        cache_ttl: int = 3600,
        fetch_timeout: float = 10.0,
    ) -> None:
        """
        Args:
            user_agent: User agent string for robots.txt rules.
            respect_robots: If False, can_fetch always returns True.
            cache_ttl: Cache TTL in seconds (default 1 hour).
            fetch_timeout: Total timeout in seconds for fetching robots.txt.
        """
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.cache_ttl = cache_ttl
        self.fetch_timeout = fetch_timeout
        self._cache: dict[str, tuple[RobotFileParser, float]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _origin(url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"

    def _get_robots_url(self, url: str) -> str:
        """Get the robots.txt URL for a given page URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    async def _download(self, robots_url: str) -> tuple[int, str]:
        """Return ``(status, body)`` for ``robots_url``. Separated out for testing."""
        timeout = aiohttp.ClientTimeout(total=self.fetch_timeout)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(robots_url, headers={"User-Agent": self.user_agent}) as resp,
        ):
            body = await resp.text(errors="replace") if resp.status < 300 else ""
            return resp.status, body

    async def _fetch_robots(self, robots_url: str) -> RobotFileParser:
        """Fetch and parse robots.txt, applying RFC 9309 rules for failures."""
        try:
            status, content = await self._download(robots_url)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, UnicodeError) as exc:
            logger.warning(
                "Could not fetch %s (%s); treating site as disallowed (RFC 9309)", robots_url, exc
            )
            lines = _DISALLOW_ALL
        else:
            if 200 <= status < 300:
                lines = content.splitlines()
            elif 400 <= status < 500:
                lines = []  # unavailable: no restrictions
            else:
                logger.warning(
                    "%s returned HTTP %d; treating site as disallowed (RFC 9309)",
                    robots_url,
                    status,
                )
                lines = _DISALLOW_ALL

        rp = RobotFileParser()
        rp.parse(lines)
        return rp

    async def _get_parser(self, origin: str, url: str) -> RobotFileParser:
        async with self._lock:
            now = time.time()
            cached = self._cache.get(origin)
            if cached is not None and now - cached[1] < self.cache_ttl:
                return cached[0]
            rp = await self._fetch_robots(self._get_robots_url(url))
            self._cache[origin] = (rp, now)
            return rp

    async def can_fetch(self, url: str) -> bool:
        """
        Check if the given URL can be fetched per robots.txt.

        Returns True if allowed (or respect_robots=False), False if disallowed.
        """
        if not self.respect_robots:
            return True
        origin = self._origin(url)
        if origin is None:
            return True
        rp = await self._get_parser(origin, url)
        return rp.can_fetch(self.user_agent, url)

    async def get_crawl_delay(self, url: str) -> float | None:
        """
        Return the ``Crawl-delay`` (seconds) robots.txt declares for this user agent, if any.

        Crawl-delay is not part of RFC 9309, but many sites use it. ScrapeFlow does not apply
        it automatically; feed it into ``RateLimitConfig`` if you want to honour it.
        """
        if not self.respect_robots:
            return None
        origin = self._origin(url)
        if origin is None:
            return None
        rp = await self._get_parser(origin, url)
        delay = rp.crawl_delay(self.user_agent)
        return float(delay) if delay is not None else None
