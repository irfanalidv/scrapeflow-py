"""Tests for HybridExtractor."""

import pytest
from pydantic import BaseModel, Field

from scrapeflow.specifications import (
    HybridExtractor,
    FieldSpec,
    ItemSpec,
    _schema_has_item_spec,
    _field_descriptions_from_model,
)


class SimplePage(BaseModel):
    """Simple model for testing."""

    title: str = Field(..., description="Page title")
    price: str = Field(..., description="Price")


def test_hybrid_extractor_instantiation():
    """HybridExtractor can be created with schema and model."""
    schema = {"title": ".title", "price": ".price"}
    extractor = HybridExtractor(SimplePage, schema=schema, use_llm_fallback=False)
    assert extractor.spec_extractor.model == SimplePage
    assert extractor.use_llm_fallback is False


def test_schema_has_item_spec():
    """_schema_has_item_spec detects ItemSpec in schema."""
    assert _schema_has_item_spec({"a": "div", "b": "span"}) is False
    assert _schema_has_item_spec({
        "items": ItemSpec(items_selector=".x", fields={"x": "span"}),
    }) is True


def test_field_descriptions_from_model():
    """_field_descriptions_from_model builds descriptions from Pydantic model."""
    schema = {"title": ".title", "price": ".price"}
    desc = _field_descriptions_from_model(SimplePage, schema)
    assert "title" in desc
    assert "price" in desc
    assert "Page title" in desc["title"]
