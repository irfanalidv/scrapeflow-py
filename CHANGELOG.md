# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-10-31

### Fixed
- `.env` files are now looked up from the current working directory instead of the package install path.
- `Extractor.extract_table()` always returned `[]`: the coroutine from `Locator.all()` was never
  awaited. It now returns one dict per data row.
- `RobotsChecker.get_crawl_delay()` always returned `None`; it now returns the `Crawl-delay`
  for the configured user agent.
- Workflow steps with `retryable=True` (the default) were never retried, while the monitor
  recorded a retry anyway. Steps that fail with a transient error (connection error, timeout,
  `ScrapeFlowBlockedError`) are now re-run through the retry handler; when retries run out the
  step fails with `ScrapeFlowRetryError` chaining the last error.
- `PlaywrightBrowserRuntime.start()` leaked the Playwright driver and browser process when
  launching failed part-way through.
- `RateLimitConfig.requests_per_minute` was ignored whenever `requests_per_second` was set, which
  is always the case with the defaults. When both are set, the slower limit now wins. The limiter
  also uses a monotonic clock.
- Creating several `ScrapeFlow` instances with `log_file` leaked file handles; old handlers are
  now closed.
- `timeout=0` (Playwright: no timeout) was silently replaced by the default timeout.
- Errors swallowed by extractors, step conditions and login checks are now logged.

### Changed
- robots.txt fetch failures follow RFC 9309: a 4xx response allows everything (as before), but a
  5xx response or a network error now disallows the site until the cache entry expires
  (previously every failure allowed everything). `about:`, `data:` and `file:` URLs skip the
  check. The robots.txt request now sends the configured robots user agent.
- "Engine not started" errors raise `ScrapeFlowNotStartedError` (a subclass of both
  `ScrapeFlowError` and `RuntimeError`, the two types raised before). A missing
  `MISTRAL_API_KEY` raises `ScrapeFlowConfigurationError` (a `ValueError` subclass).
- `SpecificationExtractor` and `HybridExtractor` are generic in the model type, so type checkers
  know what `extract()` returns.
- `StructuredExtractor` item schemas accept the dict form (`{"selector", "type", "attribute"}`)
  and an `html` type.
- Removed the unused `tenacity` dependency.
- Examples rewritten: five offline recipes against a bundled demo site, all run by the tests.
- README rewritten with verified snippets.

### Added
- `ScrapeFlowNotStartedError`, `ScrapeFlowConfigurationError`, `rate_limiter.effective_rate()`,
  and a `fetch_timeout` option on `RobotsChecker`.
- Tooling: ruff rules E, F, W, I, UP, B, SIM, C4, RUF, PTH, RET and PIE; `ruff format` replaces
  black; mypy with `check_untyped_defs` passes; CodeQL workflow; pre-commit config; CI coverage
  gate of 95% (suite at 96%, 94 tests).

## [0.4.0] - 2026-10-31

### Fixed
- LLM extraction works with current `mistralai` releases (2.x/3.x moved the client to
  `mistralai.client.Mistral`). Previously every LLM call failed with a misleading
  "mistralai is required" `ImportError` even though it was installed.
- The wheel no longer installs stray top-level `tests` and `examples` packages into
  `site-packages`.
- `create_mcp_backend()` no longer silently returns a do-nothing backend: unknown backend names
  raise `ValueError`, and the not-yet-implemented `scrapy_mcp` / `playwright_mcp` backends emit a
  `UserWarning`.
- Step timeouts chain the original `asyncio.TimeoutError` (`raise ... from`).
- Dockerfile: browsers are installed where `PLAYWRIGHT_BROWSERS_PATH` points, and `pytest` is
  available for the default `CMD` (the image previously could not run its own default command).

### Added
- `py.typed` marker (PEP 561) and `Typing :: Typed` classifier.
- `__version__` is read from installed package metadata (`importlib.metadata`).
- Tests: mocked Mistral schema generation and extraction (code-fence handling, bad JSON, async,
  new SDK layout), MCP backend factory, and real-browser tests against a local HTTP server
  (spec-driven extraction and robots.txt enforcement). 36 tests total.
- CHANGELOG, SECURITY.md, CODE_OF_CONDUCT.md, issue/PR templates, Dependabot, CITATION.cff.

### Changed
- Requires Python 3.10+ (3.8 and 3.9 are end-of-life); classifiers for 3.10 to 3.13.
- Packaging is `pyproject.toml`-only (removed `setup.py`, `pytest.ini`, `requirements*.txt`),
  with PEP 639 `license = "MIT"` and a `dev` extra (pytest, black, ruff, mypy, build, twine).
- CI: lint (ruff + black) is enforced instead of `|| true`, tests run on Python 3.10 to 3.13 with
  Chromium installed, and the Docker job now runs the test suite inside the image.
- Codebase formatted with black and cleaned with ruff (imports, modern type hints).

## [0.3.0] - 2026-03-09

### Added
- Hybrid extraction, Mistral LLM extraction, session persistence, content cleaning.

## [0.2.0] - 2026-03-09

### Added
- Specification-driven extraction, robots.txt compliance, ethical crawling, architecture refactor.

## [0.1.2] - 2025-11-27

- Initial public releases (0.1.0 to 0.1.2).
