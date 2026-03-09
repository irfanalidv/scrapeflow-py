"""Tests for content cleaning utilities."""

import pytest
from scrapeflow.content_utils import clean_html_for_llm, html_to_plain_text


def test_clean_html_removes_scripts():
    html = "<html><body><script>alert(1)</script><p>Hello</p></body></html>"
    result = clean_html_for_llm(html)
    assert "alert" not in result
    assert "Hello" in result


def test_clean_html_removes_styles():
    html = "<html><style>.x{color:red}</style><p>Text</p></html>"
    result = clean_html_for_llm(html)
    assert "color" not in result
    assert "Text" in result


def test_clean_html_normalizes_whitespace():
    html = "<p>  Hello   \n\n  World  </p>"
    result = clean_html_for_llm(html)
    assert "  " not in result or result.strip() == result


def test_clean_html_respects_max_chars():
    html = "<p>" + "x" * 200000 + "</p>"
    result = clean_html_for_llm(html, max_chars=1000)
    assert len(result) <= 1000


def test_html_to_plain_text():
    html = "<div><p>Line 1</p><p>Line 2</p></div>"
    result = html_to_plain_text(html)
    assert "Line 1" in result
    assert "Line 2" in result
