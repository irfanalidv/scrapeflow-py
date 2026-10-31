# ScrapeFlow - Playwright scraping workflow engine
FROM python:3.12-slim

WORKDIR /app

# Browsers must be installed to the same path Playwright looks in at runtime
ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install the package (and test tools, so the default CMD works)
COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY scrapeflow ./scrapeflow
RUN pip install --no-cache-dir . "pytest>=7.4.0" "pytest-asyncio>=0.23.0"

# Chromium plus its system dependencies
RUN playwright install --with-deps chromium

COPY tests ./tests
COPY examples ./examples

# Default: run tests (override for custom extraction jobs)
CMD ["pytest", "tests/", "-v", "--tb=short"]
