"""Reusable schema/specification library."""

from scrapeflow.specifications import FieldSpec, ItemSpec


def product_price_item_spec() -> ItemSpec:
    return ItemSpec(
        items_selector="article.product_pod, .product-item, .product",
        fields={
            "title": FieldSpec(
                selector="h3 a, .title, .product-title",
                prefer_attribute="title",
                fallback_attribute="title",
            ),
            "price": FieldSpec(selector=".price_color, .price, .product-price"),
            "availability": FieldSpec(
                selector=".instock.availability, .stock, .availability",
                default="",
            ),
            "url": FieldSpec(
                selector="h3 a, .product-link",
                type="attribute",
                attribute="href",
                resolve_relative_url=True,
            ),
        },
    )


def job_listing_item_spec() -> ItemSpec:
    return ItemSpec(
        items_selector=".job-card, .job-listing, article.job, .job-item",
        fields={
            "title": FieldSpec(selector="h2 a, .job-title, .title a"),
            "company": FieldSpec(
                selector=".company, .employer, .company-name",
                default="",
            ),
            "location": FieldSpec(
                selector=".location, .job-location",
                default="",
            ),
            "url": FieldSpec(
                selector="h2 a, .job-title a, a.job-link",
                type="attribute",
                attribute="href",
            ),
        },
    )
