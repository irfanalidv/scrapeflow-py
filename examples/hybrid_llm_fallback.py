"""Self-healing extraction: selectors first, a semantic backend when the layout changes.

The demo product page was "redesigned", so the old ``.product-title`` / ``.price`` selectors
match nothing. ``HybridExtractor`` notices the validation failure and asks an ``MCPBackend``
for the fields instead, using the Pydantic field descriptions.

Shows:
  * ``HybridExtractor`` with selector-first, backend-fallback extraction
  * a custom ``MCPBackend`` (offline: reads the page's schema.org JSON-LD)
  * ``MistralLLMBackend`` as a drop-in replacement (``--live``)
  * ``detect_layout_change`` reporting which selectors broke

Needs: ``pip install scrapeflow-py`` and ``playwright install chromium``.
Offline by default (bundled demo site, no key). ``--live`` calls the Mistral API and needs
``MISTRAL_API_KEY`` in the environment or a ``.env`` file.

Run: python examples/hybrid_llm_fallback.py [--live]
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from _demo_site import serve_demo_site
from pydantic import BaseModel, Field

from scrapeflow import HybridExtractor, MCPBackend, MistralLLMBackend, ScrapeFlow
from scrapeflow.config import ScrapeFlowConfig
from scrapeflow.extractors import Extractor


class ProductInfo(BaseModel):
    name: str = Field(..., description="Product name")
    price: str = Field(..., description="Price as shown, including currency")


class JsonLdBackend(MCPBackend):
    """Offline fallback: read schema.org Product data embedded in the page."""

    async def extract_with_semantics(
        self, page: Any, field_descriptions: dict[str, str], context: str | None = None
    ) -> dict[str, Any]:
        data = await Extractor.extract_json(page) or {}
        offer = data.get("offers", {})
        return {
            "name": data.get("name", ""),
            "price": f"{offer.get('price', '')} {offer.get('priceCurrency', '')}".strip(),
        }

    async def detect_layout_change(
        self, page: Any, expected_selectors: list[str]
    ) -> dict[str, bool]:
        return {sel: await page.locator(sel).count() > 0 for sel in expected_selectors}

    async def suggest_repair(
        self, page: Any, failed_selectors: list[str], field_descriptions: dict[str, str]
    ) -> dict[str, str] | None:
        return None


SCHEMA = {"name": ".product-title", "price": ".price"}  # written for the old layout


async def main(live: bool) -> None:
    backend: MCPBackend = MistralLLMBackend() if live else JsonLdBackend()
    extractor = HybridExtractor(ProductInfo, schema=SCHEMA, mcp_backend=backend)

    with serve_demo_site() as base_url:
        async with ScrapeFlow(ScrapeFlowConfig(log_level="WARNING")) as scraper:
            await scraper.navigate(base_url + "/product-redesign.html")
            broken = await backend.detect_layout_change(scraper.page, list(SCHEMA.values()))
            print("selectors still matching:", broken)
            product = await extractor.extract(scraper.page)

    print(f"backend: {type(backend).__name__}")
    print(f"extracted: {product.model_dump()}")


if __name__ == "__main__":
    asyncio.run(main(live="--live" in sys.argv))
