"""Real-browser tests against the local site in conftest.py (no internet needed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field

from scrapeflow import (
    HybridExtractor,
    ScrapeFlow,
    SpecificationExtractor,
    StructuredExtractor,
    Workflow,
)
from scrapeflow.config import (
    BrowserConfig,
    PaginationConfig,
    RateLimitConfig,
    RetryConfig,
    ScrapeFlowConfig,
)
from scrapeflow.exceptions import (
    ScrapeFlowNotStartedError,
    ScrapeFlowRobotsDisallowedError,
    ScrapeFlowValidationError,
)
from scrapeflow.extractors import Extractor
from scrapeflow.mcp_backend import MCPBackend, MistralLLMBackend, PlaceholderMCPBackend
from scrapeflow.pagination import paginate
from scrapeflow.registry import LoginHandler, SelectorRegistry
from scrapeflow.specifications import FieldSpec, ItemSpec
from tests.conftest import requires_browser

pytestmark = requires_browser


def fast_config(**overrides: Any) -> ScrapeFlowConfig:
    """Config with no rate-limit waits and a single quick retry."""
    return ScrapeFlowConfig(
        rate_limit=RateLimitConfig(requests_per_second=1000, burst_size=100),
        retry=RetryConfig(max_retries=1, initial_delay=0.01, jitter=False),
        log_level="WARNING",
        **overrides,
    )


async def test_extractor_helpers(site: str) -> None:
    async with ScrapeFlow(fast_config()) as sf:
        await sf.navigate(site + "/")
        page = sf.page
        assert page is not None

        assert await Extractor.extract_text(page, "h1") == "  Demo   Shop "
        assert await Extractor.extract_text(page, ".missing") is None
        assert await Extractor.extract_texts(page, ".tag") == ["new", "sale"]
        assert await Extractor.extract_attribute(page, "h3 a", "title") == "Alpha Book"
        assert await Extractor.extract_attribute(page, ".missing", "x") is None
        assert await Extractor.extract_attributes(page, "h3 a", "href") == ["/p/1", "/p/2"]
        assert await Extractor.extract_html(page, "#html-box") == "<b>bold</b>"
        assert await Extractor.extract_html(page, ".missing") is None
        assert await Extractor.extract_json(page) == {"@type": "Store", "name": "Demo Shop"}

        links = await Extractor.extract_links(page, "nav a")
        assert links == [
            {"href": "/page/2", "text": "Next"},
            {"href": "https://example.org/", "text": "Out"},
        ]
        assert await Extractor.extract_images(page) == [
            {"src": "/a.png", "alt": "A"},
            {"src": "/b.png", "alt": ""},
        ]
        assert await Extractor.wait_and_extract(page, "h3 a", timeout=2000) == "Alpha…"
        assert await Extractor.wait_and_extract(page, ".never", timeout=100) is None
        # Invalid selector syntax is swallowed and reported as "nothing found".
        assert await Extractor.extract_texts(page, "!!!") == []
        assert await Extractor.extract_links(page, "!!!") == []


async def test_extract_table_returns_rows(site: str) -> None:
    """Regression: extract_table always returned [] before 0.5.0 (un-awaited coroutine)."""
    async with ScrapeFlow(fast_config()) as sf:
        await sf.navigate(site + "/")
        assert sf.page is not None
        rows = await Extractor.extract_table(sf.page, "#rates")
        assert rows == [
            {"Currency": "EUR", "Rate": "1.17"},
            {"Currency": "USD", "Rate": "1.27"},
        ]
        assert await Extractor.extract_table(sf.page, "#no-table") == []


async def test_extract_json_application_json(site: str) -> None:
    async with ScrapeFlow(fast_config()) as sf:
        await sf.navigate(site + "/data")
        assert sf.page is not None
        assert await Extractor.extract_json(sf.page) == {"items": [1, 2, 3]}
        await sf.navigate(site + "/page/3")
        assert await Extractor.extract_json(sf.page) is None


async def test_structured_extractor(site: str) -> None:
    schema = {
        "title": "h1",
        "first_link": {"selector": "nav a", "type": "attribute", "attribute": "href"},
        "tags": {"selector": ".tag", "type": "texts"},
        "box": {"selector": "#html-box", "type": "html"},
        "products": {
            "items": "article.product",
            "schema": {
                "name": "h3 a",
                "link": {"selector": "h3 a", "type": "attribute", "attribute": "href"},
            },
        },
    }
    async with ScrapeFlow(fast_config()) as sf:
        await sf.navigate(site + "/")
        assert sf.page is not None
        data = await StructuredExtractor(schema).extract(sf.page)
    assert data["title"] == "  Demo   Shop "
    assert data["first_link"] == "/page/2"
    assert data["tags"] == ["new", "sale"]
    assert data["box"] == "<b>bold</b>"
    assert data["products"] == [
        {"name": "Alpha…", "link": "/p/1"},
        {"name": "Beta…", "link": "/p/2"},
    ]


class Product(BaseModel):
    title: str
    price: str
    stock: str | None = None
    url: str
    tags: list[str] = []


class Catalog(BaseModel):
    heading: str
    products: list[Product]


CATALOG_SCHEMA: dict[str, Any] = {
    "heading": FieldSpec(selector="h1"),
    "products": ItemSpec(
        items_selector="article.product",
        fields={
            "title": FieldSpec(selector="h3 a", prefer_attribute="title"),
            "price": FieldSpec(selector=[".price", ".cost"]),  # fallback chain
            "stock": FieldSpec(selector=".stock", default=None),
            "url": FieldSpec(
                selector="h3 a", type="attribute", attribute="href", resolve_relative_url=True
            ),
            "tags": FieldSpec(selector=".tag", type="texts", default=[]),
        },
    ),
}


async def test_specification_extractor(site: str) -> None:
    async with ScrapeFlow(fast_config()) as sf:
        await sf.navigate(site + "/")
        assert sf.page is not None
        catalog = await SpecificationExtractor(Catalog, schema=CATALOG_SCHEMA).extract(sf.page)
    assert catalog.heading == "Demo Shop"  # whitespace normalised
    assert [p.title for p in catalog.products] == ["Alpha Book", "Beta Book"]
    assert [p.price for p in catalog.products] == ["£10.50", "£7.25"]
    assert catalog.products[0].stock == "In stock"
    assert catalog.products[1].stock is None
    assert catalog.products[0].url == site + "/p/1"
    assert catalog.products[0].tags == ["new", "sale"]
    assert catalog.products[1].tags == []


class NeedsSku(BaseModel):
    sku: str


async def test_specification_extractor_validation_errors(site: str) -> None:
    async with ScrapeFlow(fast_config()) as sf:
        await sf.navigate(site + "/")
        assert sf.page is not None
        with pytest.raises(ScrapeFlowValidationError, match="NeedsSku"):
            await SpecificationExtractor(NeedsSku, schema={"sku": ".sku"}).extract(sf.page)
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            await SpecificationExtractor(NeedsSku, schema={"sku": ".sku"}, strict=False).extract(
                sf.page
            )


class StoreInfo(BaseModel):
    name: str = Field(..., description="Store name")


class FakeBackend(MCPBackend):
    """Offline stand-in for an LLM backend."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def extract_with_semantics(self, page, field_descriptions, context=None):  # type: ignore[no-untyped-def]
        self.calls.append(field_descriptions)
        return {"name": "Demo Shop"}

    async def detect_layout_change(self, page, expected_selectors):  # type: ignore[no-untyped-def]
        return {}

    async def suggest_repair(self, page, failed_selectors, field_descriptions):  # type: ignore[no-untyped-def]
        return None


async def test_hybrid_extractor(site: str) -> None:
    backend = FakeBackend()
    async with ScrapeFlow(fast_config()) as sf:
        await sf.navigate(site + "/")
        assert sf.page is not None

        # Selector works: no LLM call.
        ok = HybridExtractor(StoreInfo, schema={"name": "h1"}, mcp_backend=backend)
        assert (await ok.extract(sf.page)).name == "Demo Shop"
        assert backend.calls == []

        # Selector broken: falls back to the backend with the model's field description.
        broken = HybridExtractor(StoreInfo, schema={"name": ".gone"}, mcp_backend=backend)
        assert (await broken.extract(sf.page)).name == "Demo Shop"
        assert backend.calls == [{"name": "Store name"}]

        disabled = HybridExtractor(StoreInfo, schema={"name": ".gone"}, use_llm_fallback=False)
        with pytest.raises(ScrapeFlowValidationError, match="disabled"):
            await disabled.extract(sf.page)

        items = HybridExtractor(
            Catalog, schema={"products": ItemSpec(items_selector=".x", fields={})}
        )
        with pytest.raises(ScrapeFlowValidationError, match="ItemSpec"):
            await items.extract(sf.page)


async def test_mcp_backends(site: str, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_extract(content, schema, prompt=None, model="m"):  # type: ignore[no-untyped-def]
        captured.update(content=content, schema=schema, prompt=prompt, model=model)
        return (
            {"selector_for_title": "h1"}
            if "selector_for_title" in schema["properties"]
            else {"title": "Demo Shop"}
        )

    monkeypatch.setattr("scrapeflow.llm_extract.extract_with_schema_async", fake_extract)
    async with ScrapeFlow(fast_config()) as sf:
        await sf.navigate(site + "/")
        assert sf.page is not None

        placeholder = PlaceholderMCPBackend()
        assert await placeholder.extract_with_semantics(sf.page, {"a": "b"}) == {}
        assert await placeholder.detect_layout_change(sf.page, ["h1", ".nope"]) == {
            "h1": True,
            ".nope": False,
        }
        assert await placeholder.suggest_repair(sf.page, [".x"], {"a": "b"}) is None

        mistral = MistralLLMBackend(model="mistral-test")
        out = await mistral.extract_with_semantics(sf.page, {"title": "Page heading"})
        assert out == {"title": "Demo Shop"}
        assert captured["model"] == "mistral-test"
        assert captured["schema"]["required"] == ["title"]
        assert "Demo Shop" in captured["content"]
        assert await mistral.detect_layout_change(sf.page, ["h1"]) == {"h1": True}
        repair = await mistral.suggest_repair(sf.page, [".old"], {"title": "heading"})
        assert repair == {"selector_for_title": "h1"}
        assert ".old" in captured["prompt"]


async def test_paginate_follows_next_links_and_limits(site: str) -> None:
    registry = SelectorRegistry().register_pagination(
        "shop", next_selector="li.next a", has_next="li.next"
    )
    handler = registry.get_pagination("shop")
    assert handler is not None

    async def titles(page: Any, ctx: dict[str, Any]) -> list[str]:
        return await Extractor.extract_attributes(page, "h3 a", "title")

    async with ScrapeFlow(fast_config()) as sf:
        pages = [p async for p in paginate(sf, site + "/", handler, titles)]
        assert pages == [["Alpha Book", "Beta Book"], ["Gamma Book"], ["Delta Book"]]

        limited = [
            p
            async for p in paginate(sf, site + "/", handler, titles, PaginationConfig(max_pages=2))
        ]
        assert len(limited) == 2

        by_results = [
            p
            async for p in paginate(
                sf, site + "/", handler, titles, PaginationConfig(max_results=2)
            )
        ]
        assert by_results == [["Alpha Book", "Beta Book"]]

        async def as_dict(page: Any, ctx: dict[str, Any]) -> dict[str, Any]:
            return {"url": ctx["url"], "items": await titles(page, ctx)}

        dict_pages = [
            p
            async for p in paginate(
                sf, site + "/", handler, as_dict, PaginationConfig(max_results=3)
            )
        ]
        assert [len(p["items"]) for p in dict_pages] == [2, 1]


async def test_robots_disallow_and_crawl_delay(site: str) -> None:
    async with ScrapeFlow(fast_config()) as sf:
        with pytest.raises(ScrapeFlowRobotsDisallowedError):
            await sf.navigate(site + "/admin/panel")
        assert await sf.robots_checker.can_fetch(site + "/")
        assert await sf.robots_checker.get_crawl_delay(site + "/") == 2.0  # type: ignore[attr-defined]


async def test_login_session_roundtrip(site: str, tmp_path: Path) -> None:
    handler = LoginHandler(
        name="demo",
        username_selector='input[name="username"]',
        password_selector='input[name="password"]',
        submit_selector='input[type="submit"]',
        success_selector='a[href="/logout"]',
    )
    state = tmp_path / "state.json"
    async with ScrapeFlow(fast_config()) as sf:
        assert await sf.login_with_handler(site + "/", "user", "pw", handler, timeout=5000)
        await sf.save_storage_state(str(state))
        await sf.screenshot(str(tmp_path / "shot.png"))
    assert "session" in state.read_text()
    assert (tmp_path / "shot.png").stat().st_size > 0

    config = fast_config(browser=BrowserConfig(storage_state_path=str(state)))
    async with ScrapeFlow(config) as sf:
        await sf.navigate(site + "/page/3")
        assert sf.page is not None
        cookies = await sf.page.context.cookies()
        assert any(c["name"] == "session" for c in cookies)

    # A login whose success selector never appears returns False instead of raising.
    bad = LoginHandler(
        name="bad",
        username_selector='input[name="username"]',
        password_selector='input[name="password"]',
        submit_selector='input[type="submit"]',
        success_selector=".never-there",
    )
    async with ScrapeFlow(fast_config()) as sf:
        assert not await sf.login_with_handler(site + "/", "u", "p", bad, timeout=300)


async def test_workflow_end_to_end(site: str) -> None:
    seen: list[str] = []

    async def open_shop(page: Any, context: dict[str, Any]) -> None:
        await context["scraper"].navigate(site + "/")

    async def read_rates(page: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
        return await Extractor.extract_table(context["scraper"].page, "#rates")

    def remember(result: Any, context: dict[str, Any]) -> None:
        seen.append(f"{len(result)} rows")

    wf = (
        Workflow("rates")
        .add_step("open", open_shop)
        .add_step("rates", read_rates, on_success=remember)
        .add_step("skipped", read_rates, condition=lambda ctx: False)
    )
    async with ScrapeFlow(fast_config()) as sf:
        result = await sf.run_workflow(wf)
        metrics = sf.get_metrics()
    assert result.success
    assert result.steps_completed == ["open", "rates"]
    assert result.final_data[0]["Currency"] == "EUR"
    assert seen == ["2 rows"]
    assert metrics.successful_requests >= 3  # navigate + 2 steps


async def test_page_actions_require_started_engine() -> None:
    sf = ScrapeFlow(fast_config())
    for call in (
        sf.click("a"),
        sf.fill("input", "x"),
        sf.wait_for_selector("a"),
        sf.screenshot("x.png"),
        sf.save_storage_state("x.json"),
    ):
        with pytest.raises(ScrapeFlowNotStartedError, match="not started"):
            await call
