"""Public API compatibility checks."""

from inspect import signature

import scrapeflow
from scrapeflow.engine import ScrapeFlow


def test_public_exports_exist():
    assert hasattr(scrapeflow, "ScrapeFlow")
    assert hasattr(scrapeflow, "Workflow")
    assert hasattr(scrapeflow, "SpecificationExtractor")
    assert hasattr(scrapeflow, "PlaywrightBrowserRuntime")


def test_scrapeflow_constructor_backward_compatible():
    sig = signature(ScrapeFlow.__init__)
    assert "config" in sig.parameters
