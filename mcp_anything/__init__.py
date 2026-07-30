"""MCP-Anything: Generate MCP servers for any API, website, or service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_anything.generator import MCPServerGenerator
from mcp_anything.crawler import FirecrawlCrawler
from mcp_anything.analyzer import OpenAPIAnalyzer
from mcp_anything.llm import LLMBackend, create_llm, get_available_providers
from mcp_anything.enhancer import LLMEnhancedGenerator

__version__ = "0.3.0"

# ─── Core exports (always available) ───────────────────────────────────

_CORE_EXPORTS = [
    "MCPServerGenerator",
    "FirecrawlCrawler",
    "OpenAPIAnalyzer",
    "LLMBackend",
    "create_llm",
    "get_available_providers",
    "LLMEnhancedGenerator",
]

# ─── Optional SDK exports (lazy — import only when accessed) ──────────

_OPTIONAL_IMPORTS: dict[str, tuple[str, str, list[str]]] = {
    "ClaudeIntegration": ("mcp_anything.claude", "ClaudeIntegration", ["anthropic"]),
    "ClaudeEnhancedEndpoint": ("mcp_anything.claude", "ClaudeEnhancedEndpoint", ["anthropic"]),
    "ToolGroup": ("mcp_anything.claude", "ToolGroup", ["anthropic"]),
    "ClaudeEnhancedServerGenerator": (
        "mcp_anything.claude_generator", "ClaudeEnhancedGenerator", ["anthropic"]
    ),
    "OpenAIAgentsPipeline": (
        "mcp_anything.openai_agents", "OpenAIAgentsPipeline", ["agents"]
    ),
    "AgentPipelineResult": (
        "mcp_anything.openai_agents", "AgentPipelineResult", ["agents"]
    ),
}


def _lazy_import(name: str):
    mod_path, attr, deps = _OPTIONAL_IMPORTS[name]
    try:
        import importlib
        mod = importlib.import_module(mod_path)
        return getattr(mod, attr)
    except ImportError as e:
        missing = e.name
        raise ImportError(
            f"{name} requires the '{missing}' package. "
            f"Install it with: pip install mcp-anything[{deps[0]}]"
        ) from None


def __getattr__(name: str):
    if name in _OPTIONAL_IMPORTS:
        return _lazy_import(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(_CORE_EXPORTS + list(_OPTIONAL_IMPORTS.keys()))


__all__ = _CORE_EXPORTS + list(_OPTIONAL_IMPORTS.keys())
