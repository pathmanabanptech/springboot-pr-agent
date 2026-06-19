import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from app.llm import get_llm


def _fake_module(name: str, **attrs) -> ModuleType:
    """Create a throwaway module with the given attributes."""
    mod = ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unsupported MODEL_PROVIDER"):
        get_llm("ollama", "some-model", "key")


def test_provider_name_is_case_insensitive():
    with patch("langchain_anthropic.ChatAnthropic") as MockChat:
        get_llm("Anthropic", "claude-haiku-4-5", "key")
        MockChat.assert_called_once()

    with pytest.raises(ValueError):
        get_llm("BEDROCK", "model", "key")


def test_anthropic_provider():
    # langchain_anthropic is already installed — patch it directly
    with patch("langchain_anthropic.ChatAnthropic") as MockChat:
        get_llm("anthropic", "claude-haiku-4-5", "sk-ant-test")
        MockChat.assert_called_once_with(model="claude-haiku-4-5", api_key="sk-ant-test", max_tokens=4096)


def test_openai_provider():
    MockChatOpenAI = MagicMock()
    fake_mod = _fake_module("langchain_openai", ChatOpenAI=MockChatOpenAI)
    with patch.dict(sys.modules, {"langchain_openai": fake_mod}):
        get_llm("openai", "gpt-4o-mini", "sk-test")
    MockChatOpenAI.assert_called_once_with(model="gpt-4o-mini", api_key="sk-test", max_tokens=4096)


def test_google_provider():
    MockChatGoogle = MagicMock()
    fake_mod = _fake_module("langchain_google_genai", ChatGoogleGenerativeAI=MockChatGoogle)
    with patch.dict(sys.modules, {"langchain_google_genai": fake_mod}):
        get_llm("google", "gemini-1.5-flash", "AIza-test")
    MockChatGoogle.assert_called_once_with(
        model="gemini-1.5-flash", google_api_key="AIza-test", max_output_tokens=4096
    )


def test_huggingface_provider():
    MockEndpoint = MagicMock()
    MockChatHF = MagicMock()
    fake_mod = _fake_module(
        "langchain_huggingface",
        HuggingFaceEndpoint=MockEndpoint,
        ChatHuggingFace=MockChatHF,
    )
    with patch.dict(sys.modules, {"langchain_huggingface": fake_mod}):
        get_llm("huggingface", "mistralai/Mistral-7B-Instruct-v0.3", "hf_test")

    MockEndpoint.assert_called_once_with(
        repo_id="mistralai/Mistral-7B-Instruct-v0.3",
        huggingfacehub_api_token="hf_test",
        max_new_tokens=4096,
    )
    MockChatHF.assert_called_once_with(llm=MockEndpoint.return_value)
