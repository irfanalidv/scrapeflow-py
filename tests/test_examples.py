"""Run every offline example end to end so the README's recipes cannot silently rot."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import requires_browser

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

EXPECTED = {
    "price_monitor.py": "9 books, 7 in stock",
    "polite_crawler.py": "skipped /admin/index.html",
    "resilient_workflow.py": "'rates' step attempts: 2",
    "login_session_reuse.py": "member price: Signals and Noise",
    "hybrid_llm_fallback.py": "'name': 'Signals and Noise'",
}


@requires_browser
@pytest.mark.parametrize("script", sorted(EXPECTED))
def test_example_runs_offline(script: str) -> None:
    proc = subprocess.run(
        [sys.executable, str(EXAMPLES / script)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert EXPECTED[script] in proc.stdout


def test_every_example_is_covered() -> None:
    scripts = {p.name for p in EXAMPLES.glob("*.py") if not p.name.startswith("_")}
    assert scripts == set(EXPECTED)
