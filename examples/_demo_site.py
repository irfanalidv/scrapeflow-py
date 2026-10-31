"""Serve ``examples/demo_site/`` on 127.0.0.1 so the examples run without internet access.

The site is a tiny fictional bookshop with a paginated catalogue, a shipping-rates table,
a login flow that sets a session cookie, a product page whose layout "changed", and a
robots.txt that disallows ``/admin/`` and asks for a 1-second crawl delay.
"""

from __future__ import annotations

import functools
import http.server
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent / "demo_site"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve_demo_site() -> Iterator[str]:
    """Start the demo site on a free port and yield its base URL (no trailing slash)."""
    handler = functools.partial(_QuietHandler, directory=str(SITE_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
