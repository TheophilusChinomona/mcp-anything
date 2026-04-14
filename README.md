# 🔌 MCP-Anything

**Generate MCP servers for any API, website, or service — with pluggable LLM enhancement.**

Inspired by [CLI-Anything](https://github.com/HKUDS/CLI-Anything), MCP-Anything takes the same concept of auto-generating agent interfaces but targets the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) ecosystem instead of CLI tools.

## What It Does

Point MCP-Anything at any **OpenAPI spec** (URL or file) and it generates a complete **FastMCP server** with typed tools, ready to plug into any MCP client — Claude Desktop, OpenClaw, Cursor, or any agent platform.

```
OpenAPI Spec → MCP-Anything → Working MCP Server (19-73+ tools)
```

## Quick Start

```bash
# Install
pip install -e .

# Generate an MCP server from an OpenAPI spec
mcp-anything generate https://petstore3.swagger.io/api/v3/openapi.json

# With LLM enhancement for richer descriptions
mcp-anything generate spec.json --llm openai --llm-model gpt-4o

# Discover APIs from a website
mcp-anything discover https://api.example.com

# Inspect an API
mcp-anything info https://petstore3.swagger.io/api/v3/openapi.json

# List available LLM providers
mcp-anything llm-providers
```

## Generated Artifacts

For each API, MCP-Anything generates:

| File | Purpose |
|------|---------|
| `{name}_server.py` | FastMCP server with `@mcp.tool()` for every endpoint |
| `mcp_config.json` | Drop-in config block for MCP clients |
| `tools_inventory.json` | Machine-readable tool registry |
| `.env.example` | Credential template |
| `README.md` | Auto-generated docs with tool tables |

## LLM-Backed Enhancement

MCP-Anything supports **pluggable LLM backends** for enhanced generation:

| Provider | Default Model | Env Var | Use Case |
|----------|--------------|---------|----------|
| `hermes` | *(built-in)* | N/A | Zero cost, uses current session |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` | Cost-effective, fast |
| `anthropic` | `claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` | Best quality descriptions |
| `google` | `gemini-2.0-flash` | `GOOGLE_API_KEY` | Fast, free tier available |
| `openrouter` | `anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` | Access 100+ models |

```bash
# Use OpenAI for enhancement
mcp-anything generate spec.json --llm openai

# Use Anthropic Claude
mcp-anything generate spec.json --llm anthropic --llm-model claude-sonnet-4-20250514

# Use Gemini
mcp-anything generate spec.json --llm google

# Use OpenRouter (any model)
mcp-anything generate spec.json --llm openrouter --llm-model meta-llama/llama-4-maverick
```

### What LLM Enhancement Adds

- **Richer descriptions** — action-oriented docs suitable for AI agents
- **Usage examples** — realistic call patterns for each tool
- **Error handling notes** — what can go wrong and how to handle it
- **Parameter constraints** — gotchas, required combinations, rate limits

## Architecture

```
Phase 1: Analyze    → OpenAPIAnalyzer (parses spec, resolves $ref, extracts endpoints)
Phase 2: Design     → Maps endpoints → MCP tool definitions with JSON Schema
Phase 3: Enhance    → LLMEnhancedGenerator (optional, enriches descriptions)
Phase 4: Implement  → MCPServerGenerator (code gen with type annotations)
Phase 5: Tests      → (coming soon — conformance test generation)
Phase 6: Document   → Auto-generated README with tool tables
Phase 7: Publish    → mcp_config.json for instant MCP client integration
```

## Tiers

| Tier | Input | Method |
|------|-------|--------|
| **Tier 1** | OpenAPI/Swagger spec | Direct MCP server generation (highest fidelity) |
| **Tier 2** | Well-documented site | Firecrawl + doc scraping → spec discovery → generate |
| **Tier 3** | Arbitrary URL | Browser-interaction MCP server (coming soon) |

## MCP Client Integration

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "petstore": {
      "command": "python3",
      "args": ["/path/to/petstore_server.py"],
      "env": {
        "PETSTORE_BASE_URL": "https://petstore3.swagger.io/api/v3",
        "PETSTORE_API_KEY": ""
      }
    }
  }
}
```

### OpenClaw / Any MCP Client

Use the generated `mcp_config.json` directly.

## Programmatic Usage

```python
from mcp_anything import OpenAPIAnalyzer, MCPServerGenerator, create_llm

# Parse an OpenAPI spec
analyzer = OpenAPIAnalyzer("https://api.example.com/openapi.json")
analyzer.load()
endpoints = analyzer.extract_endpoints()

# Optional: enhance with LLM
llm = create_llm(provider="anthropic")
# ... use LLMEnhancedGenerator

# Generate MCP server
generator = MCPServerGenerator(analyzer, server_name="my-api")
result = generator.generate("./output/my-api")
print(f"Generated {result['tool_count']} tools")
```

## Development

```bash
# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Generate a test server
mcp-anything generate https://petstore3.swagger.io/api/v3/openapi.json --output ./test-output
```

## Roadmap

- [ ] Tier 3: Playwright-backed browser MCP servers for sites without APIs
- [ ] Test generation (Phase 5) — conformance + integration tests
- [ ] MCP-Hub registry — discover and install community-generated MCP servers
- [ ] Streaming support for large responses
- [ ] Authentication helpers (OAuth2, API keys, bearer tokens)
- [ ] Rate limiting and retry logic
- [ ] OpenClaw plugin integration

## Relationship to CLI-Anything

| | CLI-Anything | MCP-Anything |
|---|---|---|
| **Output** | Click CLI commands | FastMCP tools |
| **Target** | Desktop software | APIs & web services |
| **Protocol** | Shell/terminal | MCP (Model Context Protocol) |
| **Integration** | Claude Code, OpenClaw | Claude Desktop, OpenClaw, any MCP client |
| **LLM Enhancement** | Phase-based generation | Pluggable LLM backends |

## License

MIT
