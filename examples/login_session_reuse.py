"""Log in once, save the session, and reuse it in a later run without logging in again.

Shows:
  * a reusable ``LoginHandler`` stored in a ``SelectorRegistry``
  * ``ScrapeFlow.login_with_handler`` (success verified by a selector)
  * ``save_storage_state()`` and ``BrowserConfig(storage_state_path=...)``
  * that content behind the login is visible only with the saved session

Needs: ``pip install scrapeflow-py`` and ``playwright install chromium``.
No internet and no API key: it uses the bundled demo site on 127.0.0.1, which accepts any
username and password. Never commit real credentials or saved session files.

Run: python examples/login_session_reuse.py
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from _demo_site import serve_demo_site

from scrapeflow import ScrapeFlow
from scrapeflow.config import BrowserConfig, ScrapeFlowConfig
from scrapeflow.extractors import Extractor
from scrapeflow.registry import SelectorRegistry


async def member_prices(scraper: ScrapeFlow, base_url: str) -> list[str]:
    await scraper.navigate(base_url + "/members.html")
    return await Extractor.extract_texts(scraper.page, "#member-prices li")


async def main() -> None:
    registry = SelectorRegistry().register_login(
        "demo_shop",
        username_selector='input[name="username"]',
        password_selector='input[name="password"]',
        submit_selector='input[type="submit"]',
        success_selector='a[href="logout.html"]',
        description="Demo bookshop member login",
    )
    handler = registry.get_login("demo_shop")
    assert handler is not None

    with tempfile.TemporaryDirectory() as tmp, serve_demo_site() as base_url:
        state_file = Path(tmp) / "demo_session.json"
        quiet = ScrapeFlowConfig(log_level="WARNING")

        # Run 1: anonymous, then log in and save cookies + localStorage.
        async with ScrapeFlow(quiet) as scraper:
            print("anonymous member prices:", await member_prices(scraper, base_url))
            ok = await scraper.login_with_handler(
                base_url + "/login.html", "reader", "not-a-real-password", handler
            )
            print("login succeeded:", ok)
            await scraper.save_storage_state(str(state_file))

        # Run 2: a fresh browser that starts from the saved state; no login step.
        reuse = ScrapeFlowConfig(
            browser=BrowserConfig(storage_state_path=str(state_file)), log_level="WARNING"
        )
        async with ScrapeFlow(reuse) as scraper:
            for line in await member_prices(scraper, base_url):
                print("  member price:", line)


if __name__ == "__main__":
    asyncio.run(main())
