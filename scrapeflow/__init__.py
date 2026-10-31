"""
ScrapeFlow - An opinionated scraping workflow engine built on Playwright.

ScrapeFlow provides a robust, production-ready framework for web scraping
with built-in error handling, retry logic, anti-detection, and workflow management.

Specification-driven extraction, robots.txt compliance, and ethical crawling
(GDPR/CCPA) are built into the design.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from scrapeflow.browser_runtime import PlaywrightBrowserRuntime
from scrapeflow.engine import ScrapeFlow
from scrapeflow.exceptions import (
    ScrapeFlowBlockedError,
    ScrapeFlowError,
    ScrapeFlowRetryError,
    ScrapeFlowRobotsDisallowedError,
    ScrapeFlowTimeoutError,
    ScrapeFlowValidationError,
)
from scrapeflow.extractors import Extractor, StructuredExtractor
from scrapeflow.llm_extract import (
    extract_with_schema,
    extract_with_schema_async,
    generate_schema_from_prompt,
)
from scrapeflow.mcp_backend import (
    MCPBackend,
    MistralLLMBackend,
    PlaceholderMCPBackend,
    create_mcp_backend,
)
from scrapeflow.registry import (
    LoginHandler,
    SelectorRegistry,
    get_registry,
    register_quotes_login_handler,
)
from scrapeflow.robots import RobotsChecker
from scrapeflow.specifications import (
    FieldSpec,
    HybridExtractor,
    ItemSpec,
    JobListingSpec,
    ProductPriceSpec,
    SpecificationExtractor,
    TariffCodeSpec,
)
from scrapeflow.workflow import Step, Workflow
from scrapeflow.workflow_executor import WorkflowExecutor

try:
    __version__ = _pkg_version("scrapeflow-py")
except PackageNotFoundError:  # running from a source checkout without installation
    __version__ = "0.4.0"

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
