"""Basic usage example of ScrapeFlow."""

import asyncio
from scrapeflow import ScrapeFlow
from scrapeflow.config import ScrapeFlowConfig


async def main():
    """Basic scraping example."""
    # Create a simple configuration
    config = ScrapeFlowConfig()
    config.browser.headless = False  # Set to True for headless mode
    config.retry.max_retries = 3

    # Use ScrapeFlow as a context manager
    async with ScrapeFlow(config) as scraper:
        # Navigate to a page
        await scraper.navigate("https://example.com")

        # Take a screenshot
        await scraper.screenshot("example.png")

        # Extract some data
        title = await scraper.page.title()
        print(f"Page title: {title}")

        # Get metrics
        metrics = scraper.get_metrics()
        print(f"Success rate: {metrics.get_success_rate():.2f}%")


if __name__ == "__main__":
    asyncio.run(main())

