"""
Content cleaning and normalization for extraction.

Strips noise (scripts, styles) and normalizes text before LLM or validation.
"""

import re
from typing import Optional


def clean_html_for_llm(html: str, max_chars: int = 120000) -> str:
    """
    Clean HTML for LLM extraction: remove scripts, styles, normalize whitespace.

    Reduces token usage and improves extraction accuracy.
    """
    if not html:
        return ""

    # Remove script and style blocks
    html = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<noscript[^>]*>[\s\S]*?</noscript>", "", html, flags=re.IGNORECASE)

    # Replace block elements with newlines for readability
    for tag in ["br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"]:
        html = re.sub(rf"</{tag}>", "\n", html, flags=re.IGNORECASE)

    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", html)

    # Decode common entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = text.strip()

    return text[:max_chars] if max_chars else text


def html_to_plain_text(html: str) -> str:
    """Convert HTML to plain text, preserving structure with newlines."""
    return clean_html_for_llm(html, max_chars=0)
