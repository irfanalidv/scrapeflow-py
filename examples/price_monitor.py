"""Price monitoring: crawl a paginated catalogue into validated Pydantic records.

Shows:
  * ``SpecificationExtractor`` with ``ItemSpec`` / ``FieldSpec`` (selector fallback chain,
    attribute preference, relative-URL resolution, defaults)
  * a Pydantic validator that turns "£18.40" into ``18.4``
  * ``paginate()`` following "next" links with a registered ``PaginationHandler``
  * CSV export of the result

Needs: ``pip install scrapeflow-py`` and ``playwright install chromium``.
No internet and no API key: it crawls the bundled demo site on 127.0.0.1.

Run: python examples/price_monitor.py
"""

from __future__ import annotations

import asyncio
import csv
import sys
from typing import Any

from _demo_site import serve_demo_site
from pydantic import BaseModel, field_validator

from scrapeflow import ScrapeFlow, SpecificationExtractor
from scrapeflow.config import RateLimitConfig, ScrapeFlowConfig
from scrapeflow.pagination import paginate
from scrapeflow.registry import SelectorRegistry
from scrapeflow.specifications import FieldSpec, ItemSpec


class Book(BaseModel):
    title: str
    price: float
    in_stock: bool
    url: str

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, value: Any) -> float:
        return float(str(value).replace("£", "").strip())

    @field_validator("in_stock", mode="before")
    @classmethod
    def parse_stock(cls, value: Any) -> bool:
        return str(value).strip().lower() == "in stock"


class CataloguePage(BaseModel):
    books: list[Book]


SCHEMA = {
    "books": ItemSpec(
        items_selector="article.book",
        fields={
            # The link text is truncated ("A Field Guide to M..."); the title attribute is not.
            "title": FieldSpec(selector="h3 a", prefer_attribute="title"),
            # Discounted books use a different class: try .price, then .sale-price.
            "price": FieldSpec(selector=[".price", ".sale-price"]),
            "in_stock": FieldSpec(selector=".availability", default=""),
            "url": FieldSpec(
                selector="h3 a", type="attribute", attribute="href", resolve_relative_url=True
            ),
        },
    )
}


async def main() -> None:
    registry = SelectorRegistry().register_pagination(
        "demo_books", next_selector="li.next a", has_next="li.next"
    )
    pager = registry.get_pagination("demo_books")
    assert pager is not None
    extractor = SpecificationExtractor(CataloguePage, schema=SCHEMA)

    async def extract(page: Any, context: dict[str, Any]) -> list[Book]:
        return (await extractor.extract(page)).books

    config = ScrapeFlowConfig(
        rate_limit=RateLimitConfig(requests_per_second=2.0),
        log_level="WARNING",
    )
    books: list[Book] = []
    with serve_demo_site() as base_url:
        async with ScrapeFlow(config) as scraper:
            async for page_books in paginate(scraper, base_url + "/", pager, extract):
                print(f"{scraper.page.url.removeprefix(base_url)}: {len(page_books)} books")
                books.extend(page_books)

    in_stock = sorted((b for b in books if b.in_stock), key=lambda b: b.price)
    print(f"\n{len(books)} books, {len(in_stock)} in stock. Cheapest in stock:")
    for book in in_stock[:3]:
        print(f"  £{book.price:6.2f}  {book.title}")

    print("\nCSV:")
    writer = csv.writer(sys.stdout)
    writer.writerow(["title", "price", "in_stock"])
    for book in books:
        writer.writerow([book.title, f"{book.price:.2f}", book.in_stock])


if __name__ == "__main__":
    asyncio.run(main())
