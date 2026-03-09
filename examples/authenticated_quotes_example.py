"""
Authenticated extraction example using quotes.toscrape.com.

Demonstrates:
- login workflow with username/password
- authenticated data extraction using SpecificationExtractor
- robots.txt-aware navigation
"""

import asyncio
from pydantic import BaseModel

from scrapeflow import (
    ScrapeFlow,
    SpecificationExtractor,
    get_registry,
    register_quotes_login_handler,
)
from scrapeflow.config import ScrapeFlowConfig, EthicalCrawlingConfig
from scrapeflow.specifications import FieldSpec, ItemSpec


class QuoteItem(BaseModel):
    text: str
    author: str


class QuotesPage(BaseModel):
    quotes: list[QuoteItem]


async def run_authenticated_scrape(username: str, password: str) -> None:
    schema = {
        "quotes": ItemSpec(
            items_selector=".quote",
            fields={
                "text": FieldSpec(selector=".text"),
                "author": FieldSpec(selector=".author"),
            },
        )
    }

    config = ScrapeFlowConfig(
        ethical_crawling=EthicalCrawlingConfig(
            respect_robots_txt=True,
            user_agent_for_robots="ScrapeFlow",
        )
    )

    async with ScrapeFlow(config) as scraper:
        register_quotes_login_handler(get_registry())
        handler = get_registry().get_login("quotes_login")
        if handler is None:
            raise RuntimeError("Missing quotes_login handler in registry")

        is_logged_in = await scraper.login_with_handler(
            login_url="https://quotes.toscrape.com/login",
            username=username,
            password=password,
            handler=handler,
            timeout=10000,
        )
        if not is_logged_in:
            error_text = await scraper.page.locator(".error").first.text_content()
            raise RuntimeError(f"Login failed: {(error_text or '').strip()}")

        extractor = SpecificationExtractor(QuotesPage, schema=schema)
        data = await extractor.extract(scraper.page)

        print(f"Authenticated login: {is_logged_in}")
        print(f"Quotes extracted: {len(data.quotes)}")
        for idx, quote in enumerate(data.quotes[:3], start=1):
            print(f"{idx}. {quote.author}: {quote.text[:80]}...")


if __name__ == "__main__":
    asyncio.run(run_authenticated_scrape(username="admin", password="amdin"))
