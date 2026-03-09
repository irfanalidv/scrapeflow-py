"""
Pagination helpers for multi-page extraction.

Control max_pages, max_results, and max_wait_time for multi-page crawls.
"""

import time
from typing import Any, AsyncIterator, Callable, Optional

from scrapeflow.registry import PaginationHandler


async def paginate(
    engine: Any,
    base_url: str,
    handler: PaginationHandler,
    extract_func: Callable,
    config: Optional[Any] = None,
) -> AsyncIterator[Any]:
    """
    Paginate through pages, yielding extracted data per page.

    Args:
        engine: ScrapeFlow instance
        base_url: First page URL
        handler: PaginationHandler with next_selector, has_next
        extract_func: Async function(page, context) -> extracted data
        config: Optional PaginationConfig (max_pages, max_results, max_wait_time)

    Yields:
        Extracted data from each page
    """
    config = config or type("Config", (), {"max_pages": 100, "max_results": None, "max_wait_time": None})()
    max_pages = getattr(config, "max_pages", 100)
    max_results = getattr(config, "max_results", None)
    max_wait_time = getattr(config, "max_wait_time", None)

    url = base_url
    page_count = 0
    total_results = 0
    start_time = time.time()

    while page_count < max_pages:
        if max_wait_time and (time.time() - start_time) > max_wait_time:
            break
        if max_results and total_results >= max_results:
            break

        await engine.navigate(url)
        data = await extract_func(engine.page, {"url": url})
        yield data

        if isinstance(data, list):
            total_results += len(data)
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    total_results += len(v)
                    break

        page_count += 1

        # Check for next page
        has_next = True
        if handler.has_next:
            count = await engine.page.locator(handler.has_next).count()
            has_next = count > 0

        if not has_next:
            break

        next_el = engine.page.locator(handler.next_selector).first
        if await next_el.count() == 0:
            break

        href = await next_el.get_attribute("href")
        if not href:
            break

        from urllib.parse import urljoin
        url = urljoin(url, href)
