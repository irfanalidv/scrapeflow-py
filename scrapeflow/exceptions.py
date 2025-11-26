"""Custom exceptions for ScrapeFlow."""


class ScrapeFlowError(Exception):
    """Base exception for all ScrapeFlow errors."""

    pass


class ScrapeFlowRetryError(ScrapeFlowError):
    """Raised when a retryable error occurs."""

    def __init__(self, message: str, retry_count: int = 0, max_retries: int = 3):
        super().__init__(message)
        self.retry_count = retry_count
        self.max_retries = max_retries


class ScrapeFlowTimeoutError(ScrapeFlowError):
    """Raised when an operation times out."""

    pass


class ScrapeFlowBlockedError(ScrapeFlowError):
    """Raised when the scraper is blocked or rate-limited."""

    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after


class ScrapeFlowValidationError(ScrapeFlowError):
    """Raised when validation fails."""

    pass

