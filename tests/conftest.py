"""Shared fixtures: a tiny local website and a Chromium availability check.

Browser tests run against ``http.server`` on 127.0.0.1, so the suite never touches the
public internet.
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator

import pytest

PAGES: dict[str, tuple[int, str, str]] = {
    "/robots.txt": (
        200,
        "text/plain",
        "User-agent: *\nDisallow: /admin/\nCrawl-delay: 2\n",
    ),
    "/": (
        200,
        "text/html",
        """<html><head><title>Shop</title>
<script type="application/ld+json">{"@type": "Store", "name": "Demo Shop"}</script>
</head><body>
<h1>  Demo   Shop </h1>
<nav><a href="/page/2">Next</a><a href="https://example.org/">Out</a><a>no href</a></nav>
<img src="/a.png" alt="A"><img src="/b.png">
<article class="product"><h3><a href="/p/1" title="Alpha Book">Alpha…</a></h3>
  <span class="price">£10.50</span><span class="stock">In stock</span>
  <ul><li class="tag">new</li><li class="tag"> sale </li></ul></article>
<article class="product"><h3><a href="/p/2" title="Beta Book">Beta…</a></h3>
  <span class="cost">£7.25</span></article>
<table id="rates"><thead><tr><th>Currency</th><th>Rate</th></tr></thead>
<tbody><tr><td>EUR</td><td>1.17</td></tr><tr><td>USD</td><td>1.27</td></tr></tbody></table>
<div id="html-box"><b>bold</b></div>
<form action="/account" method="get">
  <input name="username"><input name="password" type="password">
  <input type="submit" value="Log in">
</form>
<ul class="pager"><li class="next"><a href="/page/2">next</a></li></ul>
</body></html>""",
    ),
    "/page/2": (
        200,
        "text/html",
        """<html><body>
<article class="product"><h3><a href="/p/3" title="Gamma Book">Gamma</a></h3>
  <span class="price">£3.00</span></article>
<ul class="pager"><li class="next"><a href="/page/3">next</a></li></ul>
</body></html>""",
    ),
    "/page/3": (
        200,
        "text/html",
        """<html><body>
<article class="product"><h3><a href="/p/4" title="Delta Book">Delta</a></h3>
  <span class="price">£4.00</span></article>
</body></html>""",
    ),
    "/data": (
        200,
        "text/html",
        """<html><body><script type="application/json">{"items": [1, 2, 3]}</script>
</body></html>""",
    ),
    "/account": (
        200,
        "text/html",
        """<html><body><p class="welcome">Welcome</p><a href="/logout">Log out</a>
<script>document.cookie = "session=demo; path=/";</script></body></html>""",
    ),
}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        status, ctype, body = PAGES.get(path, (404, "text/plain", "not found"))
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def site() -> Iterator[str]:
    """Base URL of a local test site (see ``PAGES``)."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


CHROMIUM = _chromium_available()

requires_browser = pytest.mark.skipif(
    not CHROMIUM, reason="Chromium not installed (playwright install chromium)"
)
