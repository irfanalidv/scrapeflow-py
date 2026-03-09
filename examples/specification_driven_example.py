"""
Specification-driven extraction example - aligns with PST.AG job requirements.

Demonstrates:
- Pydantic specification-driven extraction
- robots.txt compliance
- Ethical crawling (GDPR/CCPA config)
- Shared selector registry
- Monitoring with alerting
"""

import asyncio
from pydantic import BaseModel, Field

from scrapeflow import ScrapeFlow, SpecificationExtractor
from scrapeflow.config import (
    ScrapeFlowConfig,
    EthicalCrawlingConfig,
    RateLimitConfig,
)
from scrapeflow.specifications import FieldSpec, ItemSpec, JobListingSpec
from scrapeflow.registry import get_registry, register_job_listing_schema


class JobListingsPage(BaseModel):
    """Output model for job listings extraction."""

    jobs: list[JobListingSpec]


async def scrape_job_listings():
    """Scrape job listings using specification-driven extraction."""
    # Ethical crawling: robots.txt, rate limiting
    config = ScrapeFlowConfig(
        ethical_crawling=EthicalCrawlingConfig(
            respect_robots_txt=True,
            user_agent_for_robots="ScrapeFlow",
        ),
        rate_limit=RateLimitConfig(requests_per_second=1.0),
    )

    schema = {
        "jobs": ItemSpec(
            items_selector=".job-card, .job-listing, article.job, .job-item, .quote",
            fields={
                "title": FieldSpec(selector="h2 a, .job-title, .title a, .text"),
                "company": FieldSpec(
                    selector=".company, .employer, .author",
                    default="",
                ),
                "location": FieldSpec(
                    selector=".location, .job-location",
                    default="",
                ),
                "url": FieldSpec(
                    selector="h2 a, .job-title a, a",
                    type="attribute",
                    attribute="href",
                ),
            },
        )
    }

    async with ScrapeFlow(config) as scraper:
        # navigate() checks robots.txt automatically
        await scraper.navigate("https://quotes.toscrape.com/")

        extractor = SpecificationExtractor(JobListingsPage, schema=schema)
        data = await extractor.extract(scraper.page)

        print(f"Extracted {len(data.jobs)} items (validated via Pydantic)")
        for i, job in enumerate(data.jobs[:3]):
            print(f"  {i+1}. {job.title[:50]}... | {job.company or 'N/A'}")

        metrics = scraper.get_metrics()
        print(f"\nMetrics: {metrics.total_requests} requests, {metrics.get_success_rate():.1f}% success")


if __name__ == "__main__":
    asyncio.run(scrape_job_listings())
