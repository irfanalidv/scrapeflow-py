"""
MCP (Model Context Protocol) integration extensibility.

Provides hooks for integrating with MCP servers (e.g. Scrapy MCP Server,
Playwright MCP) for self-healing spiders and LLM-augmented extraction.

Spiders can rely on field descriptions rather than fragile XPaths when
using semantic extraction backends.
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import Page

from scrapeflow.extractors import Extractor


class MCPBackend(ABC):
    """
    Abstract base for MCP-compatible extraction backends.

    Implement this interface to integrate with:
    - Scrapy MCP Server
    - Playwright MCP
    - Custom LLM-based semantic extraction (Scrapy-LLM style)
    """

    @abstractmethod
    async def extract_with_semantics(
        self,
        page: Page,
        field_descriptions: dict[str, str],
        context: str | None = None,
    ) -> dict[str, Any]:
        """
        Extract data using semantic/LLM understanding of field descriptions.

        Args:
            page: Playwright page to extract from.
            field_descriptions: Map of field name -> human-readable description.
                               e.g. {"price": "Product price in local currency"}
            context: Optional page context or instructions for the extractor.

        Returns:
            Extracted data keyed by field name.
        """

    @abstractmethod
    async def detect_layout_change(
        self, page: Page, expected_selectors: list[str]
    ) -> dict[str, bool]:
        """
        Detect if page layout has changed (selectors no longer match).

        Used by self-healing spiders to trigger repair workflows.

        Args:
            page: Playwright page.
            expected_selectors: List of selectors that should be present.

        Returns:
            Map of selector -> True if found, False if missing.
        """

    @abstractmethod
    async def suggest_repair(
        self,
        page: Page,
        failed_selectors: list[str],
        field_descriptions: dict[str, str],
    ) -> dict[str, str] | None:
        """
        Suggest new selectors when layout has changed.

        Can use LLM or MCP tools to analyze page and propose replacements.

        Args:
            page: Playwright page.
            failed_selectors: Selectors that no longer work.
            field_descriptions: What each field represents.

        Returns:
            Map of field/selector name -> new selector, or None if repair failed.
        """


class PlaceholderMCPBackend(MCPBackend):
    """
    Placeholder implementation for when no MCP server is configured.

    Falls back to no-op; actual integration would use scrapy-mcp-server,
    playwright-mcp, or similar.
    """

    async def extract_with_semantics(
        self,
        page: Page,
        field_descriptions: dict[str, str],
        context: str | None = None,
    ) -> dict[str, Any]:
        """No-op; override with real MCP/LLM integration."""
        return {}

    async def detect_layout_change(
        self, page: Page, expected_selectors: list[str]
    ) -> dict[str, bool]:
        """Basic check: locator.count() > 0."""
        result: dict[str, bool] = {}
        for sel in expected_selectors:
            try:
                count = await page.locator(sel).count()
                result[sel] = count > 0
            except Exception:
                result[sel] = False
        return result

    async def suggest_repair(
        self,
        page: Page,
        failed_selectors: list[str],
        field_descriptions: dict[str, str],
    ) -> dict[str, str] | None:
        """No-op; real implementation would call MCP tools."""
        return None


class MistralLLMBackend(MCPBackend):
    """
    Mistral-powered semantic extraction backend.

    Uses MISTRAL_API_KEY from .env. Extracts data from page content
    using field descriptions—no selectors required.
    """

    def __init__(self, model: str = "mistral-small-latest") -> None:
        self.model = model

    async def extract_with_semantics(
        self,
        page: Page,
        field_descriptions: dict[str, str],
        context: str | None = None,
    ) -> dict[str, Any]:
        """Extract using LLM: get page content, clean for LLM, build schema, call Mistral."""
        from scrapeflow.content_utils import clean_html_for_llm
        from scrapeflow.llm_extract import extract_with_schema_async

        # Get page content
        content = await Extractor.extract_text(page, "body")
        if not content:
            html = await Extractor.extract_html(page, "body")
            content = html or ""
        content = clean_html_for_llm(content)

        # Build schema from field descriptions (all strings by default)
        schema = {
            "type": "object",
            "properties": {
                k: {"type": "string", "description": v} for k, v in field_descriptions.items()
            },
            "required": list(field_descriptions.keys()),
        }

        prompt = context or "Extract the following fields from the page content."
        return await extract_with_schema_async(content, schema, prompt=prompt, model=self.model)

    async def detect_layout_change(
        self, page: Page, expected_selectors: list[str]
    ) -> dict[str, bool]:
        """Basic selector presence check."""
        result: dict[str, bool] = {}
        for sel in expected_selectors:
            try:
                count = await page.locator(sel).count()
                result[sel] = count > 0
            except Exception:
                result[sel] = False
        return result

    async def suggest_repair(
        self,
        page: Page,
        failed_selectors: list[str],
        field_descriptions: dict[str, str],
    ) -> dict[str, str] | None:
        """Use LLM to suggest new selectors from page HTML."""
        from scrapeflow.llm_extract import extract_with_schema_async

        html = await Extractor.extract_html(page, "body")
        if not html:
            return None

        schema = {
            "type": "object",
            "properties": {
                f"selector_for_{k}": {"type": "string", "description": f"CSS selector for: {v}"}
                for k, v in field_descriptions.items()
            },
            "required": [f"selector_for_{k}" for k in field_descriptions],
        }
        prompt = (
            f"Failed selectors: {failed_selectors}. Suggest new CSS selectors that would "
            "extract these fields from the HTML. Return only valid CSS selectors."
        )
        result = await extract_with_schema_async(
            html[:60000], schema, prompt=prompt, model=self.model
        )
        return result if result else None


def create_mcp_backend(backend_type: str = "placeholder", **kwargs: Any) -> MCPBackend:
    """
    Factory for MCP backends.

    Args:
        backend_type: "placeholder" | "mistral" | "scrapy_mcp" | "playwright_mcp"
        **kwargs: Backend-specific config (model, api_key, etc.)

    Returns:
        MCPBackend instance.
    """
    if backend_type == "placeholder":
        return PlaceholderMCPBackend()
    if backend_type == "mistral":
        return MistralLLMBackend(model=kwargs.get("model", "mistral-small-latest"))
    if backend_type in ("scrapy_mcp", "playwright_mcp"):
        warnings.warn(
            f"MCP backend {backend_type!r} is not implemented yet; using PlaceholderMCPBackend "
            "(extraction returns no data). Subclass MCPBackend to plug in your own server.",
            UserWarning,
            stacklevel=2,
        )
        return PlaceholderMCPBackend()
    raise ValueError(
        f"Unknown MCP backend {backend_type!r}. "
        "Expected 'placeholder', 'mistral', 'scrapy_mcp' or 'playwright_mcp'."
    )
