"""Tests for robots.txt enforcement (see test_core_units.py for fetch-failure handling)."""

from scrapeflow.robots import RobotsChecker


async def test_robots_checker_respect_disabled():
    """When respect_robots=False, can_fetch always returns True."""
    checker = RobotsChecker(respect_robots=False)
    assert await checker.can_fetch("https://example.com/page") is True


async def test_robots_checker_respect_enabled_consults_rules():
    """When respect_robots=True, can_fetch applies the parsed robots.txt rules."""
    checker = RobotsChecker(respect_robots=True, user_agent="ScrapeFlow")

    async def fake_download(url: str) -> tuple[int, str]:
        assert url == "https://quotes.example/robots.txt"
        return 200, "User-agent: ScrapeFlow\nDisallow: /login\n"

    checker._download = fake_download  # type: ignore[method-assign]
    assert await checker.can_fetch("https://quotes.example/") is True
    assert await checker.can_fetch("https://quotes.example/login") is False
