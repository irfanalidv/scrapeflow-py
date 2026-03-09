"""Tests for shared component registry."""

from scrapeflow.registry import SelectorRegistry, register_quotes_login_handler


def test_register_quotes_login_handler():
    """Quotes login handler should be registered with expected selectors."""
    registry = SelectorRegistry()
    register_quotes_login_handler(registry)

    handler = registry.get_login("quotes_login")
    assert handler is not None
    assert handler.username_selector == 'input[name="username"]'
    assert handler.password_selector == 'input[name="password"]'
    assert handler.submit_selector == 'input[type="submit"]'
    assert handler.success_selector == 'a[href="/logout"]'
