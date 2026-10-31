# Contributing to ScrapeFlow

Thank you for your interest in contributing to ScrapeFlow! This document provides guidelines and instructions for contributing.

## License & Third-Party Code

ScrapeFlow is MIT-licensed. When contributing:

- **Do not copy or paste code** from AGPL, GPL, or other copyleft-licensed projects. Implement patterns from scratch.
- **Ideas and concepts** (e.g. "schema-from-prompt", pagination limits) are not copyrightable—original implementations are fine.
- If you use third-party libraries, ensure they are compatible with MIT (permissive licenses like MIT, Apache 2.0, BSD).

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/scrapeflow-py.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate it: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
5. Install dependencies: `pip install -e ".[dev]"` and `playwright install chromium`
6. Install Playwright browsers: `playwright install`

## Development Setup

```bash
# Install in development mode (or: uv pip install -e ".[dev]")
pip install -e ".[dev]"
playwright install chromium

# Optional: run ruff automatically on every commit
pre-commit install

# The same checks CI runs
ruff check .
ruff format --check .
mypy scrapeflow
pytest --cov=scrapeflow --cov-fail-under=95
```

Tests never touch the internet: browser tests use a local `http.server`, and LLM calls are
mocked. The examples in `examples/` are run by `tests/test_examples.py`.

## Code Style

- Follow PEP 8 style guide
- Use type hints for all functions
- Write docstrings for all public functions and classes
- Keep line length to 100 characters
- Use `ruff format` for formatting and `ruff check` for linting

## Writing Tests

- Write tests for all new features
- Aim for high test coverage
- Use `pytest` and `pytest-asyncio` for async tests
- Place tests in `tests/` directory

## Submitting Changes

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Write or update tests
4. Ensure all tests pass
5. Format and lint your code
6. Commit your changes: `git commit -m 'Add feature: description'`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Open a Pull Request

## Pull Request Guidelines

- Provide a clear description of changes
- Reference any related issues
- Ensure all CI checks pass
- Update documentation if needed
- Add examples if introducing new features

## Reporting Issues

When reporting issues, please include:

- Python version
- ScrapeFlow version
- Playwright version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages or logs

## Feature Requests

Feature requests are welcome! Please:

- Check if the feature already exists
- Explain the use case
- Describe the expected behavior
- Consider implementation complexity

Thank you for contributing to ScrapeFlow! 🎉

