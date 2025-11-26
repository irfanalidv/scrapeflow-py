"""Data extraction utilities and helpers."""

from typing import Any, Dict, List, Optional, Union
from playwright.async_api import Page, Locator


class Extractor:
    """Base class for data extractors."""

    @staticmethod
    async def extract_text(page: Page, selector: str) -> Optional[str]:
        """Extract text from an element."""
        try:
            element = page.locator(selector).first
            if await element.count() > 0:
                return await element.text_content()
            return None
        except Exception:
            return None

    @staticmethod
    async def extract_texts(page: Page, selector: str) -> List[str]:
        """Extract text from multiple elements."""
        try:
            elements = page.locator(selector)
            count = await elements.count()
            texts = []
            for i in range(count):
                text = await elements.nth(i).text_content()
                if text:
                    texts.append(text.strip())
            return texts
        except Exception:
            return []

    @staticmethod
    async def extract_attribute(
        page: Page, selector: str, attribute: str
    ) -> Optional[str]:
        """Extract an attribute value from an element."""
        try:
            element = page.locator(selector).first
            if await element.count() > 0:
                return await element.get_attribute(attribute)
            return None
        except Exception:
            return None

    @staticmethod
    async def extract_attributes(
        page: Page, selector: str, attribute: str
    ) -> List[str]:
        """Extract attribute values from multiple elements."""
        try:
            elements = page.locator(selector)
            count = await elements.count()
            attributes = []
            for i in range(count):
                attr = await elements.nth(i).get_attribute(attribute)
                if attr:
                    attributes.append(attr)
            return attributes
        except Exception:
            return []

    @staticmethod
    async def extract_html(page: Page, selector: str) -> Optional[str]:
        """Extract HTML content from an element."""
        try:
            element = page.locator(selector).first
            if await element.count() > 0:
                return await element.inner_html()
            return None
        except Exception:
            return None

    @staticmethod
    async def extract_json(page: Page, selector: str = "body") -> Optional[Dict]:
        """Extract JSON from a script tag or parse JSON from page."""
        try:
            # Try to find JSON in script tags
            scripts = page.locator("script[type='application/json']")
            count = await scripts.count()
            if count > 0:
                json_text = await scripts.first.text_content()
                import json

                return json.loads(json_text)

            # Try to extract JSON-LD
            json_ld = page.locator('script[type="application/ld+json"]')
            count = await json_ld.count()
            if count > 0:
                json_text = await json_ld.first.text_content()
                import json

                return json.loads(json_text)

            return None
        except Exception:
            return None

    @staticmethod
    async def extract_table(
        page: Page, selector: str = "table"
    ) -> List[Dict[str, Any]]:
        """Extract data from an HTML table."""
        try:
            table = page.locator(selector).first
            if await table.count() == 0:
                return []

            # Extract headers
            headers = []
            header_rows = table.locator("thead tr, tr").first
            header_cells = header_rows.locator("th, td")
            header_count = await header_cells.count()
            for i in range(header_count):
                header_text = await header_cells.nth(i).text_content()
                headers.append(header_text.strip() if header_text else f"col_{i}")

            # Extract rows
            rows = []
            body_rows = table.locator("tbody tr, tr").all()
            if not body_rows:
                body_rows = [header_rows]

            for row in body_rows[1:] if len(body_rows) > 1 else body_rows:
                cells = row.locator("td, th")
                cell_count = await cells.count()
                row_data = {}
                for i in range(min(cell_count, len(headers))):
                    cell_text = await cells.nth(i).text_content()
                    row_data[headers[i]] = cell_text.strip() if cell_text else ""
                if row_data:
                    rows.append(row_data)

            return rows
        except Exception:
            return []

    @staticmethod
    async def extract_links(page: Page, selector: str = "a") -> List[Dict[str, str]]:
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
        except Exception:
            return []

    @staticmethod
    async def extract_images(page: Page, selector: str = "img") -> List[Dict[str, str]]:
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
        except Exception:
            return []

    @staticmethod
    async def wait_and_extract(
        page: Page, selector: str, timeout: float = 30000
    ) -> Optional[str]:
        """Wait for element and extract text."""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return await Extractor.extract_text(page, selector)
        except Exception:
            return None


class StructuredExtractor:
    """Extract structured data using a schema."""

    def __init__(self, schema: Dict[str, Union[str, Dict]]):
        self.schema = schema

    async def extract(self, page: Page) -> Dict[str, Any]:
        """Extract data according to the schema."""
        result = {}
        for key, selector in self.schema.items():
            if isinstance(selector, dict):
                # Nested extraction
                if "selector" in selector:
                    extractor_type = selector.get("type", "text")
                    if extractor_type == "text":
                        result[key] = await Extractor.extract_text(
                            page, selector["selector"]
                        )
                    elif extractor_type == "attribute":
                        attr = selector.get("attribute", "href")
                        result[key] = await Extractor.extract_attribute(
                            page, selector["selector"], attr
                        )
                    elif extractor_type == "texts":
                        result[key] = await Extractor.extract_texts(
                            page, selector["selector"]
                        )
                elif "items" in selector:
                    # Extract list of items
                    items = []
                    item_elements = page.locator(selector["items"])
                    count = await item_elements.count()
                    for i in range(count):
                        item_page = item_elements.nth(i)
                        item_data = {}
                        for item_key, item_selector in selector.get(
                            "schema", {}
                        ).items():
                            if isinstance(item_selector, str):
                                item_data[item_key] = await Extractor.extract_text(
                                    item_page, item_selector
                                )
                        items.append(item_data)
                    result[key] = items
            else:
                # Simple text extraction
                result[key] = await Extractor.extract_text(page, selector)

        return result

