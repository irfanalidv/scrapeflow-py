"""
LLM-powered extraction using Mistral API.

Demonstrates:
- generate_schema_from_prompt: natural language -> JSON schema
- extract_with_schema: page content -> structured data (no selectors)
- MistralLLMBackend for semantic extraction

Requires MISTRAL_API_KEY in .env
"""

import asyncio
import os

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scrapeflow import ScrapeFlow, create_mcp_backend
from scrapeflow.config import ScrapeFlowConfig, EthicalCrawlingConfig
from scrapeflow.llm_extract import generate_schema_from_prompt, extract_with_schema


async def run_llm_extraction():
    """Extract quotes using LLM—no CSS selectors, just field descriptions."""
    if not os.environ.get("MISTRAL_API_KEY"):
        print("Set MISTRAL_API_KEY in .env to run this example")
        return

    config = ScrapeFlowConfig(
        ethical_crawling=EthicalCrawlingConfig(respect_robots_txt=True),
    )

    async with ScrapeFlow(config) as scraper:
        await scraper.navigate("https://quotes.toscrape.com/")

        # Option 1: Generate schema from prompt
        schema = generate_schema_from_prompt(
            "Extract quote text, author name, and list of tags"
        )
        print("Generated schema:", schema)

        # Option 2: Extract using schema + page content
        content = await scraper.page.evaluate(
            "() => document.body.innerText"
        )
        data = extract_with_schema(
            content,
            schema,
            prompt="Extract all quotes from this page with text, author, and tags",
        )
        print("LLM extracted:", data)

        # Option 3: Use MistralLLMBackend (field descriptions only)
        backend = create_mcp_backend("mistral")
        field_descriptions = {
            "quote": "The quote text",
            "author": "Author name",
            "tags": "Comma-separated tags",
        }
        semantic_data = await backend.extract_with_semantics(
            scraper.page,
            field_descriptions,
            context="Extract the first quote on the page",
        )
        print("Semantic extraction:", semantic_data)


if __name__ == "__main__":
    asyncio.run(run_llm_extraction())
