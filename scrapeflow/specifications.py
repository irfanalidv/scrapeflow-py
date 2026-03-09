"""
Specification-driven extraction using Pydantic models.

Declarative extraction specifications that describe exactly which fields to capture,
their types, and validation rules. Aligns with specification-driven extraction
best practices for decoupling field definitions from page structure.
"""

import re
from urllib.parse import urljoin
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel, Field, field_validator
from playwright.async_api import Page, Locator

from scrapeflow.extractors import Extractor
from scrapeflow.exceptions import ScrapeFlowValidationError


T = TypeVar("T", bound=BaseModel)


class FieldSpec(BaseModel):
    """Declarative specification for a single extraction field."""

    selector: str
    type: str = "text"  # text, attribute, texts, html, json
    attribute: Optional[str] = None
    default: Optional[Any] = None
    required: bool = False
    normalize_whitespace: bool = True
    strip: bool = True
    resolve_relative_url: bool = False
    fallback_attribute: Optional[str] = None
    prefer_attribute: Optional[str] = None


class ItemSpec(BaseModel):
    """Specification for extracting a list of items."""

    items_selector: str
    fields: Dict[str, Union[str, FieldSpec]]  # field name -> selector/spec


def _field_spec_to_extractor_args(spec: Union[str, FieldSpec]) -> Dict[str, Any]:
    """Convert FieldSpec or string to extractor arguments."""
    if isinstance(spec, str):
        return {"selector": spec, "type": "text"}
    return {
        "selector": spec.selector,
        "type": spec.type,
        "attribute": spec.attribute,
        "default": spec.default,
        "normalize_whitespace": spec.normalize_whitespace,
        "strip": spec.strip,
        "resolve_relative_url": spec.resolve_relative_url,
        "fallback_attribute": spec.fallback_attribute,
        "prefer_attribute": spec.prefer_attribute,
    }


async def _extract_from_locator(
    locator: Locator, spec: Union[str, FieldSpec], base_url: Optional[str] = None
) -> Any:
    """Extract value from a locator using field spec."""
    args = _field_spec_to_extractor_args(spec)
    selector = args["selector"]
    extract_type = args.get("type", "text")
    attribute = args.get("attribute")
    default = args.get("default")
    normalize_whitespace = args.get("normalize_whitespace", True)
    strip = args.get("strip", True)
    resolve_relative_url = args.get("resolve_relative_url", False)
    fallback_attribute = args.get("fallback_attribute")
    prefer_attribute = args.get("prefer_attribute")

    try:
        if extract_type == "text":
            if prefer_attribute:
                val = await Extractor.extract_attribute(locator, selector, prefer_attribute)
            else:
                val = None
            if val is None:
                val = await Extractor.extract_text(locator, selector)
            if not val and fallback_attribute:
                val = await Extractor.extract_attribute(locator, selector, fallback_attribute)
        elif extract_type == "texts":
            val = await Extractor.extract_texts(locator, selector)
        elif extract_type == "attribute":
            val = await Extractor.extract_attribute(
                locator, selector, attribute or "href"
            )
        elif extract_type == "html":
            val = await Extractor.extract_html(locator, selector)
        else:
            val = await Extractor.extract_text(locator, selector)

        if isinstance(val, str):
            if strip:
                val = val.strip()
            if normalize_whitespace:
                val = re.sub(r"\s+", " ", val).strip()
            if resolve_relative_url and base_url:
                val = urljoin(base_url, val)

        if isinstance(val, list) and normalize_whitespace:
            normalized = []
            for item in val:
                if isinstance(item, str):
                    s = item.strip() if strip else item
                    normalized.append(re.sub(r"\s+", " ", s).strip())
                else:
                    normalized.append(item)
            val = normalized

        return val if val is not None else default
    except Exception:
        return default


class SpecificationExtractor:
    """
    Extract and validate data using Pydantic model specifications.

    Decouples field definitions from page structure—spiders rely on field
    descriptions and validation rules, not fragile XPaths alone.
    """

    def __init__(
        self,
        model: Type[T],
        schema: Optional[Dict[str, Union[str, FieldSpec, ItemSpec]]] = None,
        strict: bool = True,
    ):
        """
        Args:
            model: Pydantic model for validation and type safety.
            schema: Optional explicit schema mapping field names to selectors.
                    If None, uses model's field aliases or names.
            strict: If True, raise ScrapeFlowValidationError on validation failure.
        """
        self.model = model
        self.schema = schema or {}
        self.strict = strict

    async def extract(self, page: Page) -> T:
        """Extract data from page and validate against the Pydantic model."""
        raw = await self._extract_raw(page)
        return self._validate(raw)

    async def _extract_raw(self, page: Page) -> Dict[str, Any]:
        """Extract raw data from page using schema."""
        result: Dict[str, Any] = {}

        for key, spec in self.schema.items():
            if isinstance(spec, ItemSpec):
                items = []
                item_elements = page.locator(spec.items_selector)
                count = await item_elements.count()
                for i in range(count):
                    item_locator = item_elements.nth(i)
                    item_data = {}
                    for item_key, item_spec in spec.fields.items():
                        item_data[item_key] = await _extract_from_locator(
                            item_locator, item_spec, base_url=page.url
                        )
                    items.append(item_data)
                result[key] = items
            else:
                result[key] = await _extract_from_locator(page, spec, base_url=page.url)

        return result

    def _validate(self, raw: Dict[str, Any]) -> T:
        """Validate raw data against Pydantic model."""
        try:
            return self.model.model_validate(raw)
        except Exception as e:
            if self.strict:
                raise ScrapeFlowValidationError(
                    f"Validation failed for {self.model.__name__}: {e}"
                ) from e
            raise


# Reusable specification libraries for common data types
class ProductPriceSpec(BaseModel):
    """Reusable spec for product/price extraction."""

    title: str = Field(..., description="Product title")
    price: str = Field(..., description="Price string")
    availability: Optional[str] = Field(None, description="Stock status")
    url: Optional[str] = Field(None, description="Product URL")

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, v: Any) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        return s


class JobListingSpec(BaseModel):
    """Reusable spec for job listing extraction."""

    title: str = Field(..., description="Job title")
    company: Optional[str] = Field(None, description="Company name")
    location: Optional[str] = Field(None, description="Job location")
    url: Optional[str] = Field(None, description="Job URL")
    description: Optional[str] = Field(None, description="Job description snippet")


class TariffCodeSpec(BaseModel):
    """Reusable spec for tariff/regulatory text extraction."""

    code: str = Field(..., description="Tariff or classification code")
    description: str = Field(..., description="Regulatory text description")
    source: Optional[str] = Field(None, description="Source reference")
