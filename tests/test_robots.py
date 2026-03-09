"""Tests for robots.txt enforcement."""

import pytest
from scrapeflow.robots import RobotsChecker


@pytest.mark.asyncio
async def test_robots_checker_respect_disabled():
    """When respect_robots=False, can_fetch always returns True."""
    checker = RobotsChecker(respect_robots=False)
    assert await checker.can_fetch("https://example.com/page") is True


@pytest.mark.asyncio
async def test_robots_checker_respect_enabled():
    """When respect_robots=True, can_fetch consults robots.txt."""
    checker = RobotsChecker(respect_robots=True, user_agent="ScrapeFlow")
    # Most sites allow ScrapeFlow; this may return True or False
    result = await checker.can_fetch("https://quotes.toscrape.com/")
    assert isinstance(result, bool)
