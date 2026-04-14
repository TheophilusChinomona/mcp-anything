"""MCP-Anything: Generate MCP servers for any API, website, or service."""

from mcp_anything.generator import MCPServerGenerator
from mcp_anything.crawler import FirecrawlCrawler
from mcp_anything.analyzer import OpenAPIAnalyzer
from mcp_anything.llm import LLMBackend, create_llm, get_available_providers
from mcp_anything.enhancer import LLMEnhancedGenerator

__version__ = "0.1.0"
__all__ = [
    "MCPServerGenerator",
    "FirecrawlCrawler",
    "OpenAPIAnalyzer",
    "LLMBackend",
    "create_llm",
    "get_available_providers",
    "LLMEnhancedGenerator",
]
