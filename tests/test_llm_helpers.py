"""LLM helper tests (no network: the Mistral client is never constructed for real)."""

from __future__ import annotations

import types

import pytest

from scrapeflow import llm_extract
from scrapeflow.exceptions import ScrapeFlowConfigurationError


def _response(content: object) -> types.SimpleNamespace:
    msg = types.SimpleNamespace(content=content)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


def test_message_text_variants() -> None:
    assert llm_extract._message_text(_response("hi")) == "hi"
    assert llm_extract._message_text(_response(None)) == ""
    chunks = [types.SimpleNamespace(text='{"a"'), types.SimpleNamespace(text=": 1}")]
    assert llm_extract._message_text(_response(chunks)) == '{"a": 1}'
    assert llm_extract._message_text(types.SimpleNamespace(choices=[])) == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n{"a": 1}\n```  ', '{"a": 1}'),
        ('```json\n{"a": 1}', '{"a": 1}'),
    ],
)
def test_strip_code_fence(raw: str, expected: str) -> None:
    assert llm_extract._strip_code_fence(raw) == expected


def test_generate_schema_falls_back_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(complete=lambda **kw: _response("not json"))
    )
    monkeypatch.setattr(llm_extract, "_get_mistral_client", lambda: client)
    assert llm_extract.generate_schema_from_prompt("x") == {"type": "object", "properties": {}}


def test_extract_with_schema_sends_prompt_and_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, object] = {}

    def complete(**kwargs: object) -> types.SimpleNamespace:
        sent.update(kwargs)
        return _response('```json\n{"title": "T"}\n```')

    client = types.SimpleNamespace(chat=types.SimpleNamespace(complete=complete))
    monkeypatch.setattr(llm_extract, "_get_mistral_client", lambda: client)
    content = "x" * (llm_extract.MAX_CONTENT_CHARS + 500)
    out = llm_extract.extract_with_schema(content, {"type": "object"}, prompt="Get title")
    assert out == {"title": "T"}
    messages = sent["messages"]
    assert isinstance(messages, list)
    user = messages[1]["content"]
    assert user.startswith("Extraction request: Get title")
    assert user.endswith("Page content:\n" + "x" * llm_extract.MAX_CONTENT_CHARS)
    assert "UNTRUSTED" in messages[0]["content"]

    monkeypatch.setattr(
        llm_extract,
        "_get_mistral_client",
        lambda: types.SimpleNamespace(
            chat=types.SimpleNamespace(complete=lambda **kw: _response(""))
        ),
    )
    assert llm_extract.extract_with_schema("c", {}) == {}


def test_api_key_from_env_and_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "from-env")
    assert llm_extract._get_api_key() == "from-env"

    monkeypatch.delenv("MISTRAL_API_KEY")
    (tmp_path / ".env").write_text("MISTRAL_API_KEY=from-dotenv\n")
    monkeypatch.chdir(tmp_path)
    try:
        assert llm_extract._get_api_key() == "from-dotenv"
    finally:
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)


def test_missing_key_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_extract, "_get_api_key", lambda: "")
    with pytest.raises(ScrapeFlowConfigurationError, match="MISTRAL_API_KEY"):
        llm_extract._get_mistral_client()


def test_missing_sdk_raises_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_module(name: str) -> None:
        raise ImportError(name)

    monkeypatch.setattr(llm_extract.importlib, "import_module", no_module)
    with pytest.raises(ImportError, match="pip install mistralai"):
        llm_extract._get_mistral_client()
