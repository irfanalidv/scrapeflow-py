"""
Component-based extraction platform: shared selectors, login handlers, pagination.

Move beyond one-off scrapers: selectors and handlers are versioned, tested,
and reusable across extraction jobs.
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass

from scrapeflow.schema_library import product_price_item_spec, job_listing_item_spec


@dataclass
class SelectorComponent:
    """A reusable selector or extraction component."""

    name: str
    selector: str
    type: str = "text"  # text, attribute, texts, html
    attribute: Optional[str] = None
    description: str = ""
    version: str = "1.0"


@dataclass
class PaginationHandler:
    """Reusable pagination logic."""

    name: str
    next_selector: str
    has_next: Optional[str] = None  # selector that indicates more pages
    max_pages: int = 100
    description: str = ""
    version: str = "1.0"


@dataclass
class LoginHandler:
    """Reusable login flow component."""

    name: str
    username_selector: str
    password_selector: str
    submit_selector: str
    success_selector: Optional[str] = None
    description: str = ""
    version: str = "1.0"


class SelectorRegistry:
    """
    Central registry for shared selectors and extraction components.

    Enables platform thinking: selectors are shared, versioned, and tested
    across multiple extraction jobs.
    """

    def __init__(self):
        self._selectors: Dict[str, SelectorComponent] = {}
        self._pagination: Dict[str, PaginationHandler] = {}
        self._login: Dict[str, LoginHandler] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register_selector(
        self,
        name: str,
        selector: str,
        type: str = "text",
        attribute: Optional[str] = None,
        description: str = "",
        version: str = "1.0",
    ) -> "SelectorRegistry":
        """Register a reusable selector."""
        self._selectors[name] = SelectorComponent(
            name=name,
            selector=selector,
            type=type,
            attribute=attribute,
            description=description,
            version=version,
        )
        return self

    def register_pagination(
        self,
        name: str,
        next_selector: str,
        has_next: Optional[str] = None,
        max_pages: int = 100,
        description: str = "",
        version: str = "1.0",
    ) -> "SelectorRegistry":
        """Register a reusable pagination handler."""
        self._pagination[name] = PaginationHandler(
            name=name,
            next_selector=next_selector,
            has_next=has_next,
            max_pages=max_pages,
            description=description,
            version=version,
        )
        return self

    def register_login(
        self,
        name: str,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
        success_selector: Optional[str] = None,
        description: str = "",
        version: str = "1.0",
    ) -> "SelectorRegistry":
        """Register a reusable login handler."""
        self._login[name] = LoginHandler(
            name=name,
            username_selector=username_selector,
            password_selector=password_selector,
            submit_selector=submit_selector,
            success_selector=success_selector,
            description=description,
            version=version,
        )
        return self

    def register_schema(self, name: str, schema: Dict[str, Any]) -> "SelectorRegistry":
        """Register a reusable extraction schema."""
        self._schemas[name] = schema
        return self

    def get_selector(self, name: str) -> Optional[SelectorComponent]:
        """Get a registered selector by name."""
        return self._selectors.get(name)

    def get_pagination(self, name: str) -> Optional[PaginationHandler]:
        """Get a registered pagination handler by name."""
        return self._pagination.get(name)

    def get_login(self, name: str) -> Optional[LoginHandler]:
        """Get a registered login handler by name."""
        return self._login.get(name)

    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a registered schema by name."""
        return self._schemas.get(name)

    def list_selectors(self) -> list[str]:
        """List all registered selector names."""
        return list(self._selectors.keys())

    def list_schemas(self) -> list[str]:
        """List all registered schema names."""
        return list(self._schemas.keys())


# Global default registry
_default_registry = SelectorRegistry()


def get_registry() -> SelectorRegistry:
    """Get the default global registry."""
    return _default_registry


# Pre-built specification libraries for common data types
def register_product_price_schema(registry: Optional[SelectorRegistry] = None) -> None:
    """Register the product/price schema to the registry."""
    reg = registry or _default_registry
    reg.register_schema("product_price", {"products": product_price_item_spec()})


def register_job_listing_schema(registry: Optional[SelectorRegistry] = None) -> None:
    """Register the job listing schema to the registry."""
    reg = registry or _default_registry
    reg.register_schema("job_listing", {"jobs": job_listing_item_spec()})


def register_quotes_login_handler(registry: Optional[SelectorRegistry] = None) -> None:
    """Register a reusable login handler for quotes.toscrape.com."""
    reg = registry or _default_registry
    reg.register_login(
        name="quotes_login",
        username_selector='input[name="username"]',
        password_selector='input[name="password"]',
        submit_selector='input[type="submit"]',
        success_selector='a[href="/logout"]',
        description="Reusable login handler for quotes.toscrape.com",
    )
