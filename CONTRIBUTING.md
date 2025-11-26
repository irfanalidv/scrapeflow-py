# Contributing to ScrapeFlow

Thank you for your interest in contributing to ScrapeFlow! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/scrapeflow-py.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate it: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
5. Install dependencies: `pip install -r requirements-dev.txt`
6. Install Playwright browsers: `playwright install`

## Development Setup

```bash
# Install in development mode
pip install -e .

# Run tests
pytest

# Format code
black scrapeflow/

# Lint code
ruff check scrapeflow/

# Type checking
mypy scrapeflow/
```

## Code Style

- Follow PEP 8 style guide
- Use type hints for all functions
- Write docstrings for all public functions and classes
- Keep line length to 100 characters
- Use `black` for code formatting
- Use `ruff` for linting

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

