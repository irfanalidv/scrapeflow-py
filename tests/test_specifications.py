"""Tests for specification-driven extraction."""

import pytest
from pydantic import BaseModel, Field

from scrapeflow.specifications import (
    FieldSpec,
    ItemSpec,
    SpecificationExtractor,
    ProductPriceSpec,
    JobListingSpec,
)


def test_field_spec():
    """Test FieldSpec model."""
    spec = FieldSpec(selector=".price", type="text")
    assert spec.selector == ".price"
    assert spec.type == "text"


def test_field_spec_fallback_selectors():
    """Test FieldSpec with fallback selector list."""
    spec = FieldSpec(selector=[".price", ".cost", "span.price-tag"], type="text")
    assert spec.selector == [".price", ".cost", "span.price-tag"]


def test_item_spec():
    """Test ItemSpec model."""
    spec = ItemSpec(
        items_selector=".product",
        fields={"title": "h2", "price": FieldSpec(selector=".price")},
    )
    assert spec.items_selector == ".product"
    assert "title" in spec.fields
    assert "price" in spec.fields


def test_product_price_spec_model():
    """Test ProductPriceSpec Pydantic model."""
    data = {"title": "Book", "price": "£10.99", "availability": "In stock"}
    obj = ProductPriceSpec.model_validate(data)
    assert obj.title == "Book"
    assert obj.price == "£10.99"
    assert obj.availability == "In stock"


def test_job_listing_spec_model():
    """Test JobListingSpec Pydantic model."""
    data = {"title": "Data Engineer", "company": "PST.AG", "location": "Remote"}
    obj = JobListingSpec.model_validate(data)
    assert obj.title == "Data Engineer"
    assert obj.company == "PST.AG"
    assert obj.location == "Remote"
