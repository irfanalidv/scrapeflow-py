"""Advanced example showing anti-detection, rate limiting, and structured extraction."""

import asyncio
from scrapeflow import ScrapeFlow
from scrapeflow.config import (
    ScrapeFlowConfig,
    AntiDetectionConfig,
    RateLimitConfig,
    RetryConfig,
)
from scrapeflow.extractors import StructuredExtractor, Extractor


async def main():
    """Advanced scraping with all features enabled."""
    # Configure anti-detection
    anti_detection = AntiDetectionConfig(
        rotate_user_agents=True,
        stealth_mode=True,
        viewport_width=1920,
        viewport_height=1080,
    )

    # Configure rate limiting
    rate_limit = RateLimitConfig(
        requests_per_second=1.0,
        burst_size=3,
    )

    # Configure retry behavior
    retry = RetryConfig(
        max_retries=5,
        initial_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0,
    )

    # Create config
    config = ScrapeFlowConfig(
        anti_detection=anti_detection,
        rate_limit=rate_limit,
        retry=retry,
        log_level="INFO",
        debug=False,
    )

    async with ScrapeFlow(config) as scraper:
        # Navigate to page
        await scraper.navigate("https://quotes.toscrape.com/")

        # Use structured extractor
        schema = {
            "quotes": {
                "items": ".quote",
                "schema": {
                    "text": ".text",
                    "author": ".author",
                },
            }
        }

        extractor = StructuredExtractor(schema)
        data = await extractor.extract(scraper.page)

        # Extract tags separately using Extractor for each quote
        quotes_with_tags = []
        quote_elements = scraper.page.locator(".quote")
        count = await quote_elements.count()
        
        for i, quote_data in enumerate(data.get("quotes", [])[:5]):  # First 5
            quote_elem = quote_elements.nth(i)
            tags = await Extractor.extract_texts(quote_elem, ".tag")
            quote_data["tags"] = tags
            quotes_with_tags.append(quote_data)

        print("📝 Extracted quotes:")
        for i, quote in enumerate(quotes_with_tags, 1):
            text = quote.get("text", "")[:60] if quote.get("text") else ""
            author = quote.get("author", "")
            tags = quote.get("tags", [])
            print(f"\n{i}. {text}...")
            print(f"   Author: {author}")
            print(f"   Tags: {', '.join(tags) if tags else 'None'}")

        # Get metrics
        metrics = scraper.get_metrics()
        print(f"\nScraping completed:")
        print(f"  Success rate: {metrics.get_success_rate():.2f}%")
        print(f"  Total requests: {metrics.total_requests}")
        print(f"  Retries: {metrics.retry_count}")


if __name__ == "__main__":
    asyncio.run(main())

