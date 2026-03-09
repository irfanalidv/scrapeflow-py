"""
MCP (Model Context Protocol) integration extensibility.

Provides hooks for integrating with MCP servers (e.g. Scrapy MCP Server,
Playwright MCP) for self-healing spiders and LLM-augmented extraction.

Spiders can rely on field descriptions rather than fragile XPaths when
using semantic extraction backends.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from playwright.async_api import Page


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
        field_descriptions: Dict[str, str],
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        pass

    @abstractmethod
    async def detect_layout_change(
        self, page: Page, expected_selectors: list[str]
    ) -> Dict[str, bool]:
        """
        Detect if page layout has changed (selectors no longer match).

        Used by self-healing spiders to trigger repair workflows.

        Args:
            page: Playwright page.
            expected_selectors: List of selectors that should be present.

        Returns:
            Map of selector -> True if found, False if missing.
        """
        pass

    @abstractmethod
    async def suggest_repair(
        self,
        page: Page,
        failed_selectors: list[str],
        field_descriptions: Dict[str, str],
    ) -> Optional[Dict[str, str]]:
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
        pass


class PlaceholderMCPBackend(MCPBackend):
    """
    Placeholder implementation for when no MCP server is configured.

    Falls back to no-op; actual integration would use scrapy-mcp-server,
    playwright-mcp, or similar.
    """

    async def extract_with_semantics(
        self,
        page: Page,
        field_descriptions: Dict[str, str],
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """No-op; override with real MCP/LLM integration."""
        return {}

    async def detect_layout_change(
        self, page: Page, expected_selectors: list[str]
    ) -> Dict[str, bool]:
        """Basic check: locator.count() > 0."""
        result = {}
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
        field_descriptions: Dict[str, str],
    ) -> Optional[Dict[str, str]]:
        """No-op; real implementation would call MCP tools."""
        return None


def create_mcp_backend(backend_type: str = "placeholder", **kwargs) -> MCPBackend:
    """
    Factory for MCP backends.

    Args:
        backend_type: "placeholder" | "scrapy_mcp" | "playwright_mcp" | "llm"
        **kwargs: Backend-specific config (api_key, server_url, etc.)

    Returns:
        MCPBackend instance.
    """
    if backend_type == "placeholder":
        return PlaceholderMCPBackend()
    # Future: elif backend_type == "scrapy_mcp": return ScrapyMCPBackend(**kwargs)
    # Future: elif backend_type == "playwright_mcp": return PlaywrightMCPBackend(**kwargs)
    return PlaceholderMCPBackend()
