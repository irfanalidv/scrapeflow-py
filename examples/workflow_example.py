"""Workflow example showing how to use ScrapeFlow workflows."""

import asyncio
from scrapeflow import ScrapeFlow, Workflow
from scrapeflow.config import ScrapeFlowConfig
from scrapeflow.extractors import Extractor


async def scrape_product_page(page, context):
    """Extract product information from a page."""
    # Wait for product details to load
    await page.wait_for_selector(".product-title", timeout=10000)

    # Extract product data
    product_data = {
        "title": await Extractor.extract_text(page, ".product-title"),
        "price": await Extractor.extract_text(page, ".price"),
        "description": await Extractor.extract_text(page, ".description"),
        "images": await Extractor.extract_images(page, ".product-image"),
    }

    context["product_data"] = product_data
    return product_data


async def save_data(data, context):
    """Save extracted data (mock function)."""
    print(f"Saving data: {data}")
    # In real usage, you would save to database, file, etc.
    return True


async def handle_error(error, context):
    """Handle errors during scraping."""
    print(f"Error occurred: {error}")
    # You could log to file, send notification, etc.


async def main():
    """Workflow example."""
    config = ScrapeFlowConfig()
    config.retry.max_retries = 3
    config.rate_limit.requests_per_second = 2.0

    async with ScrapeFlow(config) as scraper:
        # Create a workflow
        workflow = Workflow(name="product_scraper")

        # Add steps
        async def navigate_to_product(page, context):
            await scraper.navigate("https://example.com/products/1")

        workflow.add_step(
            name="navigate",
            func=navigate_to_product,
        )

        workflow.add_step(
            name="extract_data",
            func=scrape_product_page,
            retryable=True,
            required=True,
            on_success=save_data,
            on_error=handle_error,
        )

        # Execute workflow
        result = await scraper.run_workflow(workflow)

        if result.success:
            print("Workflow completed successfully!")
            print(f"Extracted data: {result.final_data}")
        else:
            print(f"Workflow failed: {result.error}")

        # Print metrics
        metrics = scraper.get_metrics()
        print(f"\nMetrics:")
        print(f"  Total requests: {metrics.total_requests}")
        print(f"  Success rate: {metrics.get_success_rate():.2f}%")
        print(f"  Average response time: {metrics.average_response_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())

