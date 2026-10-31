"""Polite crawling: honour robots.txt (Disallow and Crawl-delay) and report metrics.

Shows:
  * ``navigate()`` refusing a robots.txt-disallowed URL with ``ScrapeFlowRobotsDisallowedError``
  * reading ``Crawl-delay`` with ``RobotsChecker.get_crawl_delay()`` and turning it into a
    ``RateLimitConfig`` (ScrapeFlow does not apply Crawl-delay on its own)
  * the token-bucket rate limiter spacing out requests
  * ``get_metrics()`` after the crawl

Needs: ``pip install scrapeflow-py`` and ``playwright install chromium``.
No internet and no API key: it crawls the bundled demo site on 127.0.0.1.
The demo robots.txt asks for a 1 s delay, so the crawl takes a few seconds on purpose.

Run: python examples/polite_crawler.py
"""

from __future__ import annotations

import asyncio
import time

from _demo_site import serve_demo_site

from scrapeflow import RobotsChecker, ScrapeFlow
from scrapeflow.config import EthicalCrawlingConfig, RateLimitConfig, ScrapeFlowConfig
from scrapeflow.exceptions import ScrapeFlowRobotsDisallowedError
from scrapeflow.extractors import Extractor

USER_AGENT = "DemoPriceBot"


async def main() -> None:
    with serve_demo_site() as base_url:
        # 1. Ask robots.txt how fast we may go before configuring the engine.
        robots = RobotsChecker(user_agent=USER_AGENT)
        delay = await robots.get_crawl_delay(base_url + "/") or 0.5
        print(f"robots.txt Crawl-delay for {USER_AGENT}: {delay}s")

        config = ScrapeFlowConfig(
            # burst_size=1 means no initial burst: every request waits its turn.
            rate_limit=RateLimitConfig(requests_per_second=1 / delay, burst_size=1),
            ethical_crawling=EthicalCrawlingConfig(
                respect_robots_txt=True, user_agent_for_robots=USER_AGENT
            ),
            log_level="WARNING",
        )
        urls = [
            base_url + "/index.html",
            base_url + "/admin/index.html",  # disallowed by robots.txt
            base_url + "/catalogue-2.html",
            base_url + "/catalogue-3.html",
        ]

        started = time.perf_counter()
        async with ScrapeFlow(config, robots_checker=robots) as scraper:
            for url in urls:
                path = url.removeprefix(base_url)
                try:
                    await scraper.navigate(url)
                except ScrapeFlowRobotsDisallowedError:
                    print(f"  skipped {path:<20} (robots.txt Disallow)")
                    continue
                titles = await Extractor.extract_attributes(scraper.page, "h3 a", "title")
                elapsed = time.perf_counter() - started
                print(f"  fetched {path:<20} t={elapsed:4.1f}s  {len(titles)} books")
            metrics = scraper.get_metrics()

    print(
        f"\n{metrics.total_requests} requests, {metrics.get_success_rate():.0f}% success, "
        f"avg {metrics.average_response_time:.2f}s per request"
    )


if __name__ == "__main__":
    asyncio.run(main())
