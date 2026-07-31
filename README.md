# MCP-Anything

**Generate MCP servers for OpenAPI APIs, with optional LLM enhancement.**

MCP-Anything converts an OpenAPI 3.x document into a runnable [FastMCP](https://github.com/modelcontextprotocol/python-sdk) server. The generated server exposes API operations as typed MCP tools and can be connected to Claude Desktop, Cursor, OpenClaw, or another MCP client.

## Current status

- **Tier 1 (OpenAPI generation):** supported and tested.
- **Tier 2 (website/API documentation discovery):** supported through Firecrawl.
- **LLM enhancement:** optional OpenAI, Anthropic, Google, OpenRouter, Claude SDK, and OpenAI Agents SDK integrations.
- **Tier 3 browser-interaction servers:** not implemented.
- **Remote Dev PM profile:** the live Speccon Dev PM MCP server runs over Tailscale as a Streamable HTTP endpoint (`speccon-crm-devpm-write`, 161 tools); the read-only 139-tool profile is archived for rollback. See the Remote Dev PM section below.

## How it works

```text
OpenAPI JSON/YAML or URL
          │
          ▼
OpenAPIAnalyzer
  resolve refs, parameters, schemas, security, endpoints
          │
          ▼
MCPServerGenerator
  filter operations, generate typed FastMCP tools and runtime
          │
          ▼
Generated profile directory
  server.py + mcp_runtime.py + mcp_config.json + inventory + manifest + docs
          │
          ▼
MCP client over local stdio or SSH-backed stdio
```

The generated server uses the copied `mcp_runtime.py` for:

- API authentication with email/password login, refresh-token handling, or a static API token.
- JSON, form-encoded, and bounded multipart requests.
- Runtime capability checks for writes, tags, operation IDs, and HTTP methods.
- In-memory credentials and token state; credentials are not written into generated artifacts.

## Install

Requirements:

- Python 3.10 or newer.
- An OpenAPI 3.x JSON or YAML document, or a URL serving one.
- API credentials for the target service when the generated tools require authentication.

Install into an isolated virtual environment:

```bash
git clone https://github.com/TheophilusChinomona/mcp-anything.git
cd mcp-anything

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Optional dependency sets:

```bash
# Development and test dependencies
python -m pip install -e ".[dev]"

# All optional LLM and Agents SDK providers
python -m pip install -e ".[all]"

# Individual integrations
python -m pip install -e ".[openai]"
python -m pip install -e ".[anthropic]"
python -m pip install -e ".[google]"
python -m pip install -e ".[agents]"
```

Confirm the CLI is available:

```bash
mcp-anything llm-providers
```

## Generate an MCP server

Generate from a local or remote OpenAPI document:

```bash
mcp-anything generate \
  https://petstore3.swagger.io/api/v3/openapi.json \
  --output ./output/petstore

# Local JSON or YAML
mcp-anything generate ./specs/petstore.yaml --output ./output/petstore

# Inspect a specification without generating files
mcp-anything info ./specs/petstore.yaml
```

Useful generation controls:

```bash
# Name the server and its environment-variable prefix
mcp-anything generate spec.json \
  --output ./output/my-api \
  --name my-api \
  --env-prefix MY_API

# Keep only operations carrying selected OpenAPI tags
mcp-anything generate spec.json \
  --output ./output/read-profile \
  --tags Projects,Reports

# Keep only selected operation IDs
mcp-anything generate spec.json \
  --output ./output/small-profile \
  --operations listProjects,getProject

# Exclude selected operation IDs
mcp-anything generate spec.json \
  --output ./output/small-profile \
  --deny-operations deleteProject
```

Generated servers are read-only by default. `--allow-writes` is an explicit opt-in that includes state-changing operations; do not use it for an unreviewed or production profile.

To discover API documentation from a website:

```bash
export FIRECRAWL_API_KEY="..."
mcp-anything discover https://api.example.com --output ./output/discovery
```

## Generated artifacts

Every generated output directory contains the following files:

| File | Purpose |
|---|---|
| `{name}_server.py` | FastMCP server with one generated tool per selected endpoint |
| `mcp_runtime.py` | Self-contained authentication, HTTP, upload, and capability-policy runtime |
| `mcp_config.json` | MCP client configuration template |
| `tools_inventory.json` | Machine-readable registry of names, methods, paths, tags, parameters, and request bodies |
| `generation_manifest.json` | Generator identity, source hash, endpoint counts, profile name, and policy metadata |
| `.env.example` | Non-secret environment-variable template |
| `README.md` | Generated endpoint documentation and usage notes |
| `SKILL.md` | Agent-facing instructions for the generated tool set |

Keep `generation_manifest.json` with the generated artifact. It records the source SHA-256 so a deployed profile can be compared with the trusted workstation output.

## Configure and run a generated server

The environment prefix is derived from the server name unless `--env-prefix` is supplied. For a server named `my-api`, the generated variables are normally `MY_API_*`.

Set the generated values in the process environment. `.env.example` is a template; the generated server does not require or automatically load a `.env` file:

```bash
export MY_API_BASE_URL="https://api.example.com"
export MY_API_EMAIL="service-account@example.com"
export MY_API_PASSWORD="use-a-secret-manager-or-secure-shell"
export MY_API_API_KEY=""  # Use this instead of email/password when supported
export MY_API_ALLOW_WRITES="false"

python ./output/my-api/my_api_server.py
```

Use either email/password or a static API token as supported by the target API. Keep secrets outside Git, prompts, generated JSON, and `mcp_config.json`.

For a client configuration, start with the generated `mcp_config.json` and replace its command with the virtual-environment interpreter when needed:

```json
{
  "mcpServers": {
    "my-api": {
      "command": "/absolute/path/to/mcp-anything/.venv/bin/python",
      "args": [
        "/absolute/path/to/output/my-api/my_api_server.py"
      ],
      "env": {
        "MY_API_BASE_URL": "https://api.example.com",
        "MY_API_ALLOW_WRITES": "false",
        "MY_API_ALLOWED_METHODS": "GET"
      }
    }
  }
}
```

Do not put `MY_API_EMAIL`, `MY_API_PASSWORD`, or `MY_API_API_KEY` in shared client configuration when the client or filesystem is not a trusted secret store. Prefer a wrapper that sources a mode-640 environment file or the client’s approved secret mechanism.

## Agent setup instructions

These instructions are intended for an agent configuring an MCP client after a profile has been generated.

### 1. Inspect the profile before connecting it

```bash
cat output/my-api/generation_manifest.json
python -m json.tool output/my-api/tools_inventory.json >/dev/null
sed -n '1,160p' output/my-api/SKILL.md
```

Check:

1. `server_name`, `endpoint_count`, `spec_sha256`, and `allow_writes`.
2. The inventory’s `method`, `path`, `operation_id`, and `tags` for every tool you intend to use.
3. Whether the profile contains write methods. Treat any profile with `allow_writes: true` as requiring explicit human approval.

### 2. Register the server

Add the generated `mcp_config.json` entry to the selected MCP client, using absolute paths:

```json
{
  "mcpServers": {
    "my-api": {
      "command": "/absolute/path/to/mcp-anything/.venv/bin/python",
      "args": [
        "/absolute/path/to/output/my-api/my_api_server.py"
      ]
    }
  }
}
```

Restart the MCP client completely. Confirm that initialization succeeds and that the number of exposed tools matches the reviewed manifest/inventory.

### 3. Use the least-capable tool that satisfies the request

- Prefer `GET` tools for read-only work.
- Match the tool’s required parameters to `tools_inventory.json` before calling it.
- Do not infer that a similarly named operation is safe; inspect its HTTP method and path.
- Do not call `POST`, `PUT`, `PATCH`, or `DELETE` tools unless writes were explicitly approved for that profile.
- Never put credentials into a tool argument, prompt, generated file, or chat transcript.
- Report authentication, policy-denied, timeout, and HTTP errors without echoing secrets.

### 4. Verify without mutating data

For a new profile, first initialize the MCP connection and list tools. Then use one known harmless read operation. Do not use production-mutating calls as a connectivity test.

## Remote Dev PM profile (Streamable HTTP over Tailscale)

The live Speccon Dev PM MCP server runs on the `theo-zo` workstation over Tailscale as a Streamable HTTP endpoint — not SSH/stdio:

```text
local MCP client (speccon-erp alias)
      │ Streamable HTTP
      ▼
http://100.102.160.49:8000/mcp   (Tailscale IP, port 8000)
      │
      ▼
wrapper → speccon-crm-devpm-write FastMCP server (161 tools)
```

The endpoint binds the Tailscale interface only — no public listener, Funnel, or DNS exposure. The private OpenAPI spec stays on the trusted workstation; only the generated profile directory and manifest are deployed.

### Profile inventory

| Profile | Server name | Tools | Methods | State |
|---|---|---|---|---|
| `devpm-write` | `speccon-crm-devpm-write` | 161 (139 reads + 22 ticket/subtask writes) | `GET, POST, PUT, PATCH` | **LIVE** — served at the endpoint above |
| `devpm-read` | `speccon-crm-devpm-read` | 139 | `GET` only | dormant — archived rollback profile |

Both profiles share the `SPECCON_DEVPM` environment prefix and the `https://prod-erp-backend.azurewebsites.net` base URL. The write profile excludes the six `DELETE` operations and all non-ticket writes (projects, sprints, squads, settings, epics, labels, release notes, document imports, bug claims).

### Generate a profile locally

Run from the trusted workstation after obtaining the private spec through the approved process:

```bash
source venv/bin/activate
# read-only rollback profile (139 GET tools)
python ops/generate_devpm_profile.py \
  --profile read \
  --spec specs/speccon-openapi.json \
  --output output/speccon/profiles/devpm-read

# live ticket-write profile (161 tools)
python ops/generate_devpm_profile.py \
  --profile write \
  --spec specs/speccon-openapi.json \
  --output output/speccon/profiles/devpm-write
```

The helper pins the base URL, applies the Dev PM tag allowlist (defined in `ops/generate_devpm_profile.py`), and — for the write profile — the explicit 22-operation ticket write allowlist and 6-operation delete denylist.

Review `generation_manifest.json` and record the repository commit and `spec_sha256`. Never transfer `specs/speccon-openapi.json`, the generator source, or credentials.

### Live environment and wrapper (theo-zo)

The live secret file is `/home/theo-zo/.config/mcp-anything/speccon-devpm.env` (mode `0600`, outside Git). Its policy values differ per profile; the live write profile uses:

```dotenv
SPECCON_DEVPM_ALLOW_WRITES=true
SPECCON_DEVPM_ALLOWED_METHODS=GET,POST,PUT,PATCH
SPECCON_DEVPM_ALLOWED_OPERATIONS=<generator-emitted sorted union of the 139 GET and 22 write operation IDs>
SPECCON_DEVPM_DENIED_OPERATIONS=delete_api_devpm_DevPmTickets_Delete,delete_api_devpm_DevPmTickets_DeleteSubtask,delete_api_devpm_DevPmTickets_DeleteLink,delete_api_devpm_DevPmTickets_DeleteAttachment,delete_api_devpm_DevPmTickets_Unsubscribe,delete_api_devpm_DevPmTicketSubtasks_Delete
```

Credentials (`EMAIL`/`PASSWORD`/`API_KEY`) and the FastMCP transport settings (`FASTMCP_TRANSPORT=streamable-http`, `FASTMCP_HOST=100.102.160.49`, `FASTMCP_PORT=8000`, origin protection) live in the same file; never commit or paste them. The `<generator-emitted ...>` text above is a description — the deployed value must be the complete comma-separated list from the manifest.

The wrapper at `/home/theo-zo/.local/bin/speccon-devpm-http` sources the env file and execs the live profile, preserving MCP stdout:

```bash
#!/usr/bin/env bash
set -euo pipefail
set -a
source /home/theo-zo/.config/mcp-anything/speccon-devpm.env
set +a
exec /home/theo-zo/dev/mcp-anything/venv/bin/python \
  /home/theo-zo/dev/mcp-anything/output/speccon/profiles/devpm-write/speccon_crm_devpm_write_server.py
```

The process runs as the persistent omp hub service `speccon-devpm-http`. Restart it after changing the wrapper, env policy, or profile.

### Agent/client configuration

The client alias `speccon-erp` points at the Streamable HTTP endpoint (client-side JSON; no credentials in it):

```json
{
  "mcpServers": {
    "speccon-erp": {
      "url": "http://100.102.160.49:8000/mcp"
    }
  }
}
```

After restarting the client, verify initialization and the reviewed tool count. For the live write profile, the expected result is **161 tools** (`GET/POST/PUT/PATCH`, no `DELETE`).

### Rollback to read-only

To restore the 139-tool GET-only surface:

1. Archive the current write profile and manifest, then restore `devpm-read` into `output/speccon/profiles/` (the archived read-only tarball is the rollback baseline).
2. Set `SPECCON_DEVPM_ALLOW_WRITES=false` and `SPECCON_DEVPM_ALLOWED_METHODS=GET` in the env file.
3. Point the wrapper at `devpm-read/speccon_crm_devpm_read_server.py`.
4. Restart `speccon-devpm-http` and verify 139 tools.

The full operator runbook (including the older SSH layout for other hosts) is at `docs/superpowers/plans/2026-07-30-remote-dev-pm-mcp-deployment.md`. The agent prompt at `docs/agent-prompts/speccon-erp-mcp-setup.md` contains the behavioral rules for the live write profile.

## LLM enhancement

LLM enhancement is optional. It enriches descriptions and examples; it does not replace the OpenAPI schema or runtime capability policy.

| Provider | Default model | Environment variable |
|---|---|---|
| `hermes` | Built-in/local | None |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `anthropic` | `claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| `google` | `gemini-2.0-flash` | `GOOGLE_API_KEY` |
| `openrouter` | `anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |

Examples:

```bash
mcp-anything generate spec.json --llm openai
mcp-anything generate spec.json --llm anthropic --llm-model claude-sonnet-4-20250514
mcp-anything generate spec.json --llm google
mcp-anything generate spec.json --llm openrouter \
  --llm-model meta-llama/llama-4-maverick

# Claude SDK native tool-use enhancement
mcp-anything generate spec.json --claude

# OpenAI Agents SDK pipeline
mcp-anything generate spec.json --agents
```

LLM keys are used during generation. They are separate from the generated API server’s credentials.

## Programmatic usage

```python
from mcp_anything import MCPServerGenerator, OpenAPIAnalyzer

analyzer = OpenAPIAnalyzer("https://api.example.com/openapi.json").load()
generator = MCPServerGenerator(
    analyzer,
    server_name="my-api",
    env_prefix="MY_API",
    allow_writes=False,
)
result = generator.generate("./output/my-api")
print(result["server_file"])
print(result["tool_count"])
```

For a reusable profile with explicit policy boundaries, pass `allowed_tags`, `allowed_operations`, `denied_operations`, and `allowed_methods` to `MCPServerGenerator`. The Dev PM helper is the reference implementation for a fixed, strictly-scoped profile (read-only and ticket-write variants).

## Development and tests

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

pytest
```

Generated artifacts should be smoke-tested by compiling the generated server beside its copied runtime and by checking `tools_inventory.json` against `generation_manifest.json`.

## Limitations and roadmap

- Browser-interaction MCP servers for arbitrary sites are not implemented.
- Streaming support is not implemented.
- OAuth2 and service-specific authentication helpers are not generalized; generated runtime support currently covers login/password and static token patterns.
- Rate limiting and retry policy beyond authentication refresh are not generalized.
- Remote Tailscale deployment remains an operator runbook, not an automated installer.
- Multi-client access beyond the single Tailscale-bound Streamable HTTP endpoint (e.g. Tailscale Serve) is deferred until required.

## Relationship to CLI-Anything

| | CLI-Anything | MCP-Anything |
|---|---|---|
| **Output** | Click CLI commands | FastMCP tools |
| **Target** | Desktop software | APIs and web services |
| **Protocol** | Shell/terminal | Model Context Protocol |
| **Integration** | Claude Code, OpenClaw | Claude Desktop, Cursor, OpenClaw, or any MCP client |

## License

MIT
