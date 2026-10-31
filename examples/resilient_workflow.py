"""Resilient multi-step workflow: retries, optional steps, conditions and callbacks.

Shows:
  * ``Workflow.add_step`` chaining with ``on_success`` / ``on_error`` callbacks
  * a ``retryable`` step that hits a transient ``ConnectionError`` once and is retried
  * a non-``required`` step whose failure is recorded without stopping the run
  * a ``condition`` that skips a step based on the shared context
  * ``Extractor.extract_table`` turning an HTML table into dicts
  * ``WorkflowResult`` and the metrics (including the retry count)

Needs: ``pip install scrapeflow-py`` and ``playwright install chromium``.
No internet and no API key: it uses the bundled demo site on 127.0.0.1.

Run: python examples/resilient_workflow.py
"""

from __future__ import annotations

import asyncio
from typing import Any

from _demo_site import serve_demo_site

from scrapeflow import ScrapeFlow, Workflow
from scrapeflow.config import RetryConfig, ScrapeFlowConfig
from scrapeflow.extractors import Extractor


async def main() -> None:
    with serve_demo_site() as base_url:
        attempts = {"rates": 0}

        async def open_rates(page: Any, context: dict[str, Any]) -> None:
            await context["scraper"].navigate(base_url + "/shipping.html")

        async def read_rates(page: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
            attempts["rates"] += 1
            if attempts["rates"] == 1:
                # Simulate a flaky upstream: the first attempt drops the connection.
                raise ConnectionError("connection reset by peer")
            return await Extractor.extract_table(context["scraper"].page, "#rates")

        def store_rates(rows: list[dict[str, Any]], context: dict[str, Any]) -> None:
            context["rates"] = rows

        async def read_promotions(page: Any, context: dict[str, Any]) -> None:
            raise LookupError("no .promo banner on this page")

        def log_error(error: Exception, context: dict[str, Any]) -> None:
            print(f"  optional step failed (continuing): {error}")

        def cheapest_express(page: Any, context: dict[str, Any]) -> str:
            rows = context["rates"]
            best = min(rows, key=lambda r: float(r["Express"].lstrip("£")))
            return f"{best['Region']} at {best['Express']}"

        workflow = (
            Workflow("shipping-report")
            .add_step("open", open_rates)
            .add_step("rates", read_rates, on_success=store_rates)  # retryable by default
            .add_step("promotions", read_promotions, required=False, on_error=log_error)
            .add_step("summary", cheapest_express, condition=lambda ctx: bool(ctx.get("rates")))
        )

        config = ScrapeFlowConfig(
            retry=RetryConfig(max_retries=2, initial_delay=0.2), log_level="WARNING"
        )
        async with ScrapeFlow(config) as scraper:
            result = await scraper.run_workflow(workflow)
            metrics = scraper.get_metrics()

    print(f"success={result.success}  (False because an optional step failed)")
    print(f"completed={result.steps_completed} failed={result.steps_failed}")
    print(f"'rates' step attempts: {attempts['rates']}")
    for row in result.context["rates"]:
        print(f"  {row['Region']:<16} standard {row['Standard']:>6}  express {row['Express']:>6}")
    print(f"cheapest express: {result.final_data}")
    print(f"metrics: {metrics.total_requests} requests, {metrics.retry_count} retry")


if __name__ == "__main__":
    asyncio.run(main())
