"""Workflow example showing how to use ScrapeFlow workflows.

This example demonstrates scraping books from books.toscrape.com,
a real e-commerce site designed for scraping practice.
"""

import asyncio
from scrapeflow import ScrapeFlow, Workflow
from scrapeflow.config import ScrapeFlowConfig
from scrapeflow.extractors import StructuredExtractor


async def scrape_books_page(page, context):
    """Extract book information from the page."""
    # Use structured extractor to get all books
    schema = {
        "books": {
            "items": "article.product_pod",
            "schema": {
                "title": "h3 a",
                "price": ".price_color",
                "availability": ".instock.availability",
            }
        }
    }
    extractor = StructuredExtractor(schema)
    data = await extractor.extract(page)
    
    context["books_data"] = data
    return data


async def save_data(data, context):
    """Save extracted data (mock function)."""
    books = data.get("books", [])
    print(f"💾 Saving {len(books)} books to database...")
    # In real usage, you would save to database, file, etc.
    for book in books[:3]:  # Show first 3
        print(f"   - {book.get('title', '')[:40]}... - {book.get('price', '')}")
    return True


async def handle_error(error, context):
    """Handle errors during scraping."""
    print(f"❌ Error occurred: {error}")
    # You could log to file, send notification, etc.


async def main():
    """Workflow example with real website."""
    config = ScrapeFlowConfig()
    config.retry.max_retries = 3
    config.rate_limit.requests_per_second = 2.0

    async with ScrapeFlow(config) as scraper:
        # Create a workflow
        workflow = Workflow(name="book_scraper")

        # Add steps
        async def navigate_to_books(page, context):
            """Step 1: Navigate to books page"""
            scraper = context["scraper"]
            await scraper.navigate("https://books.toscrape.com/")
            await scraper.wait_for_selector("article.product_pod", timeout=10000)

        workflow.add_step(
            name="navigate",
            func=navigate_to_books,
            required=True,
        )

        workflow.add_step(
            name="extract_data",
            func=scrape_books_page,
            retryable=True,
            required=True,
            on_success=save_data,
            on_error=handle_error,
        )

        # Execute workflow
        result = await scraper.run_workflow(workflow)

        if result.success:
            print("\n✅ Workflow completed successfully!")
            books = result.final_data.get("books", [])
            print(f"📚 Extracted {len(books)} books")
        else:
            print(f"\n❌ Workflow failed: {result.error}")

        # Print metrics
        metrics = scraper.get_metrics()
        print(f"\n📊 Metrics:")
        print(f"   Total requests: {metrics.total_requests}")
        print(f"   Success rate: {metrics.get_success_rate():.2f}%")
        print(f"   Average response time: {metrics.average_response_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())

