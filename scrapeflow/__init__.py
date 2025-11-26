"""
ScrapeFlow - An opinionated scraping workflow engine built on Playwright.

ScrapeFlow provides a robust, production-ready framework for web scraping
with built-in error handling, retry logic, anti-detection, and workflow management.
"""

from scrapeflow.engine import ScrapeFlow
from scrapeflow.workflow import Workflow, Step
from scrapeflow.extractors import Extractor, StructuredExtractor
from scrapeflow.exceptions import (
    ScrapeFlowError,
    ScrapeFlowRetryError,
    ScrapeFlowTimeoutError,
    ScrapeFlowBlockedError,
)

__version__ = "0.1.0"
__all__ = [
    "ScrapeFlow",
    "Workflow",
    "Step",
    "Extractor",
    "StructuredExtractor",
    "ScrapeFlowError",
    "ScrapeFlowRetryError",
    "ScrapeFlowTimeoutError",
    "ScrapeFlowBlockedError",
]

