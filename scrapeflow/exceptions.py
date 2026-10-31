"""Custom exceptions for ScrapeFlow.

Every exception raised on purpose by the library derives from :class:`ScrapeFlowError`, so
callers can catch the whole family with one ``except`` clause.
"""


class ScrapeFlowError(Exception):
    """Base exception for all ScrapeFlow errors."""


class ScrapeFlowRetryError(ScrapeFlowError):
    """Raised when an operation still fails after all retries."""

    def __init__(self, message: str, retry_count: int = 0, max_retries: int = 3):
        super().__init__(message)
        self.retry_count = retry_count
        self.max_retries = max_retries


class ScrapeFlowTimeoutError(ScrapeFlowError):
    """Raised when an operation times out."""


class ScrapeFlowBlockedError(ScrapeFlowError):
    """Raised when the scraper is blocked or rate-limited."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ScrapeFlowValidationError(ScrapeFlowError):
    """Raised when extracted data fails validation."""


class ScrapeFlowRobotsDisallowedError(ScrapeFlowError):
    """Raised when robots.txt disallows fetching the URL."""


class ScrapeFlowNotStartedError(ScrapeFlowError, RuntimeError):
    """Raised when a page action is attempted before the engine or runtime has started.

    Subclasses :class:`RuntimeError` because the browser runtime raised that before 0.5.0.
    """


class ScrapeFlowConfigurationError(ScrapeFlowError, ValueError):
    """Raised when required configuration (for example ``MISTRAL_API_KEY``) is missing.

    Subclasses :class:`ValueError` so code written against earlier versions keeps working.
    """
