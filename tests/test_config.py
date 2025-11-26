"""Tests for configuration classes."""

import pytest
from scrapeflow.config import (
    ScrapeFlowConfig,
    BrowserConfig,
    RetryConfig,
    RateLimitConfig,
    AntiDetectionConfig,
    BrowserType,
)


def test_browser_config():
    """Test BrowserConfig creation."""
    config = BrowserConfig(
        browser_type=BrowserType.CHROMIUM,
        headless=True,
        timeout=30000,
    )
    assert config.browser_type == BrowserType.CHROMIUM
    assert config.headless is True
    assert config.timeout == 30000


def test_retry_config():
    """Test RetryConfig creation."""
    config = RetryConfig(
        max_retries=5,
        initial_delay=1.0,
        max_delay=60.0,
    )
    assert config.max_retries == 5
    assert config.initial_delay == 1.0
    assert config.max_delay == 60.0


def test_rate_limit_config():
    """Test RateLimitConfig creation."""
    config = RateLimitConfig(
        requests_per_second=2.0,
        burst_size=5,
    )
    assert config.requests_per_second == 2.0
    assert config.burst_size == 5


def test_anti_detection_config():
    """Test AntiDetectionConfig creation."""
    config = AntiDetectionConfig(
        rotate_user_agents=True,
        stealth_mode=True,
    )
    assert config.rotate_user_agents is True
    assert config.stealth_mode is True


def test_scrapeflow_config():
    """Test ScrapeFlowConfig creation."""
    config = ScrapeFlowConfig()
    assert config.browser is not None
    assert config.retry is not None
    assert config.rate_limit is not None
    assert config.anti_detection is not None

