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

    selector: Union[str, List[str]]  # primary selector, or list [primary, fallback1, ...]
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
        return {"selector": spec, "selectors": [spec], "type": "text"}
    sel = spec.selector
    selectors = [sel] if isinstance(sel, str) else list(sel)
    return {
        "selector": selectors[0],
        "selectors": selectors,
        "type": spec.type,
        "attribute": spec.attribute,
        "default": spec.default,
        "normalize_whitespace": spec.normalize_whitespace,
        "strip": spec.strip,
        "resolve_relative_url": spec.resolve_relative_url,
        "fallback_attribute": spec.fallback_attribute,
        "prefer_attribute": spec.prefer_attribute,
    }


async def _extract_one(
    locator: Locator,
    selector: str,
    extract_type: str,
    attribute: Optional[str],
    fallback_attribute: Optional[str],
    prefer_attribute: Optional[str],
) -> Any:
    """Extract value using a single selector."""
    if extract_type == "text":
        val = None
        if prefer_attribute:
            val = await Extractor.extract_attribute(locator, selector, prefer_attribute)
        if val is None:
            val = await Extractor.extract_text(locator, selector)
        if not val and fallback_attribute:
            val = await Extractor.extract_attribute(locator, selector, fallback_attribute)
        return val
    if extract_type == "texts":
        return await Extractor.extract_texts(locator, selector)
    if extract_type == "attribute":
        return await Extractor.extract_attribute(locator, selector, attribute or "href")
    if extract_type == "html":
        return await Extractor.extract_html(locator, selector)
    return await Extractor.extract_text(locator, selector)


async def _extract_from_locator(
    locator: Locator, spec: Union[str, FieldSpec], base_url: Optional[str] = None
) -> Any:
    """Extract value from a locator using field spec. Tries fallback selectors in order."""
    args = _field_spec_to_extractor_args(spec)
    selectors = args.get("selectors", [args["selector"]])
    extract_type = args.get("type", "text")
    attribute = args.get("attribute")
    default = args.get("default")
    normalize_whitespace = args.get("normalize_whitespace", True)
    strip = args.get("strip", True)
    resolve_relative_url = args.get("resolve_relative_url", False)
    fallback_attribute = args.get("fallback_attribute")
    prefer_attribute = args.get("prefer_attribute")

    val = None
    for selector in selectors:
        try:
            val = await _extract_one(
                locator, selector, extract_type, attribute, fallback_attribute, prefer_attribute
            )
            if val is not None and (val != "" if isinstance(val, str) else True):
                if isinstance(val, list) and len(val) == 0:
                    continue
                break
        except Exception:
            continue

    if val is None:
        return default

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


def _schema_has_item_spec(schema: Dict[str, Any]) -> bool:
    """Check if schema contains ItemSpec (list extraction)."""
    return any(isinstance(v, ItemSpec) for v in schema.values())


def _field_descriptions_from_model(
    model: Type[T], schema: Dict[str, Union[str, FieldSpec, ItemSpec]]
) -> Dict[str, str]:
    """Build field_descriptions for LLM from model and schema (single fields only)."""
    descriptions = {}
    for key in schema:
        if isinstance(schema[key], ItemSpec):
            continue
        field_info = model.model_fields.get(key)
        desc = getattr(field_info, "description", None) if field_info else None
        descriptions[key] = str(desc) if desc else key.replace("_", " ").title()
    return descriptions


class HybridExtractor:
    """
    Extract using selectors first, fall back to LLM when validation fails or result is empty.

    Best of both worlds: fast selector-based extraction with self-healing via LLM.
    Requires MISTRAL_API_KEY when LLM fallback is used.
    """

    def __init__(
        self,
        model: Type[T],
        schema: Optional[Dict[str, Union[str, FieldSpec, ItemSpec]]] = None,
        strict: bool = True,
        mcp_backend: Optional[Any] = None,
        use_llm_fallback: bool = True,
    ):
        self.spec_extractor = SpecificationExtractor(model=model, schema=schema, strict=strict)
        self.schema = schema or {}
        self.model = model
        self.use_llm_fallback = use_llm_fallback
        self._mcp = mcp_backend

    def _get_mcp(self):
        if self._mcp is not None:
            return self._mcp
        from scrapeflow.mcp_backend import create_mcp_backend
        return create_mcp_backend("mistral")

    async def extract(self, page: Page) -> T:
        """Extract: try selectors first, fall back to LLM on failure."""
        try:
            result = await self.spec_extractor.extract(page)
            # Skip fallback if we got valid result
            if result is not None:
                return result
        except ScrapeFlowValidationError:
            pass
        except Exception:
            if self.spec_extractor.strict:
                raise
            pass

        if not self.use_llm_fallback or _schema_has_item_spec(self.schema):
            raise ScrapeFlowValidationError(
                f"Selector extraction failed for {self.model.__name__} and LLM fallback disabled or schema has ItemSpec"
            )

        mcp = self._get_mcp()
        field_descriptions = _field_descriptions_from_model(self.model, self.schema)
        if not field_descriptions:
            raise ScrapeFlowValidationError(
                f"No extractable fields for LLM fallback in {self.model.__name__}"
            )

        raw = await mcp.extract_with_semantics(
            page, field_descriptions, context=f"Extract {self.model.__name__} fields."
        )
        return self.spec_extractor._validate(raw)
