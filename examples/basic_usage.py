"""Basic usage example of ScrapeFlow.

This example demonstrates basic scraping from quotes.toscrape.com,
a real website designed for scraping practice.
"""

import asyncio
from scrapeflow import ScrapeFlow
from scrapeflow.config import ScrapeFlowConfig, RateLimitConfig, RetryConfig
from scrapeflow.extractors import Extractor


async def main():
    """Basic scraping example with real website."""
    # Create a simple configuration
    config = ScrapeFlowConfig(
        rate_limit=RateLimitConfig(requests_per_second=2.0),
        retry=RetryConfig(max_retries=3),
    )
    config.browser.headless = True  # Set to False to see browser

    # Use ScrapeFlow as a context manager
    async with ScrapeFlow(config) as scraper:
        # Navigate to a real scraping practice site
        await scraper.navigate("https://quotes.toscrape.com/")

        # Extract some data
        title = await scraper.page.title()
        print(f"Page title: {title}")

        # Extract quotes from the page
        quotes = []
        quote_elements = scraper.page.locator(".quote")
        count = await quote_elements.count()

        for i in range(min(count, 5)):  # Show first 5 quotes
            quote_elem = quote_elements.nth(i)
            text = await quote_elem.locator(".text").text_content()
            author = await quote_elem.locator(".author").text_content()
            tags = await Extractor.extract_texts(quote_elem, ".tag")

            quotes.append(
                {
                    "quote": text.strip() if text else "",
                    "author": author.strip() if author else "",
                    "tags": tags,
                }
            )

        print(f"\nExtracted {len(quotes)} quotes:")
        for i, quote in enumerate(quotes, 1):
            print(f"\n{i}. {quote['quote'][:60]}...")
            print(f"   Author: {quote['author']}")
            print(f"   Tags: {', '.join(quote['tags'])}")

        # Get metrics
        metrics = scraper.get_metrics()
        print("\n📊 Metrics:")
        print(f"   Success rate: {metrics.get_success_rate():.2f}%")
        print(f"   Total requests: {metrics.total_requests}")
        print(f"   Average response time: {metrics.average_response_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
