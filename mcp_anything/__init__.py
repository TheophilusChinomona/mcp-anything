"""MCP-Anything: Generate MCP servers for any API, website, or service."""

from mcp_anything.generator import MCPServerGenerator
from mcp_anything.crawler import FirecrawlCrawler
from mcp_anything.analyzer import OpenAPIAnalyzer
from mcp_anything.llm import LLMBackend, create_llm, get_available_providers
from mcp_anything.enhancer import LLMEnhancedGenerator
from mcp_anything.claude import ClaudeIntegration, ClaudeEnhancedEndpoint, ToolGroup
from mcp_anything.claude_generator import ClaudeEnhancedGenerator as ClaudeEnhancedServerGenerator
from mcp_anything.openai_agents import OpenAIAgentsPipeline, AgentPipelineResult

__version__ = "0.3.0"
__all__ = [
    # Core
    "MCPServerGenerator",
    "FirecrawlCrawler",
    "OpenAPIAnalyzer",
    # LLM abstraction
    "LLMBackend",
    "create_llm",
    "get_available_providers",
    "LLMEnhancedGenerator",
    # Claude SDK
    "ClaudeIntegration",
    "ClaudeEnhancedEndpoint",
    "ToolGroup",
    "ClaudeEnhancedServerGenerator",
    # OpenAI Agents SDK
    "OpenAIAgentsPipeline",
    "AgentPipelineResult",
]
