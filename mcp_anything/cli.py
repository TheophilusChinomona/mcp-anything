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


BANNER = """
╔══════════════════════════════════════════════════════════╗
║  🔌 MCP-Anything: Generate MCP Servers for Any API      ║
║  🤖 With pluggable LLM backends for enhanced generation  ║
╚══════════════════════════════════════════════════════════╝
"""


def banner():
    print(BANNER)


def generate_from_spec(
    spec_source: str,
    output_dir: str,
    server_name: str = "",
    env_prefix: str = "",
    llm_config: dict | None = None,
):
    """Tier 1: Generate MCP server from an OpenAPI spec."""
    print(f"📋 Loading OpenAPI spec: {spec_source[:80]}...")
    analyzer = OpenAPIAnalyzer(spec_source)
    analyzer.load()

    summary = analyzer.summary()
    print(f"✅ Loaded: {summary['title']} v{summary['version']}")
    print(f"   Base URL: {summary['base_url']}")
    print(f"   Endpoints: {summary['endpoint_count']}")

    endpoints = analyzer.extract_endpoints()
    print(f"   Extracted {len(endpoints)} tool definitions")

    # LLM enhancement if configured
    if llm_config:
        print(f"\n🤖 Enhancing with LLM ({llm_config.get('provider', 'default')}...")
        try:
            from mcp_anything.enhancer import LLMEnhancedGenerator
            llm = create_llm(config=llm_config)
            enhancer = LLMEnhancedGenerator(analyzer, llm=llm)
            enhanced = enhancer.enhance_all()
            enh_summary = enhancer.get_enhancement_summary()
            print(f"   Enhanced {enh_summary['total_tools']} tools")
            print(f"   - With examples: {enh_summary['tools_with_examples']}")
            print(f"   - With error handling: {enh_summary['tools_with_error_handling']}")
            print(f"   - With notes: {enh_summary['tools_with_notes']}")
        except Exception as e:
            print(f"   ⚠️  LLM enhancement failed: {e}")
            print(f"   Continuing with standard generation...")

    print(f"\n🔨 Generating MCP server...")
    generator = MCPServerGenerator(analyzer, server_name=server_name, env_prefix=env_prefix)
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
    print(f"   Base patterns: {api_info['base_patterns'][:5]}")

    # Try to find OpenAPI spec
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
    print(f"  {'Provider':<15} {'Default Model':<35} {'Env Var':<25} {'Note'}")
    print(f"  {'─'*15} {'─'*35} {'─'*25} {'─'*30}")
    for p in get_available_providers():
        print(f"  {p['provider']:<15} {p['default_model']:<35} {p['env_var']:<25} {p.get('note', '')}")
    print(f"\n💡 Set MCP_ANYTHING_LLM_PROVIDER to auto-select a provider.")
    print(f"   Example: export MCP_ANYTHING_LLM_PROVIDER=anthropic")


def parse_llm_args(args: list[str]) -> dict | None:
    """Parse LLM-related CLI flags."""
    config = {}
    has_llm = False

    i = 0
    while i < len(args):
        if args[i] == "--llm" and i + 1 < len(args):
            config["provider"] = args[i + 1]
            has_llm = True
            i += 2
        elif args[i] == "--llm-model" and i + 1 < len(args):
            config["model"] = args[i + 1]
            has_llm = True
            i += 2
        elif args[i] == "--llm-key" and i + 1 < len(args):
            config["api_key"] = args[i + 1]
            has_llm = True
            i += 2
        else:
            i += 1

    return config if has_llm else None


def main():
    banner()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  mcp-anything generate <spec_url_or_file> [options]")
        print("  mcp-anything discover <website_url> [options]")
        print("  mcp-anything info <spec_url_or_file>")
        print("  mcp-anything llm-providers")
        print()
        print("Options:")
        print("  --output DIR         Output directory (default: ./output)")
        print("  --name NAME          Server name")
        print("  --env-prefix PREFIX  Environment variable prefix")
        print("  --llm PROVIDER       Use LLM for enhanced generation")
        print("  --llm-model MODEL    Override default model")
        print("  --llm-key KEY        API key for LLM provider")
        print("  --firecrawl-key KEY  Firecrawl API key")
        print()
        print("Examples:")
        print("  mcp-anything generate https://api.example.com/openapi.json")
        print("  mcp-anything generate spec.json --llm anthropic --output ./my-api")
        print("  mcp-anything generate spec.json --llm openai --llm-model gpt-4o")
        print("  mcp-anything discover https://api.example.com")
        print("  mcp-anything llm-providers")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    # Parse common flags
    output_dir = "./output"
    server_name = ""
    env_prefix = ""
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")
    llm_config = parse_llm_args(args)

    # Parse remaining flags
    positional = []
    i = 0
    while i < len(args):
        if args[i] in ("--output", "--name", "--env-prefix", "--firecrawl-key", "--llm", "--llm-model", "--llm-key"):
            i += 2  # skip flag and value
        elif args[i] == "--output" and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif args[i] == "--name" and i + 1 < len(args):
            server_name = args[i + 1]
            i += 2
        elif args[i] == "--env-prefix" and i + 1 < len(args):
            env_prefix = args[i + 1]
            i += 2
        elif args[i] == "--firecrawl-key" and i + 1 < len(args):
            firecrawl_key = args[i + 1]
            i += 2
        elif not args[i].startswith("--"):
            positional.append(args[i])
            i += 1
        else:
            i += 1

    # Re-parse to get actual values (the above loop skips them)
    output_dir = "./output"
    server_name = ""
    env_prefix = ""
    i = 0
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif args[i] == "--name" and i + 1 < len(args):
            server_name = args[i + 1]
            i += 2
        elif args[i] == "--env-prefix" and i + 1 < len(args):
            env_prefix = args[i + 1]
            i += 2
        elif args[i] == "--firecrawl-key" and i + 1 < len(args):
            firecrawl_key = args[i + 1]
            i += 2
        elif args[i] in ("--llm", "--llm-model", "--llm-key"):
            i += 2  # already parsed by parse_llm_args
        elif not args[i].startswith("--"):
            i += 1
        else:
            i += 1

    if command == "generate":
        spec = positional[0] if positional else ""
        if not spec:
            print("Error: provide an OpenAPI spec URL or file path")
            sys.exit(1)
        generate_from_spec(spec, output_dir, server_name, env_prefix, llm_config)

    elif command == "discover":
        url = positional[0] if positional else ""
        if not url:
            print("Error: provide a website URL")
            sys.exit(1)
        discover_from_url(url, output_dir, firecrawl_key, server_name)

    elif command == "info":
        spec = positional[0] if positional else ""
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
