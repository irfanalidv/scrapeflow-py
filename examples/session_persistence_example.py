"""
Session/cookie persistence example.

Demonstrates:
- Login, save storage state (cookies + localStorage)
- Restart with storage_state_path to skip login on next run
"""

import asyncio
import os
import tempfile

from scrapeflow import ScrapeFlow, SpecificationExtractor, get_registry, register_quotes_login_handler
from scrapeflow.config import ScrapeFlowConfig, EthicalCrawlingConfig, BrowserConfig
from scrapeflow.specifications import FieldSpec, ItemSpec
from pydantic import BaseModel


class QuoteItem(BaseModel):
    text: str
    author: str


class QuotesPage(BaseModel):
    quotes: list[QuoteItem]


async def run_session_example():
    """Login, save session, then load session on next run."""
    state_file = os.path.join(tempfile.gettempdir(), "scrapeflow_quotes_session.json")

    config = ScrapeFlowConfig(
        ethical_crawling=EthicalCrawlingConfig(respect_robots_txt=True),
    )

    schema = {
        "quotes": ItemSpec(
            items_selector=".quote",
            fields={
                "text": FieldSpec(selector=".text"),
                "author": FieldSpec(selector=".author"),
            },
        )
    }

    # Step 1: Login and save session (if state file doesn't exist)
    if not os.path.exists(state_file):
        async with ScrapeFlow(config) as scraper:
            register_quotes_login_handler(get_registry())
            handler = get_registry().get_login("quotes_login")
            await scraper.login_with_handler(
                login_url="https://quotes.toscrape.com/login",
                username="admin",
                password="amdin",
                handler=handler,
            )
            await scraper.save_storage_state(state_file)
            print("Session saved to", state_file)

    # Step 2: Use saved session (no login needed)
    config_with_state = ScrapeFlowConfig(
        ethical_crawling=EthicalCrawlingConfig(respect_robots_txt=True),
        browser=BrowserConfig(storage_state_path=state_file),
    )
    async with ScrapeFlow(config_with_state) as scraper:
        await scraper.navigate("https://quotes.toscrape.com/")
        extractor = SpecificationExtractor(QuotesPage, schema=schema)
        data = await extractor.extract(scraper.page)
        print(f"Loaded session: extracted {len(data.quotes)} quotes (authenticated)")


if __name__ == "__main__":
    asyncio.run(run_session_example())
