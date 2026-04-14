"""
LLM Backend - Pluggable LLM abstraction for MCP-Anything.

Supports multiple backends:
  - hermes: Uses hermes_tools (built-in, no extra cost)
  - openai: OpenAI API (GPT-4o, etc.)
  - anthropic: Anthropic API (Claude)
  - google: Google Gemini API
  - openrouter: OpenRouter (access to many models)

Usage:
    llm = LLMBackend.from_config({"provider": "hermes"})
    result = llm.complete("Explain this API endpoint...")
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMResponse:
    """Standardized response from any LLM backend."""
    content: str
    model: str = ""
    provider: str = ""
    usage: dict = field(default_factory=dict)  # prompt_tokens, completion_tokens, etc.
    raw: Any = None  # original response object


class LLMBackend(ABC):
    """Abstract base for LLM backends."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a completion request and return a standardized response."""
        ...

    @abstractmethod
    def complete_json(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.0,
    ) -> dict:
        """Send a completion request expecting JSON output. Returns parsed dict."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...


# ─── Hermes Backend (built-in, no extra API cost) ────────────────────────────

class HermesBackend(LLMBackend):
    """Uses hermes_tools for local/in-process LLM calls.

    This is the zero-cost option — it leverages whatever model
    is already powering the current Hermes session.
    """

    def __init__(self, model: str = ""):
        self._model = model

    @property
    def name(self) -> str:
        return "hermes"

    def complete(self, prompt: str, system: str = "", temperature: float = 0.0, max_tokens: int = 4096) -> LLMResponse:
        # Hermes doesn't expose a direct LLM call API, so we use
        # the execute_code approach with a subprocess to itself.
        # For now, this is a placeholder that delegates to openai-compatible.
        raise NotImplementedError(
            "Hermes backend works inline — use it from within the MCP-Anything "
            "pipeline where the calling agent (Hermes/Claude) handles the LLM work."
        )

    def complete_json(self, prompt: str, system: str = "", temperature: float = 0.0) -> dict:
        raise NotImplementedError("Same as complete()")


# ─── OpenAI Backend ──────────────────────────────────────────────────────────

class OpenAIBackend(LLMBackend):
    """OpenAI API backend (GPT-4o, GPT-4o-mini, o3-mini, etc.)."""

    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def complete(self, prompt: str, system: str = "", temperature: float = 0.0, max_tokens: int = 4096) -> LLMResponse:
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return LLMResponse(
            content=resp.choices[0].message.content or "",
            model=resp.model,
            provider=self.name,
            usage={
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            },
            raw=resp,
        )

    def complete_json(self, prompt: str, system: str = "", temperature: float = 0.0) -> dict:
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content or "{}")


# ─── Anthropic Backend ───────────────────────────────────────────────────────

class AnthropicBackend(LLMBackend):
    """Anthropic API backend (Claude Sonnet, Haiku, Opus)."""

    def __init__(self, api_key: str = "", model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self._client = None

    @property
    def name(self) -> str:
        return "anthropic"

    def _get_client(self):
        if self._client is None:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def complete(self, prompt: str, system: str = "", temperature: float = 0.0, max_tokens: int = 4096) -> LLMResponse:
        client = self._get_client()
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        resp = client.messages.create(**kwargs)
        content = "".join(block.text for block in resp.content if hasattr(block, "text"))
        return LLMResponse(
            content=content,
            model=resp.model,
            provider=self.name,
            usage={
                "prompt_tokens": resp.usage.input_tokens,
                "completion_tokens": resp.usage.output_tokens,
            },
            raw=resp,
        )

    def complete_json(self, prompt: str, system: str = "", temperature: float = 0.0) -> dict:
        json_prompt = prompt + "\n\nRespond ONLY with valid JSON. No markdown, no explanation."
        resp = self.complete(json_prompt, system, temperature)
        # Try to extract JSON from potential markdown wrapping
        content = resp.content.strip()
        if content.startswith("```"):
            content = "\n".join(content.split("\n")[1:-1])
        return json.loads(content)


# ─── Google Gemini Backend ───────────────────────────────────────────────────

class GeminiBackend(LLMBackend):
    """Google Gemini API backend."""

    def __init__(self, api_key: str = "", model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.model = model

    @property
    def name(self) -> str:
        return "google"

    def complete(self, prompt: str, system: str = "", temperature: float = 0.0, max_tokens: int = 4096) -> LLMResponse:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            self.model,
            system_instruction=system if system else None,
        )
        resp = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return LLMResponse(
            content=resp.text,
            model=self.model,
            provider=self.name,
            usage={
                "prompt_tokens": resp.usage_metadata.prompt_token_count,
                "completion_tokens": resp.usage_metadata.candidates_token_count,
            },
            raw=resp,
        )

    def complete_json(self, prompt: str, system: str = "", temperature: float = 0.0) -> dict:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            self.model,
            system_instruction=system if system else None,
        )
        resp = model.generate_content(
            prompt + "\n\nRespond ONLY with valid JSON.",
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        return json.loads(resp.text)


# ─── OpenRouter Backend ──────────────────────────────────────────────────────

class OpenRouterBackend(LLMBackend):
    """OpenRouter backend — access 100+ models via unified API."""

    def __init__(self, api_key: str = "", model: str = "anthropic/claude-sonnet-4"):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    @property
    def name(self) -> str:
        return "openrouter"

    def _request(self, messages: list[dict], temperature: float = 0.0, max_tokens: int = 4096, response_format: dict = None) -> dict:
        import httpx
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def complete(self, prompt: str, system: str = "", temperature: float = 0.0, max_tokens: int = 4096) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data = self._request(messages, temperature, max_tokens)
        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"]["content"] or "",
            model=data.get("model", self.model),
            provider=self.name,
            usage=data.get("usage", {}),
            raw=data,
        )

    def complete_json(self, prompt: str, system: str = "", temperature: float = 0.0) -> dict:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data = self._request(messages, temperature, response_format={"type": "json_object"})
        return json.loads(data["choices"][0]["message"]["content"] or "{}")


# ─── Factory ─────────────────────────────────────────────────────────────────

BACKENDS = {
    "hermes": HermesBackend,
    "openai": OpenAIBackend,
    "anthropic": AnthropicBackend,
    "google": GeminiBackend,
    "gemini": GeminiBackend,  # alias
    "openrouter": OpenRouterBackend,
}


def create_llm(
    provider: str = "",
    model: str = "",
    api_key: str = "",
    config: dict = None,
) -> LLMBackend:
    """
    Factory function to create an LLM backend.

    Priority:
      1. Explicit config dict: {"provider": "openai", "model": "gpt-4o", "api_key": "..."}
      2. Explicit args: provider="anthropic", model="claude-sonnet-4"
      3. Environment variables: MCP_ANYTHING_LLM_PROVIDER, MCP_ANYTHING_LLM_MODEL
      4. Default: openai with gpt-4o-mini

    Config dict format:
        {
            "provider": "openai|anthropic|google|gemini|openrouter|hermes",
            "model": "gpt-4o",  # optional, uses provider default
            "api_key": "sk-...",  # optional, falls back to env vars
        }
    """
    if config:
        provider = config.get("provider", provider)
        model = config.get("model", model)
        api_key = config.get("api_key", api_key)

    if not provider:
        provider = os.environ.get("MCP_ANYTHING_LLM_PROVIDER", "openai")

    provider = provider.lower()
    if provider not in BACKENDS:
        raise ValueError(f"Unknown LLM provider: {provider}. Available: {list(BACKENDS.keys())}")

    backend_cls = BACKENDS[provider]

    # Build kwargs
    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    if model:
        kwargs["model"] = model

    return backend_cls(**kwargs)


def get_available_providers() -> list[dict]:
    """Return list of available providers with their default models and env var names."""
    return [
        {"provider": "hermes", "default_model": "(built-in)", "env_var": "N/A", "note": "Zero cost, uses current session model"},
        {"provider": "openai", "default_model": "gpt-4o-mini", "env_var": "OPENAI_API_KEY"},
        {"provider": "anthropic", "default_model": "claude-sonnet-4-20250514", "env_var": "ANTHROPIC_API_KEY"},
        {"provider": "google", "default_model": "gemini-2.0-flash", "env_var": "GOOGLE_API_KEY"},
        {"provider": "openrouter", "default_model": "anthropic/claude-sonnet-4", "env_var": "OPENROUTER_API_KEY"},
    ]
