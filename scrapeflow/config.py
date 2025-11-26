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


@dataclass
class ScrapeFlowConfig:
    """Main configuration for ScrapeFlow."""

    browser: BrowserConfig = field(default_factory=BrowserConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    anti_detection: AntiDetectionConfig = field(default_factory=AntiDetectionConfig)
    log_level: str = "INFO"
    log_file: Optional[str] = None
    debug: bool = False

