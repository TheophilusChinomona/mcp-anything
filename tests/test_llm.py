"""Tests for LLM backend abstraction."""

import pytest
from mcp_anything.llm import (
    create_llm,
    get_available_providers,
    BACKENDS,
    OpenAIBackend,
    AnthropicBackend,
    GeminiBackend,
    OpenRouterBackend,
    HermesBackend,
)


class TestLLMFactory:
    """Test the LLM backend factory."""

    def test_get_available_providers(self):
        """Returns a list of provider dicts."""
        providers = get_available_providers()
        assert isinstance(providers, list)
        assert len(providers) >= 5
        provider_names = [p["provider"] for p in providers]
        assert "hermes" in provider_names
        assert "openai" in provider_names
        assert "anthropic" in provider_names
        assert "google" in provider_names
        assert "openrouter" in provider_names

    def test_create_openai_backend(self):
        """Can create an OpenAI backend."""
        llm = create_llm(provider="openai", api_key="test-key")
        assert isinstance(llm, OpenAIBackend)
        assert llm.name == "openai"
        assert llm.api_key == "test-key"

    def test_create_anthropic_backend(self):
        """Can create an Anthropic backend."""
        llm = create_llm(provider="anthropic", api_key="test-key")
        assert isinstance(llm, AnthropicBackend)
        assert llm.name == "anthropic"

    def test_create_google_backend(self):
        """Can create a Google/Gemini backend."""
        llm = create_llm(provider="google", api_key="test-key")
        assert isinstance(llm, GeminiBackend)
        assert llm.name == "google"

    def test_create_gemini_alias(self):
        """'gemini' is an alias for 'google'."""
        llm = create_llm(provider="gemini", api_key="test-key")
        assert isinstance(llm, GeminiBackend)

    def test_create_openrouter_backend(self):
        """Can create an OpenRouter backend."""
        llm = create_llm(provider="openrouter", api_key="test-key")
        assert isinstance(llm, OpenRouterBackend)
        assert llm.name == "openrouter"

    def test_create_hermes_backend(self):
        """Can create a Hermes backend."""
        llm = create_llm(provider="hermes")
        assert isinstance(llm, HermesBackend)
        assert llm.name == "hermes"

    def test_create_from_config_dict(self):
        """Can create from a config dict."""
        llm = create_llm(config={"provider": "openai", "api_key": "test-key", "model": "gpt-4o"})
        assert isinstance(llm, OpenAIBackend)
        assert llm.model == "gpt-4o"
        assert llm.api_key == "test-key"

    def test_unknown_provider_raises(self):
        """Unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_llm(provider="not-a-provider")

    def test_default_provider_is_openai(self):
        """Default provider is openai when none specified."""
        llm = create_llm(api_key="test-key")
        assert isinstance(llm, OpenAIBackend)

    def test_custom_model(self):
        """Can specify custom model."""
        llm = create_llm(provider="openrouter", model="meta-llama/llama-4-maverick", api_key="test")
        assert llm.model == "meta-llama/llama-4-maverick"

    def test_all_backends_registered(self):
        """All expected backends are in the registry."""
        assert "hermes" in BACKENDS
        assert "openai" in BACKENDS
        assert "anthropic" in BACKENDS
        assert "google" in BACKENDS
        assert "gemini" in BACKENDS
        assert "openrouter" in BACKENDS


class TestBackendDefaults:
    """Test default models for each backend."""

    def test_openai_default_model(self):
        llm = OpenAIBackend(api_key="test")
        assert llm.model == "gpt-4o-mini"

    def test_anthropic_default_model(self):
        llm = AnthropicBackend(api_key="test")
        assert "claude" in llm.model

    def test_gemini_default_model(self):
        llm = GeminiBackend(api_key="test")
        assert "gemini" in llm.model

    def test_openrouter_default_model(self):
        llm = OpenRouterBackend(api_key="test")
        assert "/" in llm.model  # OpenRouter models have provider/model format
