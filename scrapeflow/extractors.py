"""Data extraction utilities and helpers.

The ``Extractor`` helpers are best-effort by design: a missing element or a Playwright error
returns ``None`` (or an empty list) instead of raising, so one absent field never aborts a
whole page. The underlying error is logged at DEBUG level on the ``scrapeflow.extractors``
logger; enable it to see why a field came back empty.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Union

from playwright.async_api import Locator, Page

logger = logging.getLogger(__name__)

# Page and Locator both have .locator() - support both for nested extraction
PageOrLocator = Union[Page, Locator]  # noqa: UP007 - runtime alias must work on 3.10


def _log_failure(method: str, selector: str, exc: Exception) -> None:
    logger.debug("Extractor.%s(%r) failed: %s", method, selector, exc)


class Extractor:
    """Base class for data extractors."""

    @staticmethod
    async def extract_text(page_or_locator: PageOrLocator, selector: str) -> str | None:
        """Extract text from an element."""
        try:
            element = page_or_locator.locator(selector).first
            if await element.count() > 0:
                return await element.text_content()
            return None
        except Exception as exc:
            _log_failure("extract_text", selector, exc)
            return None

    @staticmethod
    async def extract_texts(page_or_locator: PageOrLocator, selector: str) -> list[str]:
        """Extract text from multiple elements."""
        try:
            elements = page_or_locator.locator(selector)
            count = await elements.count()
            texts = []
            for i in range(count):
                text = await elements.nth(i).text_content()
                if text:
                    texts.append(text.strip())
            return texts
        except Exception as exc:
            _log_failure("extract_texts", selector, exc)
            return []

    @staticmethod
    async def extract_attribute(
        page_or_locator: PageOrLocator, selector: str, attribute: str
    ) -> str | None:
        """Extract an attribute value from an element."""
        try:
            element = page_or_locator.locator(selector).first
            if await element.count() > 0:
                return await element.get_attribute(attribute)
            return None
        except Exception as exc:
            _log_failure("extract_attribute", selector, exc)
            return None

    @staticmethod
    async def extract_attributes(
        page_or_locator: PageOrLocator, selector: str, attribute: str
    ) -> list[str]:
        """Extract attribute values from multiple elements."""
        try:
            elements = page_or_locator.locator(selector)
            count = await elements.count()
            attributes = []
            for i in range(count):
                attr = await elements.nth(i).get_attribute(attribute)
                if attr:
                    attributes.append(attr)
            return attributes
        except Exception as exc:
            _log_failure("extract_attributes", selector, exc)
            return []

    @staticmethod
    async def extract_html(page_or_locator: PageOrLocator, selector: str) -> str | None:
        """Extract HTML content from an element."""
        try:
            element = page_or_locator.locator(selector).first
            if await element.count() > 0:
                return await element.inner_html()
            return None
        except Exception as exc:
            _log_failure("extract_html", selector, exc)
            return None

    @staticmethod
    async def extract_json(page: Page, selector: str = "body") -> Any | None:
        """Parse the first ``application/json`` script, else the first JSON-LD script.

        ``selector`` is accepted for backward compatibility and is not used.
        """
        try:
            for script_selector in (
                "script[type='application/json']",
                'script[type="application/ld+json"]',
            ):
                scripts = page.locator(script_selector)
                if await scripts.count() > 0:
                    json_text = await scripts.first.text_content()
                    return json.loads(json_text or "null")
            return None
        except Exception as exc:
            _log_failure("extract_json", selector, exc)
            return None

    @staticmethod
    async def extract_table(page: Page, selector: str = "table") -> list[dict[str, Any]]:
        """Extract data from an HTML table."""
        try:
            table = page.locator(selector).first
            if await table.count() == 0:
                return []

            # Extract headers
            headers: list[str] = []
            header_row = table.locator("tr").first
            header_cells = header_row.locator("th, td")
            header_count = await header_cells.count()
            for i in range(header_count):
                header_text = await header_cells.nth(i).text_content()
                headers.append(header_text.strip() if header_text else f"col_{i}")

            # Extract data rows: every row after the header row. (Before 0.5.0 the coroutine
            # returned by ``.all()`` was never awaited, so this method always returned [].)
            rows: list[dict[str, Any]] = []
            all_rows = await table.locator("tr").all()
            for row in all_rows[1:]:
                cells = row.locator("td, th")
                cell_count = await cells.count()
                row_data: dict[str, str] = {}
                for i in range(min(cell_count, len(headers))):
                    cell_text = await cells.nth(i).text_content()
                    row_data[headers[i]] = cell_text.strip() if cell_text else ""
                if row_data:
                    rows.append(row_data)

            return rows
        except Exception as exc:
            _log_failure("extract_table", selector, exc)
            return []

    @staticmethod
    async def extract_links(page: Page, selector: str = "a") -> list[dict[str, str]]:
        """Extract links with href and text."""
        try:
            links = []
            elements = page.locator(selector)
            count = await elements.count()
            for i in range(count):
                element = elements.nth(i)
                href = await element.get_attribute("href")
                text = await element.text_content()
                if href:
                    links.append({"href": href, "text": text.strip() if text else ""})
            return links
        except Exception as exc:
            _log_failure("extract_links", selector, exc)
            return []

    @staticmethod
    async def extract_images(page: Page, selector: str = "img") -> list[dict[str, str]]:
        """Extract images with src and alt."""
        try:
            images = []
            elements = page.locator(selector)
            count = await elements.count()
            for i in range(count):
                element = elements.nth(i)
                src = await element.get_attribute("src")
                alt = await element.get_attribute("alt")
                images.append({"src": src or "", "alt": alt or ""})
            return images
        except Exception as exc:
            _log_failure("extract_images", selector, exc)
            return []

    @staticmethod
    async def wait_and_extract(page: Page, selector: str, timeout: float = 30000) -> str | None:
        """Wait for element and extract text."""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return await Extractor.extract_text(page, selector)
        except Exception as exc:
            _log_failure("wait_and_extract", selector, exc)
            return None


async def _extract_by_type(target: PageOrLocator, spec: dict[str, Any]) -> Any:
    """Extract one value described by ``{"selector": ..., "type": ..., "attribute": ...}``."""
    extractor_type = spec.get("type", "text")
    sel = spec["selector"]
    if extractor_type == "attribute":
        return await Extractor.extract_attribute(target, sel, spec.get("attribute", "href"))
    if extractor_type == "texts":
        return await Extractor.extract_texts(target, sel)
    if extractor_type == "html":
        return await Extractor.extract_html(target, sel)
    return await Extractor.extract_text(target, sel)


class StructuredExtractor:
    """Extract structured data using a schema."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema

    async def extract(self, page: Page) -> dict[str, Any]:
        """Extract data according to the schema.

        Schema values may be a CSS selector string (first match's text), a dict with
        ``selector`` and optional ``type`` (``text`` / ``texts`` / ``attribute``) and
        ``attribute``, or a dict with ``items`` (a selector for repeated elements) and
        ``schema`` (per-item field selectors, which accept the same forms).
        """
        result: dict[str, Any] = {}
        for key, selector in self.schema.items():
            if isinstance(selector, dict):
                # Nested extraction
                if "selector" in selector:
                    result[key] = await _extract_by_type(page, selector)
                elif "items" in selector:
                    # Extract list of items
                    items = []
                    item_elements = page.locator(selector["items"])
                    count = await item_elements.count()
                    for i in range(count):
                        item_page = item_elements.nth(i)
                        item_data: dict[str, Any] = {}
                        for item_key, item_selector in selector.get("schema", {}).items():
                            if isinstance(item_selector, str):
                                item_data[item_key] = await Extractor.extract_text(
                                    item_page, item_selector
                                )
                            elif isinstance(item_selector, dict) and "selector" in item_selector:
                                item_data[item_key] = await _extract_by_type(
                                    item_page, item_selector
                                )
                        items.append(item_data)
                    result[key] = items
            else:
                # Simple text extraction
                result[key] = await Extractor.extract_text(page, selector)

        return result
