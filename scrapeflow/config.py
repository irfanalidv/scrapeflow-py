"""Configuration and settings for ScrapeFlow."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class BrowserType(str, Enum):
    """Supported browser types."""

    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (
        Exception,
    )  # Will be customized per use case


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_second: float = 1.0
    requests_per_minute: Optional[float] = None
    burst_size: int = 5


@dataclass
class AntiDetectionConfig:
    """Configuration for anti-detection features."""

    rotate_user_agents: bool = True
    rotate_proxies: bool = False
    stealth_mode: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agents: List[str] = field(default_factory=list)
    proxies: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class BrowserConfig:
    """Configuration for browser settings."""

    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = True
    timeout: int = 30000  # milliseconds
    slow_mo: int = 0  # milliseconds
    args: List[str] = field(default_factory=list)
    proxy: Optional[Dict[str, str]] = None
    storage_state_path: Optional[str] = None  # Load cookies/session from file on start


@dataclass
class PaginationConfig:
    """
    Pagination control for multi-page extraction.

    Limits: max_pages, max_results, max_wait_time (seconds).
    """

    max_pages: int = 100
    max_results: Optional[int] = None
    max_wait_time: Optional[float] = None  # seconds
    auto_paginate: bool = True


@dataclass
class EthicalCrawlingConfig:
    """
    Ethical crawling configuration—GDPR/CCPA baked into specification design.

    Rate limiting, robots.txt respect, and compliance are built into the
    specification layer, not retrofitted.
    """

    respect_robots_txt: bool = True
    user_agent_for_robots: str = "ScrapeFlow"
    max_pages_per_domain: Optional[int] = None
    honor_noindex: bool = True
    data_retention_days: Optional[int] = None  # GDPR: document retention
    anonymize_ip: bool = False  # GDPR: minimize personal data
    consent_required: bool = False  # GDPR: require consent for tracking


@dataclass
class ScrapeFlowConfig:
    """Main configuration for ScrapeFlow."""

    browser: BrowserConfig = field(default_factory=BrowserConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    anti_detection: AntiDetectionConfig = field(default_factory=AntiDetectionConfig)
    ethical_crawling: EthicalCrawlingConfig = field(
        default_factory=EthicalCrawlingConfig
    )
    log_level: str = "INFO"
    log_file: Optional[str] = None
    debug: bool = False

