"""Tests for version metadata, LLM extraction (Mistral mocked), and a real-browser smoke test."""

import http.server
import sys
import threading
import types

import pytest
from pydantic import BaseModel

import scrapeflow
from scrapeflow import llm_extract

# --------------------------------------------------------------------------- metadata


def test_version_exposed():
    assert isinstance(scrapeflow.__version__, str)
    assert scrapeflow.__version__.count(".") >= 2


# --------------------------------------------------------------------------- LLM (mocked)


class _FakeChat:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        msg = types.SimpleNamespace(content=self.reply)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


class _FakeClient:
    def __init__(self, reply):
        self.chat = _FakeChat(reply)


def test_generate_schema_strips_code_fences(monkeypatch):
    reply = '```json\n{"type": "object", "properties": {"title": {"type": "string"}}}\n```'
    client = _FakeClient(reply)
    monkeypatch.setattr(llm_extract, "_get_mistral_client", lambda: client)
    schema = llm_extract.generate_schema_from_prompt("book title")
    assert schema["properties"] == {"title": {"type": "string"}}
    assert client.chat.calls[0]["response_format"] == {"type": "json_object"}


def test_generate_schema_wraps_bare_properties(monkeypatch):
    monkeypatch.setattr(
        llm_extract, "_get_mistral_client", lambda: _FakeClient('{"price": {"type": "number"}}')
    )
    schema = llm_extract.generate_schema_from_prompt("price")
    assert schema == {
        "type": "object",
        "properties": {"price": {"type": "number"}},
        "required": ["price"],
    }


def test_extract_with_schema_parses_json_and_handles_garbage(monkeypatch):
    client = _FakeClient('{"title": "A Light in the Attic", "price": 51.77}')
    monkeypatch.setattr(llm_extract, "_get_mistral_client", lambda: client)
    out = llm_extract.extract_with_schema("<h1>A Light in the Attic</h1>", {"type": "object"})
    assert out == {"title": "A Light in the Attic", "price": 51.77}

    monkeypatch.setattr(llm_extract, "_get_mistral_client", lambda: _FakeClient("not json"))
    assert llm_extract.extract_with_schema("x", {"type": "object"}) == {}


async def test_extract_with_schema_async(monkeypatch):
    monkeypatch.setattr(llm_extract, "_get_mistral_client", lambda: _FakeClient('{"a": 1}'))
    assert await llm_extract.extract_with_schema_async("x", {"type": "object"}) == {"a": 1}


def test_mistral_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.setattr(llm_extract, "_get_api_key", lambda: "")
    with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
        llm_extract._get_mistral_client()


def test_mistral_client_supports_new_sdk_layout(monkeypatch):
    """mistralai>=2 exposes the client at mistralai.client.Mistral, not mistralai.Mistral."""

    class FakeMistral:
        def __init__(self, api_key):
            self.api_key = api_key

    top = types.ModuleType("mistralai")  # no top-level Mistral attribute
    sub = types.ModuleType("mistralai.client")
    sub.Mistral = FakeMistral
    top.client = sub
    monkeypatch.setitem(sys.modules, "mistralai", top)
    monkeypatch.setitem(sys.modules, "mistralai.client", sub)
    monkeypatch.setattr(llm_extract, "_get_api_key", lambda: "k")
    assert llm_extract._get_mistral_client().api_key == "k"


# --------------------------------------------------------------------------- real browser

PAGE = b"""<html><head><title>Shelf</title></head><body>
<article class="book"><h3>Alpha</h3><span class="price">10.50</span></article>
<article class="book"><h3>Beta</h3><span class="price">7.25</span></article>
</body></html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/robots.txt":
            body, ctype = b"User-agent: *\nDisallow: /private\n", "text/plain"
        else:
            body, ctype = PAGE, "text/html"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def local_site():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


browser = pytest.mark.skipif(
    not _chromium_available(), reason="Chromium not installed (playwright install chromium)"
)


class Book(BaseModel):
    title: str
    price: float


class Shelf(BaseModel):
    books: list[Book]


@browser
async def test_browser_navigate_and_spec_extraction(local_site):
    from scrapeflow import ScrapeFlow, SpecificationExtractor
    from scrapeflow.config import ScrapeFlowConfig
    from scrapeflow.specifications import FieldSpec, ItemSpec

    schema = {
        "books": ItemSpec(
            items_selector="article.book",
            fields={"title": FieldSpec(selector="h3"), "price": FieldSpec(selector=".price")},
        )
    }
    async with ScrapeFlow(ScrapeFlowConfig()) as scraper:
        await scraper.navigate(local_site + "/")
        assert await scraper.page.title() == "Shelf"
        data = await SpecificationExtractor(Shelf, schema=schema).extract(scraper.page)
    assert [b.title for b in data.books] == ["Alpha", "Beta"]
    assert [b.price for b in data.books] == [10.5, 7.25]


@browser
async def test_browser_respects_robots_txt(local_site):
    from scrapeflow import ScrapeFlow
    from scrapeflow.config import EthicalCrawlingConfig, ScrapeFlowConfig
    from scrapeflow.exceptions import ScrapeFlowRobotsDisallowedError

    config = ScrapeFlowConfig(ethical_crawling=EthicalCrawlingConfig(respect_robots_txt=True))
    async with ScrapeFlow(config) as scraper:
        with pytest.raises(ScrapeFlowRobotsDisallowedError):
            await scraper.navigate(local_site + "/private/page")


# --------------------------------------------------------------------------- MCP factory


def test_create_mcp_backend_types():
    from scrapeflow.mcp_backend import (
        MistralLLMBackend,
        PlaceholderMCPBackend,
        create_mcp_backend,
    )

    assert isinstance(create_mcp_backend(), PlaceholderMCPBackend)
    assert isinstance(create_mcp_backend("mistral"), MistralLLMBackend)
    with pytest.warns(UserWarning, match="not implemented"):
        assert isinstance(create_mcp_backend("scrapy_mcp"), PlaceholderMCPBackend)
    with pytest.raises(ValueError, match="Unknown MCP backend"):
        create_mcp_backend("nope")
