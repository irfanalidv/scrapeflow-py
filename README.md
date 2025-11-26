# ScrapeFlow

**An opinionated scraping workflow engine built on Playwright**

[![GitHub](https://img.shields.io/github/license/irfanalidv/ScrapeFlow)](https://github.com/irfanalidv/ScrapeFlow/blob/main/LICENSE)

[![PyPI](https://img.shields.io/pypi/v/scrapeflow-py)](https://pypi.org/project/scrapeflow-py/)

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/scrapeflow-py?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/scrapeflow-py)

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)

[![Playwright](https://img.shields.io/badge/Playwright-1.40%2B-green)](https://playwright.dev/)

[![Status](https://img.shields.io/badge/status-active-success)](https://github.com/irfanalidv/ScrapeFlow)

---

ScrapeFlow is a production-ready Python library that transforms Playwright into a powerful, enterprise-grade web scraping framework. It handles the common challenges of web scraping: retries, rate limiting, anti-detection, error recovery, and workflow orchestration.

## 🚀 Features

- **🔄 Intelligent Retry Logic**: Automatic retries with exponential backoff and jitter
- **⚡ Rate Limiting**: Token bucket algorithm to respect server limits
- **🕵️ Anti-Detection**: Stealth mode, user agent rotation, and proxy support
- **📊 Workflow Engine**: Define complex scraping workflows with steps and conditions
- **📈 Monitoring & Metrics**: Built-in performance monitoring and logging
- **🛠️ Data Extraction**: Powerful utilities for extracting structured data
- **🔧 Error Handling**: Comprehensive error classification and recovery
- **📝 Type Hints**: Full type support for better IDE experience

## 📦 Installation

```bash
pip install scrapeflow-py
```

Or install from source:

```bash
git clone https://github.com/irfanalidv/ScrapeFlow.git
cd ScrapeFlow
pip install -e .
```

**Note**: After installation, install Playwright browsers:

```bash
playwright install
```

## 🎯 Quick Start

### Basic Usage

```python
import asyncio
from scrapeflow import ScrapeFlow
from scrapeflow.config import ScrapeFlowConfig

async def main():
    config = ScrapeFlowConfig()
    config.browser.headless = False

    async with ScrapeFlow(config) as scraper:
        await scraper.navigate("https://example.com")
        title = await scraper.page.title()
        print(f"Page title: {title}")

asyncio.run(main())
```

### Workflow Example

```python
import asyncio
from scrapeflow import ScrapeFlow, Workflow
from scrapeflow.extractors import Extractor

async def extract_data(page, context):
    return {
        "title": await Extractor.extract_text(page, "h1"),
        "links": await Extractor.extract_links(page, "a"),
    }

async def main():
    async with ScrapeFlow() as scraper:
        workflow = Workflow(name="my_scraper")
        workflow.add_step("navigate", lambda page, context: scraper.navigate("https://example.com"))
        workflow.add_step("extract", extract_data)

        result = await scraper.run_workflow(workflow)
        print(result.final_data)

asyncio.run(main())
```

## 📚 Documentation

### Configuration

ScrapeFlow is highly configurable:

```python
from scrapeflow.config import (
    ScrapeFlowConfig,
    AntiDetectionConfig,
    RateLimitConfig,
    RetryConfig,
    BrowserConfig,
    BrowserType,
)

config = ScrapeFlowConfig(
    browser=BrowserConfig(
        browser_type=BrowserType.CHROMIUM,
        headless=True,
        timeout=30000,
    ),
    retry=RetryConfig(
        max_retries=5,
        initial_delay=1.0,
        max_delay=60.0,
        exponential_base=2.0,
    ),
    rate_limit=RateLimitConfig(
        requests_per_second=2.0,
        burst_size=5,
    ),
    anti_detection=AntiDetectionConfig(
        rotate_user_agents=True,
        stealth_mode=True,
        viewport_width=1920,
        viewport_height=1080,
    ),
    log_level="INFO",
)
```

### Anti-Detection

ScrapeFlow includes several anti-detection features:

```python
from scrapeflow.config import AntiDetectionConfig

# User agent rotation
anti_detection = AntiDetectionConfig(
    rotate_user_agents=True,
    user_agents=[
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
        # Add your custom user agents
    ],
)

# Proxy rotation
anti_detection = AntiDetectionConfig(
    rotate_proxies=True,
    proxies=[
        {"server": "http://proxy1:8080"},
        {"server": "http://proxy2:8080"},
    ],
)

# Stealth mode (removes automation indicators)
anti_detection = AntiDetectionConfig(stealth_mode=True)
```

### Rate Limiting

Control request frequency to avoid being blocked:

```python
from scrapeflow.config import RateLimitConfig

rate_limit = RateLimitConfig(
    requests_per_second=1.0,  # 1 request per second
    requests_per_minute=60.0,  # Or 60 per minute
    burst_size=5,  # Allow bursts of 5 requests
)
```

### Retry Logic

Automatic retries with exponential backoff:

```python
from scrapeflow.config import RetryConfig

retry = RetryConfig(
    max_retries=5,
    initial_delay=1.0,  # Start with 1 second
    max_delay=60.0,  # Cap at 60 seconds
    exponential_base=2.0,  # Double delay each retry
    jitter=True,  # Add randomness to avoid thundering herd
)
```

### Data Extraction

ScrapeFlow provides powerful extraction utilities:

```python
from scrapeflow.extractors import Extractor, StructuredExtractor

# Simple extraction
title = await Extractor.extract_text(page, "h1")
links = await Extractor.extract_links(page, "a")
images = await Extractor.extract_images(page, "img")

# Table extraction
table_data = await Extractor.extract_table(page, "table")

# Structured extraction with schema
schema = {
    "title": "h1",
    "description": ".description",
    "items": {
        "items": ".item",
        "schema": {
            "name": ".name",
            "price": ".price",
        },
    },
}
extractor = StructuredExtractor(schema)
data = await extractor.extract(page)
```

### Workflows

Build complex scraping workflows:

```python
from scrapeflow import Workflow

workflow = Workflow(name="product_scraper")

# Add steps
workflow.add_step(
    name="navigate",
    func=lambda page, context: scraper.navigate("https://example.com"),
    required=True,  # Stop workflow if this fails
)

workflow.add_step(
    name="extract",
    func=extract_data,
    retryable=True,
    on_success=save_data,  # Callback on success
    on_error=handle_error,  # Callback on error
    condition=lambda ctx: ctx.get("should_extract", True),  # Conditional execution
)

# Execute
result = await scraper.run_workflow(workflow)
```

### Monitoring & Metrics

Track scraping performance:

```python
# Get metrics
metrics = scraper.get_metrics()
print(f"Success rate: {metrics.get_success_rate():.2f}%")
print(f"Total requests: {metrics.total_requests}")
print(f"Average response time: {metrics.average_response_time:.2f}s")
print(f"Errors by type: {metrics.errors_by_type}")

# Reset metrics
scraper.reset_metrics()
```

### Error Handling

ScrapeFlow provides custom exceptions:

```python
from scrapeflow.exceptions import (
    ScrapeFlowError,
    ScrapeFlowRetryError,
    ScrapeFlowTimeoutError,
    ScrapeFlowBlockedError,
)

try:
    await scraper.navigate("https://example.com")
except ScrapeFlowBlockedError as e:
    print(f"Blocked! Retry after {e.retry_after} seconds")
except ScrapeFlowTimeoutError:
    print("Request timed out")
except ScrapeFlowRetryError as e:
    print(f"Failed after {e.retry_count} retries")
```

## 🎨 Examples

Check out the `examples/` directory for more examples:

- `basic_usage.py` - Simple scraping example
- `workflow_example.py` - Workflow orchestration
- `advanced_example.py` - All features combined

## 🏗️ Architecture

ScrapeFlow is built with a modular architecture:

```
scrapeflow/
├── engine.py          # Main ScrapeFlow engine
├── workflow.py        # Workflow definition and execution
├── config.py          # Configuration classes
├── anti_detection.py  # Anti-detection utilities
├── rate_limiter.py    # Rate limiting implementation
├── retry.py           # Retry logic and error classification
├── monitoring.py      # Metrics and logging
├── extractors.py      # Data extraction utilities
└── exceptions.py      # Custom exceptions
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on top of [Playwright](https://playwright.dev/) - an amazing browser automation library
- Inspired by the need for production-ready scraping solutions

## 📧 Contact

Irfan Ali - [GitHub](https://github.com/irfanalidv)

Project Link: [https://github.com/irfanalidv/ScrapeFlow](https://github.com/irfanalidv/ScrapeFlow)

---

**Made with ❤️ for the scraping community**
