"""
OpenAI Agents SDK Integration for MCP-Anything.

Uses the OpenAI Agents SDK with OpenRouter as the model provider.
Creates multi-agent pipelines for analyzing APIs and generating MCP servers.

Architecture:
  ┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
  │  Analyzer    │ ──→ │  Designer    │ ──→ │  Code Generator  │
  │  Agent       │     │  Agent       │     │  Agent           │
  └─────────────┘     └──────────────┘     └─────────────────┘
        │                     │                      │
   Parse spec          Design tools          Generate server
   Extract meta        Group tools           Write files
   Identify flows      Plan structure        Validate output

Works with any OpenRouter-compatible model (Claude, GPT-4, Llama, Gemini, etc.)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Callable

from agents import Agent, Runner, function_tool, RunConfig, OpenAIChatCompletionsModel
from openai import AsyncOpenAI


# ─── OpenRouter Client Setup ─────────────────────────────────────────────────

def create_openrouter_client(api_key: str = "") -> AsyncOpenAI:
    """Create an AsyncOpenAI client configured for OpenRouter."""
    key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    return AsyncOpenAI(
        api_key=key,
        base_url="https://openrouter.ai/api/v1",
    )


def create_agent_model(
    model: str = "anthropic/claude-sonnet-4",
    api_key: str = "",
    provider: str = "openrouter",
) -> OpenAIChatCompletionsModel:
    """Create a model instance for the Agents SDK.

    Args:
        model: Model identifier (e.g., "anthropic/claude-sonnet-4", "openai/gpt-4o")
        api_key: API key for the provider
        provider: "openrouter", "openai", or "anthropic" (default: openrouter)
    """
    if provider == "openrouter":
        client = create_openrouter_client(api_key)
    elif provider == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        client = AsyncOpenAI(api_key=key)
    elif provider == "anthropic":
        # Anthropic via OpenAI-compatible endpoint (OpenRouter handles this)
        client = create_openrouter_client(api_key)
    else:
        client = create_openrouter_client(api_key)

    return OpenAIChatCompletionsModel(model=model, openai_client=client)


# ─── Shared Tools (available to all agents) ──────────────────────────────────

@function_tool
def validate_json_schema(schema_str: str) -> str:
    """Validate that a string is valid JSON Schema.

    Args:
        schema_str: The JSON schema string to validate
    """
    try:
        schema = json.loads(schema_str)
        if not isinstance(schema, dict):
            return "ERROR: Schema must be a JSON object"
        if "type" not in schema:
            return "WARNING: Schema missing 'type' field"
        return f"VALID: type={schema.get('type')}, properties={len(schema.get('properties', {}))}"
    except json.JSONDecodeError as e:
        return f"ERROR: Invalid JSON - {e}"


@function_tool
def sanitize_python_name(name: str) -> str:
    """Convert any string into a valid Python identifier (snake_case).

    Args:
        name: The string to sanitize
    """
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    if name and name[0].isdigit():
        name = f"op_{name}"
    return name.lower()


@function_tool
def write_file_tool(path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed.

    Args:
        path: Absolute file path to write to
        content: The file content
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"SUCCESS: Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"ERROR: {e}"


@function_tool
def read_file_tool(path: str) -> str:
    """Read content from a file.

    Args:
        path: Absolute file path to read
    """
    try:
        return Path(path).read_text()[:10000]
    except Exception as e:
        return f"ERROR: {e}"


# ─── Agent Definitions ───────────────────────────────────────────────────────

ANALYZER_INSTRUCTIONS = """You are an API Analysis Agent. Your job is to examine OpenAPI specifications and extract comprehensive metadata.

For each endpoint you find, you must determine:
1. The HTTP method and path
2. A clear, one-sentence summary
3. All parameters (path, query, header) with types and constraints
4. Request body schema (if any)
5. Response schema (for 200/201 responses)
6. Authentication requirements
7. Rate limiting hints
8. Tags/categories for grouping

You also analyze the overall API:
- API purpose and domain
- Base URL and versioning scheme
- Authentication method (API key, OAuth2, Bearer, etc.)
- Available scopes/permissions
- Common patterns across endpoints

Output your analysis as structured JSON that downstream agents can consume.
Be thorough but concise. Focus on information that matters for MCP tool generation."""

DESIGNER_INSTRUCTIONS = """You are an MCP Tool Design Agent. You take API analysis and design optimal MCP tool definitions.

For each API endpoint, you design:
1. A clean, Pythonic tool name (snake_case)
2. An action-oriented description (starts with a verb, tells the agent what happens)
3. Typed parameters with constraints and examples
4. Expected response format
5. Error handling strategy

You also create logical groupings:
- Group related tools into workflow-oriented clusters
- Identify common tool sequences (e.g., "list → get → update → delete")
- Suggest parameter defaults and optional fields

Design principles:
- Tool names should be self-documenting
- Descriptions should explain WHAT the tool does, not just echo the endpoint name
- Parameters should have clear types, constraints, and examples
- Consider the agent's perspective: what information does it need?

Output your designs as structured JSON with tool definitions and groupings."""

GENERATOR_INSTRUCTIONS = """You are an MCP Server Code Generator Agent. You take tool designs and produce production-ready FastMCP server code.

Your output must be:
1. Syntactically valid Python
2. A complete, self-contained MCP server file
3. Using FastMCP with @mcp.tool() decorators
4. With proper type annotations
5. With comprehensive docstrings
6. With error handling for HTTP requests
7. With environment variable configuration

Code quality standards:
- Follow PEP 8 style
- Use httpx for HTTP requests
- Return structured dicts (JSON-serializable)
- Handle errors gracefully
- Include configuration via environment variables
- Add a proper module docstring with API metadata

Always validate your generated code is syntactically correct before returning it.
Use the write_file_tool to save the generated server file."""


# ─── Pipeline Orchestrator ───────────────────────────────────────────────────

@dataclass
class AgentPipelineResult:
    """Result from running the multi-agent pipeline."""
    server_file: str = ""
    config_file: str = ""
    inventory_file: str = ""
    tool_count: int = 0
    group_count: int = 0
    analysis: dict = field(default_factory=dict)
    designs: list[dict] = field(default_factory=list)
    groups: list[dict] = field(default_factory=list)
    model: str = ""
    provider: str = ""


class OpenAIAgentsPipeline:
    """Multi-agent pipeline for MCP server generation using OpenAI Agents SDK.

    Creates a pipeline of specialized agents:
    1. Analyzer Agent - Parses OpenAPI spec, extracts metadata
    2. Designer Agent - Designs tool definitions and groupings
    3. Generator Agent - Produces FastMCP server code

    Supports any OpenRouter-compatible model.
    """

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4",
        api_key: str = "",
        provider: str = "openrouter",
    ):
        self.model = model
        self.api_key = api_key
        self.provider = provider
        self._model_instance = None

    @property
    def model_instance(self):
        if self._model_instance is None:
            self._model_instance = create_agent_model(
                model=self.model,
                api_key=self.api_key,
                provider=self.provider,
            )
        return self._model_instance

    def _create_analyzer(self) -> Agent:
        return Agent(
            name="API-Analyzer",
            instructions=ANALYZER_INSTRUCTIONS,
            model=self.model_instance,
            tools=[validate_json_schema, read_file_tool],
        )

    def _create_designer(self) -> Agent:
        return Agent(
            name="Tool-Designer",
            instructions=DESIGNER_INSTRUCTIONS,
            model=self.model_instance,
            tools=[sanitize_python_name, validate_json_schema],
        )

    def _create_generator(self, output_dir: str) -> Agent:
        return Agent(
            name="Code-Generator",
            instructions=GENERATOR_INSTRUCTIONS + f"\n\nWrite all files to: {output_dir}/",
            model=self.model_instance,
            tools=[write_file_tool, read_file_tool, sanitize_python_name],
        )

    async def run(
        self,
        spec_source: str,
        output_dir: str = "./output",
        server_name: str = "",
        on_progress: Callable | None = None,
    ) -> AgentPipelineResult:
        """Run the full multi-agent pipeline.

        Args:
            spec_source: OpenAPI spec URL or file path
            output_dir: Where to write generated files
            server_name: Name for the MCP server
            on_progress: Callback(agent_name, message)
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Load spec content
        spec_content = self._load_spec(spec_source)

        result = AgentPipelineResult(
            model=self.model,
            provider=self.provider,
        )

        # ── Step 1: Analyzer ──
        if on_progress:
            on_progress("analyzer", f"Analyzing API spec...")

        analyzer = self._create_analyzer()
        analysis_prompt = f"""Analyze this OpenAPI specification and extract all endpoint metadata.

Spec source: {spec_source}

Spec content:
{spec_content[:15000]}

Return a JSON object with:
{{
  "api": {{
    "title": "...",
    "version": "...",
    "description": "...",
    "base_url": "...",
    "auth_type": "api_key|oauth2|bearer|none",
    "auth_header": "Authorization|X-API-Key|..."
  }},
  "endpoints": [
    {{
      "operation_id": "...",
      "method": "GET|POST|...",
      "path": "/...",
      "summary": "...",
      "description": "...",
      "tags": ["..."],
      "parameters": [
        {{"name": "...", "location": "path|query|header", "type": "string|integer|...", "required": true, "description": "...", "constraints": "..."}}
      ],
      "request_body": {{"content_type": "...", "schema": {{...}}}},
      "response_schema": {{...}},
      "auth_required": true|false
    }}
  ]
}}"""

        analysis_result = await Runner.run(analyzer, analysis_prompt)
        analysis_text = analysis_result.final_output

        # Parse analysis
        try:
            analysis = self._extract_json(analysis_text)
        except Exception:
            analysis = {"raw": analysis_text, "parse_error": True}

        result.analysis = analysis
        endpoints = analysis.get("endpoints", [])
        api_meta = analysis.get("api", {})

        if on_progress:
            on_progress("analyzer", f"Found {len(endpoints)} endpoints")

        if not server_name:
            server_name = re.sub(
                r'[^a-zA-Z0-9_-]', '-',
                api_meta.get("title", "api").lower()
            ).strip('-') or "generated-api"

        # ── Step 2: Designer ──
        if on_progress:
            on_progress("designer", f"Designing {len(endpoints)} MCP tools...")

        designer = self._create_designer()
        design_prompt = f"""Design MCP tool definitions for these API endpoints.

API: {api_meta.get('title', 'Unknown')} v{api_meta.get('version', 'Unknown')}
Base URL: {api_meta.get('base_url', 'Unknown')}
Auth: {api_meta.get('auth_type', 'none')}

Endpoints:
{json.dumps(endpoints[:20], indent=2)}

For each endpoint, produce a tool design. Also suggest logical groupings.

Return JSON:
{{
  "tools": [
    {{
      "operation_id": "...",
      "tool_name": "snake_case_name",
      "description": "Action-oriented description starting with a verb",
      "parameters": [
        {{"name": "snake_case", "python_type": "str|int|float|bool|dict", "required": true, "default": null, "description": "...", "example": "..."}}
      ],
      "returns": "Description of what the tool returns",
      "error_handling": "...",
      "prerequisites": "..."
    }}
  ],
  "groups": [
    {{
      "name": "group_name",
      "description": "...",
      "tools": ["tool1", "tool2"],
      "workflow": "Typical sequence of calls"
    }}
  ]
}}"""

        design_result = await Runner.run(designer, design_prompt)
        design_text = design_result.final_output

        try:
            designs = self._extract_json(design_text)
        except Exception:
            designs = {"raw": design_text, "parse_error": True}

        tool_designs = designs.get("tools", [])
        groups = designs.get("groups", [])
        result.designs = tool_designs
        result.groups = groups

        if on_progress:
            on_progress("designer", f"Designed {len(tool_designs)} tools in {len(groups)} groups")

        # ── Step 3: Generator ──
        if on_progress:
            on_progress("generator", f"Generating FastMCP server code...")

        generator = self._create_generator(str(output_path))

        env_prefix = server_name.upper().replace("-", "_")

        generator_prompt = f"""Generate a complete FastMCP server for this API.

API: {api_meta.get('title', 'Unknown')} v{api_meta.get('version', 'Unknown')}
Base URL: {api_meta.get('base_url', 'Unknown')}
Auth: {api_meta.get('auth_type', 'none')}
Server name: {server_name}
Env prefix: {env_prefix}

Tool designs:
{json.dumps(tool_designs[:25], indent=2)}

Groups:
{json.dumps(groups, indent=2)}

Generate:
1. {server_name}_server.py - Complete FastMCP server with all tools
2. mcp_config.json - MCP client configuration
3. tools_inventory.json - Machine-readable tool registry
4. .env.example - Environment variable template

Use the write_file_tool to write each file to: {output_path}/

The server must:
- Import fastmcp, httpx, os
- Use @mcp.tool() decorators
- Have typed parameters with docstrings
- Return JSON-serializable dicts
- Use environment variables for BASE_URL and API_KEY
- Handle HTTP errors gracefully"""

        gen_result = await Runner.run(generator, generator_prompt)
        gen_text = gen_result.final_output

        result.tool_count = len(tool_designs)
        result.group_count = len(groups)

        # Find generated files
        server_file = output_path / f"{server_name}_server.py"
        if server_file.exists():
            result.server_file = str(server_file)
        config_file = output_path / "mcp_config.json"
        if config_file.exists():
            result.config_file = str(config_file)
        inventory_file = output_path / "tools_inventory.json"
        if inventory_file.exists():
            result.inventory_file = str(inventory_file)

        # If generator didn't write files, create them from designs
        if not result.server_file:
            if on_progress:
                on_progress("generator", "Writing server from designs...")
            self._write_server_from_designs(
                output_path, server_name, env_prefix, api_meta,
                tool_designs, groups, spec_source,
            )
            result.server_file = str(output_path / f"{server_name}_server.py")
            result.config_file = str(output_path / "mcp_config.json")
            result.inventory_file = str(output_path / "tools_inventory.json")

        if on_progress:
            on_progress("done", f"Generated {result.tool_count} tools")

        return result

    def run_sync(self, **kwargs) -> AgentPipelineResult:
        """Synchronous wrapper for run()."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.run(**kwargs))

    def _load_spec(self, source: str) -> str:
        """Load spec content from URL or file."""
        if source.startswith(("http://", "https://")):
            import httpx
            resp = httpx.get(source, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            return resp.text
        else:
            return Path(source).read_text()

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response (handles markdown wrapping)."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (```json ... ````)
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        return json.loads(text)

    def _write_server_from_designs(
        self,
        output_path: Path,
        server_name: str,
        env_prefix: str,
        api_meta: dict,
        tool_designs: list[dict],
        groups: list[dict],
        spec_source: str,
    ):
        """Fallback: write server from design data if generator didn't write it."""
        base_url = api_meta.get("base_url", "/")

        lines = [
            '"""',
            f'{server_name} - MCP Server (OpenAI Agents SDK Generated)',
            f'Generated by MCP-Anything with OpenAI Agents SDK',
            f'Model: {self.model}',
            '',
            f'Title: {api_meta.get("title", "Unknown")}',
            f'Version: {api_meta.get("version", "Unknown")}',
            f'Base URL: {base_url}',
            f'Tools: {len(tool_designs)}',
            '"""',
            '',
            'import json',
            'import os',
            'from typing import Any, Literal, Optional',
            '',
            'import httpx',
            'from fastmcp import FastMCP',
            '',
            '# ─── Configuration ──────────────────────────────────────────────────────',
            '',
            f'BASE_URL = os.environ.get("{env_prefix}_BASE_URL", "{base_url}")',
            f'API_KEY = os.environ.get("{env_prefix}_API_KEY", "")',
            '',
            '# ─── HTTP Client ────────────────────────────────────────────────────────',
            '',
            'def _get_headers() -> dict:',
            '    headers = {"Content-Type": "application/json", "Accept": "application/json"}',
            '    if API_KEY:',
            '        headers["Authorization"] = f"Bearer {API_KEY}"',
            '    return headers',
            '',
            'def _request(method: str, path: str, params: dict = None, body: dict = None) -> dict:',
            '    """Make an HTTP request and return parsed JSON."""',
            '    url = BASE_URL.rstrip("/") + path',
            '    with httpx.Client(timeout=30) as client:',
            '        resp = client.request(',
            '            method=method,',
            '            url=url,',
            '            params=params or {},',
            '            json=body if body else None,',
            '            headers=_get_headers(),',
            '        )',
            '        resp.raise_for_status()',
            '        if resp.status_code == 204:',
            '            return {"status": "success", "code": 204}',
            '        try:',
            '            return resp.json()',
            '        except Exception:',
            '            return {"status": "success", "text": resp.text[:2000]}',
            '',
            '# ─── MCP Server ─────────────────────────────────────────────────────────',
            '',
            f'mcp = FastMCP("{server_name}")',
            '',
        ]

        # Generate tools from designs
        for design in tool_designs:
            tool_name = design.get("tool_name", design.get("operation_id", "unknown").lower())
            desc = design.get("description", "")
            params = design.get("parameters", [])

            # Build param signature
            param_parts = []
            for p in params:
                pname = p.get("name", "param")
                ptype = p.get("python_type", "Any")
                type_map = {"str": "str", "int": "int", "float": "float", "bool": "bool", "dict": "dict", "list": "list"}
                py_type = type_map.get(ptype, "Any")
                if p.get("required", False):
                    param_parts.append(f"{pname}: {py_type}")
                else:
                    default = repr(p.get("default", "")) if p.get("default") is not None else ('""' if py_type == "str" else "None")
                    param_parts.append(f"{pname}: {py_type} = {default}")

            if design.get("has_body"):
                param_parts.append("body: dict = {}")

            params_str = ", ".join(param_parts)

            # Build docstring
            doc_lines = [desc]
            if params:
                doc_lines.append("")
                for p in params:
                    pdoc = p.get("description", "")
                    if p.get("example"):
                        pdoc += f" (e.g., {p['example']})"
                    doc_lines.append(f"    {p.get('name', 'param')}: {pdoc}")

            doc_str = "\n".join(doc_lines)

            # Build body
            method = design.get("method", "GET")
            path = design.get("path", "/")

            body_lines = [f'    path = f"{path}"']
            body_lines.append("    query_params = {}")

            for p in params:
                if p.get("location") == "query":
                    pname = p.get("name", "param")
                    body_lines.append(f"    if {pname} is not None and {pname} != '':")
                    body_lines.append(f'        query_params["{pname}"] = {pname}')

            if design.get("has_body"):
                body_lines.append("    request_body = body if body else None")
            else:
                body_lines.append("    request_body = None")

            body_lines.append(f'    return _request("{method}", path, params=query_params, body=request_body)')

            body_str = "\n".join(body_lines)

            lines.extend([
                '@mcp.tool()',
                f'def {tool_name}({params_str}) -> dict:',
                f'    """{doc_str}"""',
                body_str,
                '',
            ])

        server_code = "\n".join(lines)
        server_file = output_path / f"{server_name}_server.py"
        server_file.write_text(server_code)

        # Write config
        config = {
            "mcpServers": {
                server_name: {
                    "command": "python3",
                    "args": [str(server_file)],
                    "env": {
                        f"{env_prefix}_BASE_URL": f"${{{env_prefix}_BASE_URL}}",
                        f"{env_prefix}_API_KEY": f"${{{env_prefix}_API_KEY}}",
                    },
                }
            }
        }
        (output_path / "mcp_config.json").write_text(json.dumps(config, indent=2))

        # Write inventory
        inventory = []
        for d in tool_designs:
            inventory.append({
                "name": d.get("tool_name", ""),
                "operation_id": d.get("operation_id", ""),
                "description": d.get("description", ""),
                "parameters": d.get("parameters", []),
                "group": next(
                    (g["name"] for g in groups if d.get("tool_name", "") in g.get("tools", [])),
                    "ungrouped"
                ),
            })
        (output_path / "tools_inventory.json").write_text(json.dumps(inventory, indent=2))

        # Write .env
        (output_path / ".env.example").write_text(
            f"# {server_name} MCP Server\n"
            f"{env_prefix}_BASE_URL={base_url}\n"
            f"{env_prefix}_API_KEY=\n"
        )
