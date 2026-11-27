import pytest
from src.assistant.ai import ollama_generate_url

@pytest.mark.parametrize("base,expected",[
    (None,"http://127.0.0.1:11434/api/generate"),
    ("http://host.docker.internal:11434","http://host.docker.internal:11434/api/generate"),
    ("http://127.0.0.1:11434/","http://127.0.0.1:11434/api/generate"),
    ("https://example.com",None),
    ("http://host.docker.internal:11434.evil.test",None),
    ("http://127.0.0.1:11434@evil.test",None),
])
def test_allowed_ollama_endpoint(monkeypatch,base,expected):
    if base is None:monkeypatch.delenv("OLLAMA_BASE_URL",raising=False)
    else:monkeypatch.setenv("OLLAMA_BASE_URL",base)
    assert ollama_generate_url()==expected
