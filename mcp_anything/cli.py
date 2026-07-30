"""CLI entry point for MCP-Anything."""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path

from mcp_anything.analyzer import OpenAPIAnalyzer
from mcp_anything.generator import MCPServerGenerator
from mcp_anything.crawler import FirecrawlCrawler
from mcp_anything.llm import create_llm, get_available_providers
from mcp_anything.openai_agents import OpenAIAgentsPipeline


BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║  🔌 MCP-Anything: Generate MCP Servers for Any API              ║
║  🤖 LLM • 🧠 Claude SDK • 🤝 OpenAI Agents SDK + OpenRouter     ║
╚══════════════════════════════════════════════════════════════════╝
"""


def banner():
    print(BANNER)


def generate_from_spec(
    spec_source: str,
    output_dir: str,
    server_name: str = "",
    env_prefix: str = "",
    llm_config: dict | None = None,
    use_claude: bool = False,
    claude_model: str = "claude-sonnet-4-20250514",
    use_agents: bool = False,
    agents_model: str = "anthropic/claude-sonnet-4",
    agents_provider: str = "openrouter",
    include_tests: bool = False,
    allow_writes: bool = False,
    allowed_tags: set[str] | None = None,
    allowed_operations: set[str] | None = None,
    denied_operations: set[str] | None = None,
):
    """Generate MCP server from an OpenAPI spec."""
    print(f"📋 Loading OpenAPI spec: {spec_source[:80]}...")
    analyzer = OpenAPIAnalyzer(spec_source)
    analyzer.load()

    summary = analyzer.summary()
    print(f"✅ Loaded: {summary['title']} v{summary['version']}")
    print(f"   Base URL: {summary['base_url']}")
    print(f"   Endpoints: {summary['endpoint_count']}")

    endpoints = analyzer.extract_endpoints()
    print(f"   Extracted {len(endpoints)} tool definitions")

    # ── OpenAI Agents SDK mode ──
    if use_agents:
        print(f"\n🤝 OpenAI Agents SDK Mode")
        print(f"   Model: {agents_model}")
        print(f"   Provider: {agents_provider}")
        print(f"   Running 3-agent pipeline: Analyzer → Designer → Generator")

        pipeline = OpenAIAgentsPipeline(
            model=agents_model,
            provider=agents_provider,
        )

        def on_progress(agent, msg):
            icons = {"analyzer": "📋", "designer": "📐", "generator": "🔨", "done": "✅"}
            print(f"   {icons.get(agent, '•')} [{agent}] {msg}")

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()

        result = loop.run_until_complete(pipeline.run(
            spec_source=spec_source,
            output_dir=output_dir,
            server_name=server_name,
            on_progress=on_progress,
        ))

        print(f"\n✅ Generated MCP Server via OpenAI Agents!")
        print(f"   Server:  {result.server_file or '(see output dir)'}")
        print(f"   Config:  {result.config_file or '(see output dir)'}")
        print(f"   Tools:   {result.tool_count}")
        print(f"   Groups:  {result.group_count}")
        print(f"   Model:   {result.model}")
        return {
            "server_file": result.server_file,
            "config_file": result.config_file,
            "tool_count": result.tool_count,
            "group_count": result.group_count,
            "server_name": server_name,
        }

    # ── Claude-native enhancement ──
    if use_claude:
        print(f"\n🧠 Claude Enhancement Mode ({claude_model})")
        print(f"   Using Anthropic SDK with native tool_use...")

        from mcp_anything.claude_generator import ClaudeEnhancedGenerator

        def on_progress(step, detail):
            icons = {"analyze": "📋", "enhance": "🧠", "generate": "🔨", "write": "💾", "done": "✅"}
            print(f"   {icons.get(step, '•')} {step}: {detail}")

        generator = ClaudeEnhancedGenerator(
            analyzer=analyzer,
            model=claude_model,
            batch_size=5,
        )
        result = generator.generate(
            output_dir=output_dir,
            server_name=server_name,
            env_prefix=env_prefix,
            include_groups=True,
            include_tests=include_tests,
            on_progress=on_progress,
        )

        print(f"\n✅ Generated Claude-Enhanced MCP Server!")
        print(f"   Server:  {result['server_file']}")
        print(f"   Config:  {result['config_file']}")
        print(f"   Tools:   {result['tool_count']} enhanced tools")
        print(f"   Groups:  {result['group_count']} logical workflows")
        print(f"   Model:   {result['claude_model']}")

        enh = result["enhancement_summary"]
        print(f"\n📊 Enhancement Stats:")
        print(f"   With examples:      {enh.get('with_examples', 0)}")
        print(f"   With error handling:{enh.get('with_error_handling', 0)}")
        print(f"   With prerequisites: {enh.get('with_prerequisites', 0)}")

        return result

    # Standard LLM enhancement (non-Claude)
    if llm_config:
        print(f"\n🤖 Enhancing with LLM ({llm_config.get('provider', 'default')}...")
        try:
            from mcp_anything.enhancer import LLMEnhancedGenerator
            llm = create_llm(config=llm_config)
            enhancer = LLMEnhancedGenerator(analyzer, llm=llm)
            enhanced = enhancer.enhance_all()
            enh_summary = enhancer.get_enhancement_summary()
            print(f"   Enhanced {enh_summary['total_tools']} tools")
        except Exception as e:
            print(f"   ⚠️  LLM enhancement failed: {e}")
            print(f"   Continuing with standard generation...")

    # Standard generation
    print(f"\n🔨 Generating MCP server...")
    generator = MCPServerGenerator(
        analyzer,
        server_name=server_name,
        env_prefix=env_prefix,
        allow_writes=allow_writes,
        allowed_tags=allowed_tags,
        allowed_operations=allowed_operations,
        denied_operations=denied_operations,
    )
    result = generator.generate(output_dir)

    print(f"\n✅ Generated MCP server!")
    print(f"   Server:  {result['server_file']}")
    print(f"   Config:  {result['config_file']}")
    print(f"   Tools:   {result['tool_count']} MCP tools")
    print(f"   Output:  {output_dir}")
    print(f"\n📋 To use:")
    print(f"   1. Set {result['server_name'].upper().replace('-','_')}_BASE_URL and _API_KEY in .env")
    print(f"   2. Add mcp_config.json contents to your MCP client")
    print(f"   3. pip install fastmcp httpx")

    return result


def discover_from_url(url: str, output_dir: str, firecrawl_key: str = "", server_name: str = ""):
    """Tier 2: Discover API from a website and generate MCP server."""
    crawler = FirecrawlCrawler(api_key=firecrawl_key)

    print(f"🌐 Crawling {url} for API documentation...")
    results = crawler.discover_api_docs(url)
    print(f"   Found {len(results)} documentation pages")

    print(f"🔍 Extracting API structure from docs...")
    api_info = crawler.extract_api_from_docs(results)
    print(f"   Discovered {len(api_info['endpoints'])} endpoint references")

    print(f"🔎 Looking for OpenAPI specs...")
    specs = crawler.extract_openapi_specs(url)
    if specs:
        print(f"   Found OpenAPI spec: {specs[0]}")
        return generate_from_spec(specs[0], output_dir, server_name=server_name)

    print(f"⚠️  No OpenAPI spec found. Web scraping results saved.")
    discovery_file = Path(output_dir) / "discovery.json"
    discovery_file.parent.mkdir(parents=True, exist_ok=True)
    discovery_file.write_text(json.dumps(api_info, indent=2))
    print(f"   Discovery data: {discovery_file}")

    return api_info


def list_providers():
    """List available LLM providers."""
    print("🤖 Available LLM Providers:\n")
    print(f"  {'Provider':<15} {'Default Model':<35} {'Env Var':<25}")
    print(f"  {'─'*15} {'─'*35} {'─'*25}")
    for p in get_available_providers():
        print(f"  {p['provider']:<15} {p['default_model']:<35} {p['env_var']:<25}")
    print(f"\n🧠 Claude-Native Mode (recommended):")
    print(f"   mcp-anything generate spec.json --claude")
    print(f"   Uses Anthropic SDK with native tool_use for richer output")
    print(f"\n💡 Generic LLM mode:")
    print(f"   mcp-anything generate spec.json --llm openai")
    print(f"   Set MCP_ANYTHING_LLM_PROVIDER to auto-select")


def parse_args(args: list[str]) -> dict:
    """Parse all CLI flags into a config dict."""
    config = {
        "output": "./output",
        "name": "",
        "env_prefix": "",
        "firecrawl_key": os.environ.get("FIRECRAWL_API_KEY", ""),
        "llm": None,
        "claude": False,
        "claude_model": "claude-sonnet-4-20250514",
        "agents": False,
        "agents_model": "anthropic/claude-sonnet-4",
        "agents_provider": "openrouter",
        "include_tests": False,
        "allow_writes": False,
        "allowed_tags": set(),
        "allowed_operations": set(),
        "denied_operations": set(),
        "positional": [],
    }

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--output" and i + 1 < len(args):
            config["output"] = args[i + 1]; i += 2
        elif arg == "--name" and i + 1 < len(args):
            config["name"] = args[i + 1]; i += 2
        elif arg == "--env-prefix" and i + 1 < len(args):
            config["env_prefix"] = args[i + 1]; i += 2
        elif arg == "--firecrawl-key" and i + 1 < len(args):
            config["firecrawl_key"] = args[i + 1]; i += 2
        elif arg == "--claude":
            config["claude"] = True; i += 1
        elif arg == "--claude-model" and i + 1 < len(args):
            config["claude"] = True
            config["claude_model"] = args[i + 1]; i += 2
        elif arg == "--include-tests":
            config["include_tests"] = True; i += 1
        elif arg == "--agents":
            config["agents"] = True; i += 1
        elif arg == "--agents-model" and i + 1 < len(args):
            config["agents"] = True
            config["agents_model"] = args[i + 1]; i += 2
        elif arg == "--agents-provider" and i + 1 < len(args):
            config["agents_provider"] = args[i + 1]; i += 2
        elif arg == "--llm" and i + 1 < len(args):
            config["llm"] = {"provider": args[i + 1]}; i += 2
        elif arg == "--llm-model" and i + 1 < len(args):
            if config["llm"] is None:
                config["llm"] = {}
            config["llm"]["model"] = args[i + 1]; i += 2
        elif arg == "--llm-key" and i + 1 < len(args):
            if config["llm"] is None:
                config["llm"] = {}
            config["llm"]["api_key"] = args[i + 1]; i += 2
        elif arg == "--allow-writes":
            config["allow_writes"] = True; i += 1
        elif arg == "--tags" and i + 1 < len(args):
            config["allowed_tags"] = {value.strip() for value in args[i + 1].split(",") if value.strip()}; i += 2
        elif arg == "--operations" and i + 1 < len(args):
            config["allowed_operations"] = {value.strip() for value in args[i + 1].split(",") if value.strip()}; i += 2
        elif arg == "--deny-operations" and i + 1 < len(args):
            config["denied_operations"] = {value.strip() for value in args[i + 1].split(",") if value.strip()}; i += 2
        elif not arg.startswith("--"):
            config["positional"].append(arg); i += 1
        else:
            i += 1

    return config


def main():
    banner()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  mcp-anything generate <spec> [options]")
        print("  mcp-anything discover <url> [options]")
        print("  mcp-anything info <spec>")
        print("  mcp-anything llm-providers")
        print()
        print("Generation Modes:")
        print("  (default)          Standard mechanical code generation")
        print("  --claude           Claude SDK enhancement (native tool_use)")
        print("  --agents           OpenAI Agents SDK pipeline (3-agent workflow)")
        print("  --llm PROVIDER     Generic LLM enhancement")
        print()
        print("Options:")
        print("  --output DIR             Output directory (default: ./output)")
        print("  --name NAME              Server name")
        print("  --env-prefix PREFIX      Environment variable prefix")
        print("  --allow-writes           Include state-changing tools")
        print("  --tags TAG1,TAG2         Restrict tools to tags")
        print("  --operations OP1,OP2     Restrict tools to operation IDs")
        print("  --deny-operations OP1    Exclude operation IDs")
        print("  --claude-model MODEL     Claude model (default: claude-sonnet-4-20250514)")
        print("  --agents-model MODEL     Agents model (default: anthropic/claude-sonnet-4)")
        print("  --agents-provider PROV   Agents provider (default: openrouter)")
        print("  --include-tests          Generate test cases")
        print("  --llm-model MODEL        Override LLM model")
        print("  --llm-key KEY            LLM API key")
        print("  --firecrawl-key KEY      Firecrawl API key")
        print()
        print("Examples:")
        print("  mcp-anything generate https://api.example.com/openapi.json")
        print("  mcp-anything generate spec.json --agents")
        print("  mcp-anything generate spec.json --agents-model openai/gpt-4o")
        print("  mcp-anything generate spec.json --agents-model meta-llama/llama-4-maverick")
        print("  mcp-anything generate spec.json --claude")
        print("  mcp-anything generate spec.json --llm openai")
        print("  mcp-anything discover https://api.example.com")
        print("  mcp-anything llm-providers")
        sys.exit(1)

    command = sys.argv[1]
    config = parse_args(sys.argv[2:])

    if command == "generate":
        spec = config["positional"][0] if config["positional"] else ""
        if not spec:
            print("Error: provide an OpenAPI spec URL or file path")
            sys.exit(1)
        generate_from_spec(
            spec_source=spec,
            output_dir=config["output"],
            server_name=config["name"],
            env_prefix=config["env_prefix"],
            llm_config=config["llm"],
            use_claude=config["claude"],
            claude_model=config["claude_model"],
            use_agents=config["agents"],
            agents_model=config["agents_model"],
            agents_provider=config["agents_provider"],
            include_tests=config["include_tests"],
            allow_writes=config["allow_writes"],
            allowed_tags=config["allowed_tags"],
            allowed_operations=config["allowed_operations"],
            denied_operations=config["denied_operations"],
        )

    elif command == "discover":
        url = config["positional"][0] if config["positional"] else ""
        if not url:
            print("Error: provide a website URL")
            sys.exit(1)
        discover_from_url(url, config["output"], config["firecrawl_key"], config["name"])

    elif command == "info":
        spec = config["positional"][0] if config["positional"] else ""
        if not spec:
            print("Error: provide an OpenAPI spec URL or file path")
            sys.exit(1)
        analyzer = OpenAPIAnalyzer(spec)
        analyzer.load()
        endpoints = analyzer.extract_endpoints()
        summary = analyzer.summary()
        print(json.dumps(summary, indent=2))
        print(f"\nEndpoints ({len(endpoints)}):")
        for ep in endpoints:
            print(f"  {ep.method:7s} {ep.path:40s} → {ep.operation_id}")

    elif command == "llm-providers":
        list_providers()

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
