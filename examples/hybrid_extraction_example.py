"""
Hybrid extraction: selectors first, LLM fallback when validation fails.

Demonstrates:
- SpecificationExtractor with selector-based extraction
- HybridExtractor: tries selectors, falls back to Mistral when needed
- Content cleaning for LLM (scripts/styles stripped)

Requires MISTRAL_API_KEY in .env for LLM fallback.
"""

import asyncio
import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pydantic import BaseModel, Field
from scrapeflow import ScrapeFlow, HybridExtractor, SpecificationExtractor
from scrapeflow.config import ScrapeFlowConfig, EthicalCrawlingConfig
from scrapeflow.specifications import FieldSpec


class ProductSpec(BaseModel):
    """Single product page model."""

    title: str = Field(..., description="Product title")
    price: str = Field(..., description="Price string")
    availability: Optional[str] = Field(None, description="Stock status")


async def run_hybrid_example():
    """Extract product from books.toscrape using hybrid approach."""
    config = ScrapeFlowConfig(
        ethical_crawling=EthicalCrawlingConfig(respect_robots_txt=True),
    )

    # Schema with fallback selectors - tries .product_main h1, then h1, then title
    schema = {
        "title": FieldSpec(selector=[".product_main h1", "h1", "title"]),
        "price": FieldSpec(selector=[".price_color", ".product_price .price"]),
        "availability": FieldSpec(selector=[".availability", ".instock"]),
    }

    async with ScrapeFlow(config) as scraper:
        await scraper.navigate("https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html")

        # Use HybridExtractor: selectors first, LLM fallback if validation fails
        use_llm = bool(os.environ.get("MISTRAL_API_KEY"))
        extractor = HybridExtractor(
            ProductSpec,
            schema=schema,
            use_llm_fallback=use_llm,
        )
        data = await extractor.extract(scraper.page)

        print("Extracted (selector or LLM):")
        print(f"  Title: {data.title}")
        print(f"  Price: {data.price}")
        print(f"  Availability: {data.availability}")


if __name__ == "__main__":
    asyncio.run(run_hybrid_example())
