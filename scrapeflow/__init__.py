"""
ScrapeFlow - An opinionated scraping workflow engine built on Playwright.

ScrapeFlow provides a robust, production-ready framework for web scraping
with built-in error handling, retry logic, anti-detection, and workflow management.

Specification-driven extraction, robots.txt compliance, and ethical crawling
(GDPR/CCPA) are built into the design.
"""

from scrapeflow.engine import ScrapeFlow
from scrapeflow.workflow import Workflow, Step
from scrapeflow.workflow_executor import WorkflowExecutor
from scrapeflow.extractors import Extractor, StructuredExtractor
from scrapeflow.specifications import (
    FieldSpec,
    ItemSpec,
    SpecificationExtractor,
    HybridExtractor,
    ProductPriceSpec,
    JobListingSpec,
    TariffCodeSpec,
)
from scrapeflow.robots import RobotsChecker
from scrapeflow.registry import (
    SelectorRegistry,
    LoginHandler,
    get_registry,
    register_quotes_login_handler,
)
from scrapeflow.browser_runtime import PlaywrightBrowserRuntime
from scrapeflow.llm_extract import (
    generate_schema_from_prompt,
    extract_with_schema,
    extract_with_schema_async,
)
from scrapeflow.mcp_backend import (
    MCPBackend,
    PlaceholderMCPBackend,
    MistralLLMBackend,
    create_mcp_backend,
)
from scrapeflow.exceptions import (
    ScrapeFlowError,
    ScrapeFlowRetryError,
    ScrapeFlowTimeoutError,
    ScrapeFlowBlockedError,
    ScrapeFlowValidationError,
    ScrapeFlowRobotsDisallowedError,
)

__version__ = "0.3.0"
__all__ = [
    "ScrapeFlow",
    "Workflow",
    "Step",
    "WorkflowExecutor",
    "Extractor",
    "StructuredExtractor",
    "FieldSpec",
    "ItemSpec",
    "SpecificationExtractor",
    "HybridExtractor",
    "ProductPriceSpec",
    "JobListingSpec",
    "TariffCodeSpec",
    "RobotsChecker",
    "SelectorRegistry",
    "LoginHandler",
    "get_registry",
    "register_quotes_login_handler",
    "PlaywrightBrowserRuntime",
    "MCPBackend",
    "PlaceholderMCPBackend",
    "MistralLLMBackend",
    "create_mcp_backend",
    "ScrapeFlowError",
    "ScrapeFlowRetryError",
    "ScrapeFlowTimeoutError",
    "ScrapeFlowBlockedError",
    "ScrapeFlowValidationError",
    "ScrapeFlowRobotsDisallowedError",
    "generate_schema_from_prompt",
    "extract_with_schema",
    "extract_with_schema_async",
]

