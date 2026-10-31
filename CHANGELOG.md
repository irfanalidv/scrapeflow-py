# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
